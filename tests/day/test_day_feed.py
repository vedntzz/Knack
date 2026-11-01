import json
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

import pytest
from day_world import (
    allow_verdict,
    BRANCH,
    DayWorld,
    deny_verdict,
    FakePulls,
    pull,
    REPO,
    TODAY,
    YESTERDAY,
)
from knack.cli import main
from knack.day.feed import day_feed, day_json


def events(world: DayWorld, kind: str) -> list[dict[str, Any]]:
    feed = json.loads(day_json(world.day()))
    return [e for e in feed["events"] if e["type"] == kind]


def test_feed_names_the_repo_branch_and_day(world: DayWorld) -> None:
    feed = day_feed(world.day())
    assert (feed.repo, feed.branch, feed.date) == (REPO, BRANCH, "2026-11-01")


def test_todays_commits_on_the_branch_with_first_message_line(world: DayWorld) -> None:
    world.commit("old work", date=YESTERDAY)
    sha = world.commit("Drop alias sort keys\n\nLong body.")
    expected = {"type": "commit", "sha": sha, "author": "Dana Lee"}
    expected |= {"message": "Drop alias sort keys", "time": "2026-11-01T09:00:00Z"}
    assert events(world, "commit") == [expected]


def test_open_and_merged_prs_today_and_nothing_else(world: DayWorld) -> None:
    world.pulls = FakePulls(
        [
            pull(7, "open", TODAY),
            pull(8, "closed", YESTERDAY, merged="2026-11-01T10:00:00Z"),
            pull(9, "closed", TODAY),
            pull(10, "open", YESTERDAY),
            pull(7, "open", TODAY),
        ]
    )
    found = [(e["number"], e["state"], e["time"]) for e in events(world, "pr")]
    assert found == [(7, "open", TODAY), (8, "merged", "2026-11-01T10:00:00Z")]


def test_prs_are_asked_for_this_repo_and_branch(world: DayWorld) -> None:
    pulls = FakePulls([])
    world.pulls = pulls
    day_feed(world.day())
    assert pulls.asked == [(REPO, BRANCH)]


def test_no_github_token_says_so_and_lists_no_prs(world: DayWorld) -> None:
    world.pulls = None
    feed = day_feed(world.day())
    assert feed.pulls_error == "GITHUB_TOKEN is not set"
    assert [e for e in feed.events if e.type == "pr"] == []


def test_unreachable_github_is_reported_never_raised(world: DayWorld) -> None:
    world.pulls = FakePulls(OSError("network down"))
    feed = day_feed(world.day())
    assert feed.pulls_error == "GitHub unreachable: network down"


def test_todays_deny_is_a_block_citing_root_and_decider(world: DayWorld) -> None:
    deny = world.receipt(deny_verdict())
    expected = {"type": "receipt", "kind": "block", "time": TODAY}
    expected |= {"root_id": "root-41", "decider": "maria", "receipt_hash": deny.hash}
    assert events(world, "receipt") == [expected]


def test_other_days_repos_allows_and_guard_errors_are_left_out(world: DayWorld) -> None:
    world.receipt(deny_verdict(), time=YESTERDAY)
    world.receipt(deny_verdict(), repo="other/repo")
    world.receipt(allow_verdict())
    world.receipt(allow_verdict("guard-error: boom"))
    assert events(world, "receipt") == []


def test_a_resolve_allow_is_learn_with_its_own_hash(world: DayWorld) -> None:
    deny = world.receipt(deny_verdict(), time=YESTERDAY)
    allow = world.resolve(deny)
    [learn] = events(world, "receipt")
    assert (learn["kind"], learn["receipt_hash"]) == ("learn", allow.hash)
    assert (learn["root_id"], learn["decider"]) == ("root-41", "maria")


def test_a_warn_today_in_this_repo_has_no_hash(world: DayWorld) -> None:
    world.warn()
    world.warn(time=YESTERDAY)
    world.warn(repo="other/repo")
    expected = {"type": "receipt", "kind": "warn", "time": TODAY}
    expected |= {"root_id": None, "decider": None, "receipt_hash": None}
    assert events(world, "receipt") == [expected]


def test_hold_is_held_and_escalate_is_argue_citing_the_deny(world: DayWorld) -> None:
    deny = world.receipt(deny_verdict(), time=YESTERDAY)
    world.ruling(deny, "hold", time="2026-11-01T10:00:00+00:00")
    world.ruling(deny, "escalate", time="2026-11-01T11:00:00+00:00")
    found = [
        (e["kind"], e["root_id"], e["receipt_hash"]) for e in events(world, "receipt")
    ]
    assert found == [("held", "root-41", deny.hash), ("argue", "root-41", deny.hash)]


def test_a_ruling_on_another_repos_deny_is_left_out(world: DayWorld) -> None:
    deny = world.receipt(deny_verdict(), repo="other/repo", time=YESTERDAY)
    world.ruling(deny, "hold")
    assert events(world, "receipt") == []


def test_unreadable_registry_leaves_decider_unknown(world: DayWorld) -> None:
    world.registry.write_text("{not json")
    world.receipt(deny_verdict())
    [block] = events(world, "receipt")
    assert (block["root_id"], block["decider"]) == ("root-41", None)


def test_events_of_every_type_come_newest_last(world: DayWorld) -> None:
    world.pulls = FakePulls([pull(7, "open", "2026-11-01T12:00:00Z")])
    world.receipt(deny_verdict(), time="2026-11-01T14:00:00+00:00")
    world.commit("first", date="2026-11-01T08:00:00+00:00")
    world.warn(time="2026-11-01T10:00:00+00:00")
    order = [e["type"] for e in json.loads(day_json(world.day()))["events"]]
    assert order == ["commit", "receipt", "pr", "receipt"]


def test_outside_git_the_feed_is_empty_not_an_error(
    world: DayWorld, tmp_path: Path
) -> None:
    world.clone = tmp_path / "not-a-repo"
    world.clone.mkdir()
    feed = day_feed(world.day())
    assert (feed.repo, feed.branch, feed.events) == (None, None, [])


def tree(folder: Path) -> dict[str, bytes]:
    return {str(p): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def test_cli_prints_the_feed_and_writes_nothing(
    world: DayWorld, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The CLI reads the real clock, so its events are stamped now.
    now = datetime.now(UTC).replace(microsecond=0)
    deny = world.receipt(deny_verdict(), time=(now - timedelta(minutes=1)).isoformat())
    world.commit("Drop alias sort keys", date=now.isoformat())
    monkeypatch.setenv("HOME", str(world.home.parent))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    monkeypatch.setenv("KNACK_REGISTRY", str(world.registry))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.chdir(world.clone)
    before = tree(world.home.parent) | tree(world.registry.parent)
    assert main(["day", "--json"]) == 0
    feed = json.loads(capsys.readouterr().out)
    assert [e.get("receipt_hash") for e in feed["events"]] == [deny.hash, None]
    assert tree(world.home.parent) | tree(world.registry.parent) == before


def test_cli_day_requires_json(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        main(["day"])
    assert exited.value.code == 2
