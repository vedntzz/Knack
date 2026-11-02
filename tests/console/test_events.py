import json
import shutil
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from knack.console.app import console_receipts, create_app
from knack.receipts.chain import receipts_path

FIXTURE = Path(__file__).parents[1] / "fixtures" / "console_75025" / "verdicts.jsonl"
# The fixture's allow is line 1 and its deny line 2.
ALLOW_LINE, DENY_LINE = FIXTURE.read_text().splitlines()
DENY = json.loads(DENY_LINE)["hash"]
POLL = 0.02


def client(receipts: Path) -> TestClient:
    base = receipts.parent
    places = (receipts, base / "warns.jsonl", base / "rulings.jsonl")
    return TestClient(create_app(*places, lambda repo: None, poll_seconds=POLL))


def later(write: Callable[[], None]) -> threading.Thread:
    # Runs after the stream has opened, the way the guard writes mid-session.
    writer = threading.Thread(target=lambda: (time.sleep(0.2), write()))
    writer.start()
    return writer


def append_later(path: Path, *lines: str) -> threading.Thread:
    def append() -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.writelines(line + "\n" for line in lines)

    return later(append)


def replace_later(path: Path, text: str) -> threading.Thread:
    def replace() -> None:
        path.write_text(text, encoding="utf-8")

    return later(replace)


