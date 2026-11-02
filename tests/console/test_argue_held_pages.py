import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from knack.console import app
from knack.console.app import create_app, RECEIPTS_ENV
from tests.console.test_verdict_page import HTML, QUOTE, visible

REPO_ROOT = Path(__file__).parents[2]
# The frozen one-story run: block, hold, escalate (Spark and Spark Open), uphold.
FROZEN = REPO_ROOT / "mockups" / "fixtures" / "one_story"
DATA_REGISTRY = REPO_ROOT / "data" / "registry" / "airflow.json"
DATA_ROOTS = REPO_ROOT / "data" / "roots" / "airflow"
BLOCK = "0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9"
UPHOLD = "ff61cef704607eef0105368f9ad68aa63cc425050c9e53e3c8d561dfff01fc41"
ALLOW = "5636f0a41b5949d75e3267078cd96dcb60ad03a9ebb77bddca5fef33e7db58da"
SPARK = ("muse-spark-1.3", "api.meta.ai")
SPARK_OPEN = ("meta-models/muse-spark-open-1026", "inference.baseten.co")
# Spark Open's own reply, verbatim from the self-check it answered.
SPARK_OPEN_REPLY = (
    "The quotes do not discuss a deprecation cycle for documented public REST API "
    "order_by values or the constraint of removing them in a minor release. "
    "A person will decide."
)
Json = dict[str, Any]


