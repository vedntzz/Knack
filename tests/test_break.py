import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from knack import cli
from knack.console.app import create_app
from knack.console.events import all_news
from knack.dispute.rulings import append_ruling, load_rulings
from knack.guard.check import GUARD_ERROR_REASON
from knack.hooks import pretool_guard
from knack.hooks.pretool_guard import decide
from knack.miss.cases import ModelAnswer
from knack.miss.selfcheck import load_checks, SelfCheck
from knack.pipeline.clients import MissingCredentials, RefusedCredentials
from knack.receipts.chain import append_receipt, load_receipts, TAIL_BYTES, verify_chain
from knack.walk.registry import Registry
from knack.watch import hook
from knack.watch.credentials import key_path, watch_key
from tests.console.test_argue_held_pages import BLOCK, ESCALATE, HOLD, Story
from tests.console.test_verdict_page import HTML
from tests.dispute.test_rulings import record
from tests.hooks.test_pretool import (
    make_clone,
    make_registry,
    raise_error,
    violating_write_event,
)

REPO_ROOT = Path(__file__).parents[1]
REPAIRS = REPO_ROOT / "mockups" / "fixtures" / "self_repair"
MODEL_KEYS = ("MODEL_API_KEY", "BASETEN_API_KEY", "GITHUB_TOKEN")
RULED_PAGES = ("argue", "held")
# Unknown, prefix, overlong, traversal, NUL, quote, non-ASCII and encoded-slash names.
BAD_NAMES = (
    "0" * 64,
    BLOCK[:12],
    BLOCK + "0",
    "f" * 4096,
    "..%2F..%2Fetc%2Fpasswd",
    "%2e%2e",
    "%00",
    "%22%3E%3Cscript%3E",
    "%E2%80%A6",
    "%FF%FE",
    "a%2Fb",
)
ROUTES = (
    "/verdict/{}",
    "/verdict/{}/argue",
    "/verdict/{}/held",
    "/verdict/{}/rulings",
    "/recovery/{}",
)
TRACEBACK = "Traceback (most recent call last)"
# Built by concatenation so the secret scan never matches this file.
FAKE_KEY = "sk" + "-should-never-print"
Json = dict[str, Any]


def story_client(story: Story) -> TestClient:
    # The frozen one-story console, with a kept repair, that never re-raises a 500.
    places = (story.receipts, story.kept / "warns.jsonl", story.rulings)
    app = create_app(*places, lambda repo: story.registry, repairs=REPAIRS)
    return TestClient(app, raise_server_exceptions=False)


def assert_page(story: Story, path: str) -> str:
    response = story_client(story).get(path, headers=HTML)
    assert response.status_code == 200, response.text
    assert TRACEBACK not in response.text
    return response.text


def tamper(path: Path, wanted: str, old: str, new: str) -> int:
    # Rewrites one field of the wanted receipt in place, keeping its hash; its line number.
    lines = path.read_text().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines) if wanted in line[-80:])
    assert old in lines[at]
    lines[at] = lines[at].replace(old, new, 1)
    path.write_text("".join(lines))
    return at + 1


def no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in MODEL_KEYS:
        monkeypatch.delenv(name, raising=False)


def write_key(name: str, value: str, mode: int) -> Path:
    path = key_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    path.chmod(mode)
    return path


def empty_registry(directory: Path) -> Registry:
    (directory / "roots").mkdir(exist_ok=True)
    return Registry(repo="apache/airflow", roots_dir=directory / "roots", rules=[])


def run_hook_process(stdin: str, cwd: Path, registry: Path) -> Any:
    # The guard as Muse Code runs it, pointed at the given registry file.
    clean = {k: v for k, v in os.environ.items() if not k.startswith("KNACK_")}
    env = clean | {"KNACK_REGISTRY": str(registry), "HOME": os.environ["HOME"]}
    argv = [sys.executable, "-m", "knack.hooks.pretool"]
    return subprocess.run(
        argv, input=stdin.encode(), capture_output=True, cwd=cwd, env=env, timeout=60
    )