def first_event(receipts: Path) -> tuple[str, str]:
    # The first named event on GET /events: its name and its data.
    with client(receipts).stream("GET", "/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        return named_event(response.iter_lines())


def named_event(lines: Iterator[str]) -> tuple[str, str]:
    named = ""
    for line in lines:
        named = line[7:] if line.startswith("event: ") else named
        if line.startswith("data: ") and named:
            return named, line[6:]
    raise AssertionError("the stream ended without an event")


def test_a_deny_appended_after_connecting_is_sent_by_its_hash(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    receipts.write_text(ALLOW_LINE + "\n")
    writer = append_later(receipts, DENY_LINE)
    assert first_event(receipts) == ("deny", DENY)
    writer.join()


def test_allows_and_denies_already_on_file_are_not_sent(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    shutil.copy(FIXTURE, receipts)
    later = json.loads(DENY_LINE) | {"hash": "f" * 64}
    writer = append_later(receipts, ALLOW_LINE, json.dumps(later))
    assert first_event(receipts) == ("deny", "f" * 64)
    writer.join()


def test_a_file_replaced_by_a_new_run_sends_its_new_deny(tmp_path: Path) -> None:
    # scripts/demo_block.sh copies each run's receipts over the last run's.
    receipts = tmp_path / "verdicts.jsonl"
    shutil.copy(FIXTURE, receipts)
    rerun = json.dumps(json.loads(DENY_LINE) | {"hash": "e" * 64})
    writer = replace_later(receipts, f"{ALLOW_LINE}\n{rerun}\n")
    assert first_event(receipts) == ("deny", "e" * 64)
    writer.join()


def test_a_missing_receipts_file_waits_instead_of_failing(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    writer = append_later(receipts, DENY_LINE)
    assert first_event(receipts) == ("deny", DENY)
    writer.join()


def test_the_home_page_waits_quietly_on_the_event_stream(tmp_path: Path) -> None:
    response = client(tmp_path / "verdicts.jsonl").get(
        "/", headers={"accept": "text/html"}
    )
    assert response.status_code == 200
    assert 'data-events="/events"' in response.text
    assert "Waiting for the next block." in response.text


def test_the_console_tails_the_receipts_file_it_is_pointed_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kept = tmp_path / "demo_block.receipts.jsonl"
    monkeypatch.setenv("KNACK_CONSOLE_RECEIPTS", str(kept))
    assert console_receipts() == kept


def test_the_console_tails_the_guards_receipts_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KNACK_CONSOLE_RECEIPTS", raising=False)
    assert console_receipts() == receipts_path()


def test_an_uphold_receipt_is_not_sent_as_a_new_deny(tmp_path: Path) -> None:
    # A person's uphold records a deny, but it blocks nothing new.
    receipts = tmp_path / "verdicts.jsonl"
    receipts.write_text(ALLOW_LINE + "\n")
    resolution = {"of": DENY, "action": "uphold", "by": "maria", "reason": "stands"}
    upheld = json.loads(DENY_LINE) | {"hash": "a" * 64, "resolution": resolution}
    later = json.loads(DENY_LINE) | {"hash": "f" * 64}
    writer = append_later(receipts, json.dumps(upheld), json.dumps(later))
    assert first_event(receipts) == ("deny", "f" * 64)
    writer.join()


# The frozen one-story run: a block, its hold and escalate rulings, and the uphold.
STORY = Path(__file__).parents[2] / "mockups" / "fixtures" / "one_story"
STORY_LINES = (STORY / "receipts.jsonl").read_text().splitlines()
HOLD_LINE, ESCALATE_LINE = (STORY / "rulings.jsonl").read_text().splitlines()
UPHOLD_LINE = next(x for x in STORY_LINES if '"resolution"' in x)
BLOCK = json.loads(UPHOLD_LINE)["resolution"]["of"]
SENTINEL = "f" * 64
GAP = 0.15


def story_without_uphold(base: Path) -> Path:
    receipts = base / "verdicts.jsonl"
    receipts.write_text("".join(x + "\n" for x in STORY_LINES if x != UPHOLD_LINE))
    return receipts


def sentinel_deny() -> str:
    return json.dumps(json.loads(DENY_LINE) | {"hash": SENTINEL})


def appended_in_turn(*writes: tuple[Path, str]) -> threading.Thread:
    # Each line lands a few polls after the last, the way argue and resolve write.
    def append_each() -> None:
        for path, line in writes:
            time.sleep(GAP)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    return later(append_each)


def events_through_sentinel(receipts: Path) -> list[tuple[str, object]]:
    # Every named event up to the sentinel deny, which proves nothing else came between.
    sent: list[tuple[str, object]] = []
    with client(receipts).stream("GET", "/events") as response:
        lines = response.iter_lines()
        while not sent or sent[-1] != ("deny", SENTINEL):
            name, data = named_event(lines)
            sent.append((name, data if name == "deny" else json.loads(data)))
    return sent


def sent_after(receipts: Path, *writes: tuple[Path, str]) -> list[tuple[str, object]]:
    # Writes each line in turn, then the sentinel deny; every event sent before the sentinel.
    writer = appended_in_turn(*writes, (receipts, sentinel_deny()))
    sent = events_through_sentinel(receipts)
    writer.join()
    return sent[:-1]


def ruling_sent(decision: str) -> tuple[str, object]:
    return "ruling", {"block": BLOCK, "decision": decision}


def resolution_sent(action: str) -> tuple[str, object]:
    return "resolution", {"block": BLOCK, "action": action}


def settled(action: str) -> str:
    # The story's uphold receipt, rewritten as a person's allow or retire.
    upheld = json.loads(UPHOLD_LINE)
    resolution = upheld["resolution"] | {"action": action}
    return json.dumps(upheld | {"decision": "allow", "resolution": resolution})


def test_each_ruling_and_resolution_sends_exactly_one_event_in_order(
    tmp_path: Path,
) -> None:
    receipts, rulings = story_without_uphold(tmp_path), tmp_path / "rulings.jsonl"
    writes = ((rulings, HOLD_LINE), (rulings, ESCALATE_LINE), (receipts, UPHOLD_LINE))
    in_order = [ruling_sent("hold"), ruling_sent("escalate"), resolution_sent("uphold")]
    assert sent_after(receipts, *writes) == in_order


@pytest.mark.parametrize("action", ["allow", "retire"])
def test_an_allow_or_retire_is_sent_as_its_resolution(
    tmp_path: Path, action: str
) -> None:
    receipts = story_without_uphold(tmp_path)
    found = sent_after(receipts, (receipts, settled(action)))
    assert found == [resolution_sent(action)]


def test_rulings_and_resolutions_already_on_file_are_not_sent(tmp_path: Path) -> None:
    receipts = tmp_path / "verdicts.jsonl"
    receipts.write_text("".join(x + "\n" for x in STORY_LINES))
    rulings = tmp_path / "rulings.jsonl"
    rulings.write_text(HOLD_LINE + "\n")
    found = sent_after(receipts, (rulings, ESCALATE_LINE))
    assert found == [ruling_sent("escalate")]


def test_a_torn_ruling_line_is_skipped_not_sent(tmp_path: Path) -> None:
    receipts, rulings = story_without_uphold(tmp_path), tmp_path / "rulings.jsonl"
    assert sent_after(receipts, (rulings, HOLD_LINE[:40])) == []