def frozen_rulings() -> list[Json]:
    lines = (FROZEN / "rulings.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


HOLD, ESCALATE = frozen_rulings()


def ticks_dropped(text: str) -> str:
    # Backticked spans render as code, so the visible text has no backticks.
    return text.replace("`", "")


class Story:
    # The frozen run copied into a temporary kept-receipts folder, and the airflow registry.
    def __init__(self, base: Path) -> None:
        self.kept = base / "kept"
        shutil.copytree(FROZEN, self.kept)
        self.receipts = self.kept / "receipts.jsonl"
        self.rulings = self.kept / "rulings.jsonl"
        shutil.copytree(DATA_ROOTS, base / "roots")
        self.registry = base / "registry.json"
        self.registry.write_text(json.dumps(registry_body(base / "roots")))

    def client(self) -> TestClient:
        places = (self.receipts, self.kept / "warns.jsonl", self.rulings)
        return TestClient(create_app(*places, lambda repo: self.registry))

    def get(self, path: str) -> str:
        response = self.client().get(path, headers=HTML)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/html")
        return response.text

    def keep_rulings(self, *kept: Json) -> None:
        self.rulings.write_text("".join(json.dumps(r) + "\n" for r in kept))

    def drop_receipt(self, wanted: str) -> None:
        lines = self.receipts.read_text().splitlines(keepends=True)
        self.receipts.write_text("".join(x for x in lines if wanted not in x[-80:]))


def registry_body(roots: Path) -> Json:
    data: Json = json.loads(DATA_REGISTRY.read_text())
    rules = [
        e | {"rule": str((DATA_REGISTRY.parent / e["rule"]).resolve())}
        for e in data["rules"]
    ]
    return data | {"roots_dir": str(roots), "rules": rules}


def section(html: str, label: str) -> str:
    # The visible text of the section labelled by the heading with this id.
    found = re.search(
        rf'<section[^>]*aria-labelledby="{label}".*?</section>', html, re.S
    )
    assert found, label
    return visible(found.group(0))


@pytest.fixture
def story(tmp_path: Path) -> Story:
    return Story(tmp_path)


def test_the_argue_page_shows_the_lines_the_note_the_objection_and_the_hold(
    story: Story,
) -> None:
    text = visible(story.get(f"/verdict/{BLOCK}/argue"))
    for line in ('"state": DagRun.state,', '"start_date": DagRun.start_date,'):
        assert line in text
    assert QUOTE in text
    assert "Pushkal Gupta" in text and "#75025" in text
    assert f"The agent, {HOLD['agent']}, objected" in text
    assert HOLD["objection"] in text
    assert ticks_dropped(HOLD["cited_quotes"][0]) in text
    assert ticks_dropped(HOLD["reply"]) in text
    assert "Hold" in text and "Lines 135–136 stay blocked." in text


def test_the_argue_page_names_exactly_the_models_on_the_hold_ruling(
    story: Story,
) -> None:
    answered = section(story.get(f"/verdict/{BLOCK}/argue"), "by")
    assert f"{SPARK[0]} at {SPARK[1]}" in answered
    assert SPARK_OPEN[0] not in answered and SPARK_OPEN[1] not in answered
    assert "The block itself ran no model: 17.3 ms to decide." in answered


def test_the_held_page_shows_the_escalation_both_models_and_spark_opens_answer(
    story: Story,
) -> None:
    html = story.get(f"/verdict/{BLOCK}/held")
    text = visible(html)
    assert ESCALATE["objection"] in text and ESCALATE["reply"] in text
    assert SPARK_OPEN_REPLY in text
    answered = section(html, "by")
    for model, host in (SPARK, SPARK_OPEN):
        assert f"{model} at {host}" in answered
    assert answered.index(SPARK[0]) < answered.index(SPARK_OPEN[0])


def test_the_held_page_shows_the_uphold_by_reason_and_time(story: Story) -> None:
    html = story.get(f"/verdict/{BLOCK}/held")
    assert "<h1>A person upheld the decision.</h1>" in html
    resolved = section(html, "resolved")
    assert "Upheld by Vedant Srivastava" in resolved
    assert "these two sort options never worked (they returned an error)" in resolved
    assert "Nov 2 2026, 14:45:07 UTC" in resolved
    assert "knack resolve" not in resolved


def test_an_unresolved_held_case_shows_the_three_resolve_commands(
    story: Story,
) -> None:
    story.drop_receipt(UPHOLD)
    html = story.get(f"/verdict/{BLOCK}/held")
    assert "<h1>Held for a person.</h1>" in html
    decide = section(html, "decide")
    assert "A human runs this" in decide
    assert f'knack resolve {BLOCK} allow|retire|uphold --reason "<why>"' in decide
    for action in ("allow", "retire", "uphold"):
        command = f"knack resolve {BLOCK} {action} --reason &quot;&lt;why&gt;&quot;"
        assert f'data-copy-text="{command}"' in html
        assert f"Copy {action}" in decide
    assert "Upheld by" not in visible(html)


def test_block_links_to_argue_and_argue_links_to_held(story: Story) -> None:
    assert f'href="/verdict/{BLOCK}/argue"' in story.get(f"/verdict/{BLOCK}")
    assert f'href="/verdict/{BLOCK}/held"' in story.get(f"/verdict/{BLOCK}/argue")
    assert f'href="/verdict/{BLOCK}/argue"' in story.get(f"/verdict/{BLOCK}/held")


def test_argue_says_the_later_held_objection_was_resolved(story: Story) -> None:
    text = visible(story.get(f"/verdict/{BLOCK}/argue"))
    assert "A later objection was held for a person, who upheld it." in text


def test_argue_ends_on_the_fix(story: Story) -> None:
    fix = section(story.get(f"/verdict/{BLOCK}/argue"), "fix")
    assert "Delete lines 135–136." in fix
    assert "Lines 137–138 already use the right names." in fix


def test_held_links_back_to_what_the_record_answered(story: Story) -> None:
    html = story.get(f"/verdict/{BLOCK}/held")
    assert f'<a href="/verdict/{BLOCK}/argue">What the record answered</a>' in html


def test_argue_does_not_link_to_held_when_the_latest_ruling_held(
    story: Story,
) -> None:
    story.keep_rulings(ESCALATE, HOLD)
    assert "/held" not in story.get(f"/verdict/{BLOCK}/argue")


def test_a_deny_never_argued_has_no_argue_link(story: Story) -> None:
    story.keep_rulings()
    assert f"/verdict/{BLOCK}/argue" not in story.get(f"/verdict/{BLOCK}")


@pytest.mark.parametrize("page", ["argue", "held"])
def test_an_unknown_hash_is_the_404_page(story: Story, page: str) -> None:
    response = story.client().get(f"/verdict/{'0' * 64}/{page}", headers=HTML)
    assert response.status_code == 404
    assert "No receipt with that hash." in visible(response.text)


@pytest.mark.parametrize("kept,page", [((), "argue"), ((), "held"), ((HOLD,), "held")])
def test_no_ruling_of_that_kind_is_the_404_page(
    story: Story, kept: tuple[Json, ...], page: str
) -> None:
    story.keep_rulings(*kept)
    response = story.client().get(f"/verdict/{BLOCK}/{page}", headers=HTML)
    assert response.status_code == 404
    assert "No ruling on that receipt." in visible(response.text)


def test_an_allow_receipt_has_no_argue_page(story: Story) -> None:
    response = story.client().get(f"/verdict/{ALLOW}/argue", headers=HTML)
    assert response.status_code == 404


def test_a_ruling_without_an_agent_says_so(story: Story) -> None:
    story.keep_rulings({k: v for k, v in HOLD.items() if k != "agent"})
    text = visible(story.get(f"/verdict/{BLOCK}/argue"))
    assert "Agent not recorded" in text


def test_a_missing_self_check_leaves_spark_opens_answer_a_gap(story: Story) -> None:
    (story.kept / "traces" / "self_checks.jsonl").unlink()
    text = visible(story.get(f"/verdict/{BLOCK}/held"))
    assert f"{SPARK_OPEN[0]}’s answer not recorded" in text
    assert SPARK_OPEN_REPLY not in text


def test_ruling_text_is_escaped_never_run(story: Story) -> None:
    story.keep_rulings(HOLD | {"objection": "<script>alert(1)</script>"})
    html = story.get(f"/verdict/{BLOCK}/argue")
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html


def test_kept_receipts_bring_their_rulings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RECEIPTS_ENV, str(tmp_path / "receipts.jsonl"))
    assert getattr(app, "console_rulings")() == tmp_path / "rulings.jsonl"