def crashed_decide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Json | None:
    monkeypatch.setattr(pretool_guard, "check_file", raise_error(RuntimeError("boom")))
    event = violating_write_event("new_dags.py", tmp_path)
    receipts = tmp_path / "verdicts.jsonl"
    return decide(event, make_registry(tmp_path), tmp_path / "log", receipts)


# Tampered receipt -> verify fails.


@pytest.mark.parametrize(
    "old,new",
    [('"decision":"deny"', '"decision":"allow"'), ('"repo":"', '"repo":"x')],
)
def test_a_tampered_receipt_fails_verify(
    tmp_path: Path, old: str, new: str, capsys: pytest.CaptureFixture[str]
) -> None:
    story = Story(tmp_path)
    at = tamper(story.receipts, BLOCK, old, new)
    report = verify_chain(story.receipts)
    assert (report.broken_line, report.problem) == (
        at,
        "hash does not match the record",
    )
    assert cli.main(["receipts", "verify", "--path", str(story.receipts)]) != 0


def test_a_deleted_receipt_fails_verify(tmp_path: Path) -> None:
    story = Story(tmp_path)
    lines = story.receipts.read_text().splitlines(keepends=True)
    story.receipts.write_text("".join(lines[:1] + lines[2:]))
    assert verify_chain(story.receipts).broken_line == 2


def test_a_torn_last_receipt_fails_verify(tmp_path: Path) -> None:
    story = Story(tmp_path)
    whole = story.receipts.read_text()
    story.receipts.write_text(whole + whole.splitlines()[0][:40])
    assert verify_chain(story.receipts).problem == "not a receipt"


# Corrupt rulings line -> argue and held still render, 200, no traceback.


@pytest.mark.parametrize("page", RULED_PAGES)
def test_a_torn_rulings_line_is_skipped(tmp_path: Path, page: str) -> None:
    story = Story(tmp_path)
    torn = json.dumps(ESCALATE)[:50]
    story.rulings.write_text(
        json.dumps(HOLD) + "\n" + json.dumps(ESCALATE) + "\n" + torn
    )
    assert_page(story, f"/verdict/{BLOCK}/{page}")


@pytest.mark.parametrize("page", RULED_PAGES)
@pytest.mark.parametrize(
    "garbage",
    ["{", "null", "[]", "42", '"text"', "{}", '{"receipt_hash": 1}', "\x00\x00"],
)
def test_a_garbage_rulings_line_is_skipped(
    tmp_path: Path, page: str, garbage: str
) -> None:
    story = Story(tmp_path)
    story.rulings.write_text(
        "\n".join([json.dumps(HOLD), garbage, json.dumps(ESCALATE)]) + "\n"
    )
    assert_page(story, f"/verdict/{BLOCK}/{page}")


@pytest.mark.parametrize("page", RULED_PAGES)
def test_a_rulings_line_torn_inside_a_utf8_character_is_skipped(
    tmp_path: Path, page: str
) -> None:
    # A write cut mid-character leaves bytes that are not UTF-8.
    story = Story(tmp_path)
    whole = (json.dumps(HOLD) + "\n" + json.dumps(ESCALATE) + "\n").encode()
    story.rulings.write_bytes(whole + '{"reply": "…'.encode()[:-1])
    assert_page(story, f"/verdict/{BLOCK}/{page}")


@pytest.mark.parametrize("page", RULED_PAGES)
def test_a_ruling_with_no_model_shows_a_labelled_gap(tmp_path: Path, page: str) -> None:
    story = Story(tmp_path)
    story.keep_rulings(HOLD | {"model": None}, ESCALATE | {"model": None})
    assert "Model not recorded" in assert_page(story, f"/verdict/{BLOCK}/{page}")


