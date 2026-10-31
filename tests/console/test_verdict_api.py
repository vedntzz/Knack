import json
from pathlib import Path
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from knack.console.app import create_app
from knack.console.links import CONSOLE_URL, verdict_url
from knack.contracts.models import MatchedCode, Root, Verdict
from knack.dispute.rulings import append_ruling, RulingRecord
from knack.receipts.chain import append_receipt, guard_receipt, Receipt
from knack.receipts.warns import record_warn

REPO = "apache/airflow"
RULE = "no-alias-sort-keys"
CLONE = "/w/airflow"
QUOTE = "Sorting by an alias never worked; drop both keys."
SOURCE = "https://github.com/apache/airflow/pull/75025"


def root_fields(quote: str = QUOTE) -> dict[str, Any]:
    return {
        "id": "root-75025",
        "title": "Sort keys are columns",
        "decision": "Drop the aliased sort keys.",
        "why": "An alias was never sortable.",
        "decided_by": "maria",
        "source_url": SOURCE,
        "quote": quote,
        "status": "Confirmed",
        "rejected_alternative": "Keep the aliases.",
    }


def deny(matched: str = '"state"') -> Verdict:
    return Verdict(
        allowed=False,
        reason="Knack blocked this edit.",
        rule_id=RULE,
        root_ids=["root-75025"],
        latency_ms=12.5,
        matched=[MatchedCode(line=23, text=matched)],
    )


def allow() -> Verdict:
    return Verdict(allowed=True, reason="no rule matched", latency_ms=3.25)


class World:
    # A receipts file, a warns file and a registry with one Confirmed root.
    def __init__(self, base: Path) -> None:
        self.receipts = base / "verdicts.jsonl"
        self.warns = base / "warns.jsonl"
        self.rulings = base / "rulings.jsonl"
        self.registry = base / "registry" / "registry.json"
        self.write_root(root_fields())
        rules = [{"rule": "rules/no-alias.yml", "root_ids": ["root-75025"]}]
        body = {"repo": REPO, "roots_dir": "roots", "rules": rules}
        self.registry.write_text(json.dumps(body))

    def write_root(self, fields: dict[str, Any]) -> None:
        roots = self.registry.parent / "roots"
        roots.mkdir(parents=True, exist_ok=True)
        (roots / "root-75025.json").write_text(json.dumps(fields))

    def receipt(
        self,
        verdict: Verdict,
        time: str,
        branch: str | None = "fix-sort",
        rule: str = RULE,
        repo: str = REPO,
        session: str | None = "s-1",
    ) -> Receipt:
        root = Root.model_validate(root_fields())
        fields = guard_receipt(
            repo,
            f"{CLONE}/dags.py",
            rule,
            root if verdict.root_ids else None,
            verdict,
            time,
            branch=branch,
            session_id=session,
        )
        return append_receipt(self.receipts, fields)

    def warn(self, context: str, time: str, session: str | None = "s-1") -> None:
        record_warn(self.warns, REPO, Path(CLONE), session, context, time)

    def ruling(
        self,
        receipt: Receipt,
        objection: str,
        decision: Literal["hold", "escalate"] = "hold",
    ) -> None:
        cited = [QUOTE] if decision == "hold" else []
        record = RulingRecord(
            time=at(7),
            receipt_hash=receipt.hash,
            objection=objection,
            decision=decision,
            reply="The quote answers this.",
            cited_quotes=cited,
            model="muse-spark-1.3",
        )
        append_ruling(self.rulings, record)

    def client(self) -> TestClient:
        app = create_app(self.receipts, self.warns, self.rulings, self.registry_for)
        return TestClient(app)

    def registry_for(self, repo: str) -> Path | None:
        return self.registry if repo == REPO else None