def test_a_corrupt_hold_leaves_held_showing_no_answer(tmp_path: Path) -> None:
    # The escalation survives a corrupt hold line; held still renders.
    story = Story(tmp_path)
    story.rulings.write_text("{corrupt\n" + json.dumps(ESCALATE) + "\n")
    assert_page(story, f"/verdict/{BLOCK}/held")


# Missing model keys -> a message naming the env var and the file, never the key.


@pytest.mark.parametrize("name", MODEL_KEYS)
def test_a_missing_key_names_its_env_var_and_its_file(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    no_keys(monkeypatch)
    with pytest.raises(MissingCredentials) as raised:
        watch_key(name)
    assert name in str(raised.value)
    assert str(key_path(name)) in str(raised.value)


@pytest.mark.parametrize("name", MODEL_KEYS)
def test_a_readable_key_file_is_refused_without_printing_the_key(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    no_keys(monkeypatch)
    path = write_key(name, FAKE_KEY, 0o644)
    with pytest.raises(RefusedCredentials) as raised:
        watch_key(name)
    assert str(path) in str(raised.value)
    assert FAKE_KEY not in str(raised.value)


def test_an_empty_key_file_names_its_env_var_and_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    no_keys(monkeypatch)
    path = write_key("MODEL_API_KEY", "  \n", 0o600)
    with pytest.raises(RefusedCredentials) as raised:
        watch_key("MODEL_API_KEY")
    assert "MODEL_API_KEY" in str(raised.value) and str(path) in str(raised.value)


def test_watch_without_keys_says_which_key_and_where_and_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    no_keys(monkeypatch)
    write_key("GITHUB_TOKEN", "ghp-placeholder", 0o600)
    with pytest.raises(MissingCredentials) as raised:
        hook._clients(False)()  # pyright: ignore[reportPrivateUsage]
    assert "MODEL_API_KEY" in str(raised.value)
    assert str(key_path("MODEL_API_KEY")) in str(raised.value)
    hook._report(raised.value, loud=True)  # pyright: ignore[reportPrivateUsage]
    err = capsys.readouterr().err
    assert "MODEL_API_KEY" in err and TRACEBACK not in err


# Empty registry -> the guard allows, nothing crashes.


def test_an_empty_registry_allows(tmp_path: Path) -> None:
    event = violating_write_event("new_dags.py", tmp_path)
    receipts = tmp_path / "verdicts.jsonl"
    log = tmp_path / "log"
    assert decide(event, empty_registry(tmp_path), log, receipts) is None
    assert not log.exists()
    assert load_receipts(receipts) == []


@pytest.mark.parametrize(
    "body",
    ["", "{}", "[]", '{"repo": "apache/airflow", "roots_dir": "r", "rules": []}'],
)
def test_an_empty_registry_file_allows_through_the_hook(
    tmp_path: Path, body: str
) -> None:
    clone = make_clone(tmp_path / "clone", "https://github.com/apache/airflow.git")
    registry = tmp_path / "registry.json"
    registry.write_text(body)
    event = violating_write_event("new_dags.py", clone)
    done = run_hook_process(json.dumps(event), clone, registry)
    assert (done.returncode, done.stdout) == (0, b"")
    assert TRACEBACK.encode() not in done.stderr


# Forced guard crash -> edit proceeds, error logged, guard-error receipt verifies.


def test_a_forced_guard_crash_lets_the_edit_proceed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert crashed_decide(tmp_path, monkeypatch) is None
    assert "RuntimeError: boom" in (tmp_path / "log").read_text()


def test_a_forced_guard_crash_receipt_says_guard_error_and_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crashed_decide(tmp_path, monkeypatch)
    receipts = tmp_path / "verdicts.jsonl"
    [receipt] = load_receipts(receipts)
    assert receipt.decision == GUARD_ERROR_REASON
    assert verify_chain(receipts).problem is None
    assert cli.main(["receipts", "verify", "--path", str(receipts)]) == 0


def test_a_crash_before_any_rule_runs_still_lets_the_edit_proceed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pretool_guard, "load_roots", raise_error(OSError("disk")))
    event = violating_write_event("new_dags.py", tmp_path)
    log = tmp_path / "log"
    assert decide(event, make_registry(tmp_path), log, tmp_path / "v.jsonl") is None
    assert "OSError: disk" in log.read_text()


def test_a_receipt_write_crash_keeps_the_deny(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Our receipt failing must never turn a Confirmed deny into an allow.
    monkeypatch.setattr(pretool_guard, "append_receipt", raise_error(OSError("full")))
    event = violating_write_event("new_dags.py", tmp_path)
    log = tmp_path / "log"
    result = decide(event, make_registry(tmp_path), log, tmp_path / "v.jsonl")
    assert result is not None
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "OSError: full" in log.read_text()


# Unknown hashes and malformed URLs on every console route -> 404, never 500.


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("name", BAD_NAMES)
@pytest.mark.parametrize("html", [True, False])
def test_a_bad_name_is_404_never_500(
    tmp_path: Path, route: str, name: str, html: bool
) -> None:
    client = story_client(Story(tmp_path))
    response = client.get(route.format(name), headers=HTML if html else {})
    assert response.status_code == 404, (route.format(name), response.text[:300])
    assert TRACEBACK not in response.text


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("html", [True, False])
def test_a_missing_receipts_file_is_404_never_500(
    tmp_path: Path, route: str, html: bool
) -> None:
    story = Story(tmp_path)
    story.receipts.unlink()
    response = story_client(story).get(
        route.format(BLOCK), headers=HTML if html else {}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("route", ROUTES[:4])
def test_a_receipt_torn_inside_a_utf8_character_is_never_500(
    tmp_path: Path, route: str
) -> None:
    # The hook was cut mid-write; the console still finds the receipts before it.
    story = Story(tmp_path)
    story.receipts.write_bytes(story.receipts.read_bytes() + '{"file":"…'.encode()[:-1])
    response = story_client(story).get(route.format(BLOCK), headers=HTML)
    assert response.status_code != 500, response.text[:300]


def test_a_recovery_run_missing_its_files_is_404_never_500(tmp_path: Path) -> None:
    broken = tmp_path / "self_repair"
    shutil.copytree(REPAIRS, broken)
    shutil.rmtree(broken / "rule")
    story = Story(tmp_path / "s")
    places = (story.receipts, story.kept / "warns.jsonl", story.rulings)
    app = create_app(*places, lambda repo: story.registry, repairs=broken)
    client = TestClient(app, raise_server_exceptions=False)
    rule = json.loads(next((REPAIRS / "cases").glob("*.json")).read_text())["rule_id"]
    assert client.get(f"/recovery/{rule}", headers=HTML).status_code == 404


# A receipt torn mid-character: the guard keeps receipting; verify names the line.

TORN_TAIL = '{"file":"…'.encode()[:-1]


def torn_receipts(tmp_path: Path) -> Path:
    # One whole guard receipt, then a write cut inside a UTF-8 character.
    receipts = tmp_path / "verdicts.jsonl"
    event = violating_write_event("new_dags.py", tmp_path)
    decide(event, make_registry(tmp_path), tmp_path / "log", receipts)
    receipts.write_bytes(receipts.read_bytes() + TORN_TAIL)
    return receipts


def test_a_deny_after_a_torn_last_line_is_still_receipted(tmp_path: Path) -> None:
    receipts = torn_receipts(tmp_path)
    event = violating_write_event("new_dags.py", tmp_path)
    result = decide(event, make_registry(tmp_path), tmp_path / "log", receipts)
    [first, second] = load_receipts(receipts)
    assert second.decision == "deny" and second.prev == first.hash
    assert result is not None and second.hash in str(result)


def test_verify_names_the_torn_line_not_a_codec_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    receipts = torn_receipts(tmp_path)
    event = violating_write_event("new_dags.py", tmp_path)
    decide(event, make_registry(tmp_path), tmp_path / "log", receipts)
    report = verify_chain(receipts)
    assert (report.receipts, report.broken_line) == (1, 2)
    assert report.problem == "not a receipt"
    assert cli.main(["receipts", "verify", "--path", str(receipts)]) != 0
    assert "codec" not in capsys.readouterr().err


def test_the_event_stream_skips_a_line_torn_inside_a_utf8_character(
    tmp_path: Path,
) -> None:
    story = Story(tmp_path)
    for path in (story.receipts, story.rulings):
        path.write_bytes(path.read_bytes() + TORN_TAIL)
    found = all_news(story.receipts, story.rulings)
    assert BLOCK in [key for key, _ in found]


def test_a_receipt_longer_than_the_tail_never_stops_the_next_one(
    tmp_path: Path,
) -> None:
    # A module-wide match can make one receipt outgrow the 64 KiB tail read.
    receipts = tmp_path / "verdicts.jsonl"
    base: Json = {"time": "t", "repo": "r", "file": "/x.py", "rule_id": "r1"}
    base |= {"root_ids": [], "decision": "deny", "quote_sha256": None}
    base |= {"latency_ms": 1.0}
    big = base | {"matched": [{"line": 1, "text": "x" * (TAIL_BYTES + 1)}]}
    first = append_receipt(receipts, big)
    second = append_receipt(receipts, base)
    assert second.prev == first.hash
    assert verify_chain(receipts).problem is None


# Leftovers from the review: torn self-checks, a ruling after a torn tail, an early crash.


def a_self_check() -> SelfCheck:
    answer = ModelAnswer(model="m", yes=False, answer="no", prompt_sha256="0" * 64)
    fields: Json = {"time": "t", "trigger": "watch", "question": "q", "rule_id": "r"}
    fields |= {"source": "s", "file": "a.py", "answers": [answer], "case_key": None}
    return SelfCheck.model_validate(fields)


def test_a_self_checks_line_torn_inside_a_utf8_character_is_skipped(
    tmp_path: Path,
) -> None:
    checks = tmp_path / "self_checks.jsonl"
    whole = a_self_check()
    checks.write_bytes((whole.model_dump_json() + "\n").encode() + TORN_TAIL)
    assert load_checks(checks) == [whole]


def test_a_ruling_after_a_torn_tail_starts_a_line_of_its_own(tmp_path: Path) -> None:
    rulings = tmp_path / "rulings.jsonl"
    rulings.write_bytes(TORN_TAIL)
    kept = record()
    append_ruling(rulings, kept)
    append_ruling(rulings, kept)
    assert load_rulings(rulings) == [kept, kept]


def test_a_crash_before_any_rule_runs_still_writes_a_guard_error_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pretool_guard, "load_roots", raise_error(OSError("disk")))
    event = violating_write_event("new_dags.py", tmp_path)
    receipts = tmp_path / "verdicts.jsonl"
    assert decide(event, make_registry(tmp_path), tmp_path / "log", receipts) is None
    [receipt] = load_receipts(receipts)
    assert receipt.decision == GUARD_ERROR_REASON
    assert receipt.file == str(tmp_path / "new_dags.py")
    assert verify_chain(receipts).problem is None


def test_a_crash_with_no_readable_target_still_writes_a_guard_error_receipt(
    tmp_path: Path,
) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    event: Json = {"tool_name": "write_file", "cwd": str(tmp_path)}
    assert decide(event, make_registry(tmp_path), tmp_path / "log", receipts) is None
    [receipt] = load_receipts(receipts)
    assert receipt.decision == GUARD_ERROR_REASON


def test_a_crash_with_no_receipts_kept_writes_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pretool_guard, "load_roots", raise_error(OSError("disk")))
    event = violating_write_event("new_dags.py", tmp_path)
    assert decide(event, make_registry(tmp_path), tmp_path / "log", None) is None
    assert list(tmp_path.glob("*.jsonl")) == []