def at(minute: int) -> str:
    return f"2026-10-31T12:{minute:02d}:00+00:00"


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def get(world: World, receipt: Receipt) -> dict[str, Any]:
    response = world.client().get(f"/verdict/{receipt.hash}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    return response.json()


def test_the_deny_carries_its_decision_decider_why_quote_and_source(
    world: World,
) -> None:
    body = get(world, world.receipt(deny(), at(5)))
    assert body["outcome"] == "deny"
    root = body["root"]
    assert (root["decision"], root["decided_by"]) == (
        "Drop the aliased sort keys.",
        "maria",
    )
    assert (root["why"], root["quote"], root["source_url"]) == (
        "An alias was never sortable.",
        QUOTE,
        SOURCE,
    )
    assert root["rejected_alternative"] == "Keep the aliases."


def test_the_deny_carries_matched_code_latency_and_where(world: World) -> None:
    receipt = world.receipt(deny(), at(5))
    body = get(world, receipt)
    assert body["matched"] == [{"line": 23, "text": '"state"'}]
    assert body["latency_ms"] == 12.5
    assert (body["hash"], body["time"], body["rule_id"]) == (receipt.hash, at(5), RULE)
    assert (body["repo"], body["branch"]) == (REPO, "fix-sort")
    assert body["file"] == f"{CLONE}/dags.py"


def test_the_receipt_and_quote_verify(world: World) -> None:
    body = get(world, world.receipt(deny(), at(5)))
    assert body["hash_verified"] is True
    assert body["root"]["quote_verified"] is True


def test_a_quote_edited_since_the_deny_is_flagged(world: World) -> None:
    receipt = world.receipt(deny(), at(5))
    world.write_root(root_fields("A different quote, written later."))
    root = get(world, receipt)["root"]
    assert root["quote_verified"] is False


def test_a_tampered_receipt_is_flagged(world: World) -> None:
    receipt = world.receipt(deny(), at(5))
    record = json.loads(world.receipts.read_text())
    world.receipts.write_text(json.dumps(record | {"latency_ms": 1.0}) + "\n")
    body = get(world, receipt)
    assert (body["latency_ms"], body["hash_verified"]) == (1.0, False)


def test_other_decisions_are_the_rules_on_that_branch(world: World) -> None:
    before = world.receipt(allow(), at(1))
    world.receipt(allow(), at(2), branch="main")
    world.receipt(allow(), at(3), rule="other-rule")
    world.receipt(allow(), at(4), repo="fastapi/fastapi")
    denied = world.receipt(deny(), at(5))
    after = world.receipt(deny('"start_date"'), at(6))
    others = get(world, denied)["other_decisions"]
    assert [o["hash"] for o in others] == [before.hash, after.hash]
    assert [o["outcome"] for o in others] == ["allow", "deny"]
    assert set(others[0]) == {"hash", "time", "file", "outcome", "latency_ms"}


def test_the_warn_is_the_sessions_latest_before_the_deny(world: World) -> None:
    world.warn("older warning", at(1))
    world.warn("other session's warning", at(2), session="s-2")
    world.warn("the warning the agent had", at(3))
    denied = world.receipt(deny(), at(5))
    world.warn("a later warning", at(6))
    warn = get(world, denied)["warn"]
    assert warn == {"time": at(3), "context": "the warning the agent had"}


def test_no_warn_before_the_deny_is_null(world: World) -> None:
    denied = world.receipt(deny(), at(5))
    world.warn("a later warning", at(6))
    assert get(world, denied)["warn"] is None


def test_a_sessionless_receipt_takes_the_clones_latest_warn(world: World) -> None:
    world.warn("from some session", at(3))
    denied = world.receipt(deny(), at(5), session=None)
    assert get(world, denied)["warn"]["context"] == "from some session"


def test_a_root_gone_from_the_store_is_null(world: World) -> None:
    receipt = world.receipt(deny(), at(5))
    (world.registry.parent / "roots" / "root-75025.json").unlink()
    body = get(world, receipt)
    assert (body["outcome"], body["root"]) == ("deny", None)


def test_a_repo_with_no_registry_still_answers(world: World) -> None:
    receipt = world.receipt(allow(), at(5), repo="someone/else")
    assert get(world, receipt)["root"] is None


def test_an_unknown_hash_is_404(world: World) -> None:
    world.receipt(deny(), at(5))
    response = world.client().get(f"/verdict/{'a' * 64}")
    assert response.status_code == 404
    assert response.json() == {"detail": "no receipt with that hash"}


def test_a_missing_receipts_file_is_404(world: World) -> None:
    assert world.client().get(f"/verdict/{'a' * 64}").status_code == 404


def test_the_console_is_local_and_links_by_hash() -> None:
    assert CONSOLE_URL == "http://127.0.0.1:7655"
    assert verdict_url("ab" * 32) == f"{CONSOLE_URL}/verdict/{'ab' * 32}"


def test_knack_console_serves_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    from knack.cli import main as knack_main
    from knack.console import app

    served: list[bool] = []
    monkeypatch.setattr(app, "serve", lambda: served.append(True))
    assert knack_main(["console"]) == 0 and served == [True]


def test_the_registry_env_wins_for_every_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from knack.console.verdict import home_registry_for

    monkeypatch.setenv("KNACK_REGISTRY", str(tmp_path / "team.json"))
    assert home_registry_for(REPO) == (tmp_path / "team.json").resolve()


def test_without_the_env_the_repos_home_registry_is_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from knack.console.verdict import home_registry_for

    monkeypatch.delenv("KNACK_REGISTRY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert home_registry_for(REPO) is None
    home = tmp_path / ".knack" / "registries" / "apache-airflow"
    home.mkdir(parents=True)
    (home / "registry.json").write_text("{}")
    assert home_registry_for(REPO) == home / "registry.json"


def get_rulings(world: World, receipt_hash: str) -> Any:
    response = world.client().get(f"/verdict/{receipt_hash}/rulings")
    assert response.headers["content-type"] == "application/json"
    return response


def test_a_denys_rulings_are_listed_in_the_order_argued(world: World) -> None:
    denied = world.receipt(deny(), at(5))
    world.ruling(denied, "Alias it.")
    world.ruling(denied, "A pinned client needs it.", "escalate")
    response = get_rulings(world, denied.hash)
    assert response.status_code == 200
    first, second = response.json()
    assert first == {
        "time": at(7),
        "receipt_hash": denied.hash,
        "objection": "Alias it.",
        "decision": "hold",
        "reply": "The quote answers this.",
        "cited_quotes": [QUOTE],
        "model": "muse-spark-1.3",
    }
    assert (second["objection"], second["decision"]) == (
        "A pinned client needs it.",
        "escalate",
    )


def test_rulings_on_another_deny_are_left_out(world: World) -> None:
    denied = world.receipt(deny(), at(5))
    other = world.receipt(deny('"start_date"'), at(6))
    world.ruling(other, "Not about this deny.")
    world.ruling(denied, "About this deny.")
    found = get_rulings(world, denied.hash).json()
    assert [r["objection"] for r in found] == ["About this deny."]


def test_a_receipt_never_argued_has_no_rulings(world: World) -> None:
    denied = world.receipt(deny(), at(5))
    response = get_rulings(world, denied.hash)
    assert (response.status_code, response.json()) == (200, [])


def test_rulings_for_an_unknown_hash_is_404(world: World) -> None:
    denied = world.receipt(deny(), at(5))
    world.ruling(denied, "Alias it.")
    response = get_rulings(world, "a" * 64)
    assert response.status_code == 404
    assert response.json() == {"detail": "no receipt with that hash"}


def test_a_ruling_made_after_start_is_found(world: World) -> None:
    denied = world.receipt(deny(), at(5))
    client = world.client()
    assert client.get(f"/verdict/{denied.hash}/rulings").json() == []
    world.ruling(denied, "Alias it.")
    assert len(client.get(f"/verdict/{denied.hash}/rulings").json()) == 1
