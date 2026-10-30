import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from knack import cli
from knack.bench.attempts import Attempt, attempt_fields, replay_attempts
from knack.bench.reclassify import reclassify
from knack.bench.report import load_runs
from knack.bench.run import RunRecord
from knack.contracts.models import Root
from knack.roots.store import write_root
from knack.walk.registry import Registry, RegistryEntry

RULE = "id: widgets-9\nlanguage: python\nseverity: error\nmessage: m\nrule:\n  pattern: asyncio.gather($$$)\n"
LOADER = "import asyncio\n\n\nasync def load(items):\n    return [await i.read() for i in items]\n"
LEGACY = "import asyncio\n\n\nasync def old(items):\n    return await asyncio.gather(*items)\n"
CLEAN_BODY = "return [await i.read() for i in items]"
GATHER_BODY = "return await asyncio.gather(*[i.read() for i in items])"
GATHER = "asyncio.gather(*[i.read() for i in items])"
BLOCKED = "tool blocked by hook: Knack blocked this edit.\nDecision: d"


def sandbox_with_base(tmp_path: Path) -> Path:
    # A repo whose first commit is the base, like a bench sandbox.
    sandbox = tmp_path / "sandbox"
    (sandbox / "src").mkdir(parents=True)
    (sandbox / "src/loader.py").write_text(LOADER)
    (sandbox / "src/legacy.py").write_text(LEGACY)
    git = ["git", "-C", str(sandbox), "-c", "user.name=d", "-c", "user.email=d@x"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True)
    return sandbox


def rule_file(tmp_path: Path) -> Path:
    path = tmp_path / "rule.yml"
    path.write_text(RULE)
    return path


def run_event(event: dict[str, Any]) -> dict[str, Any]:
    # The shape Muse exports for a session run event.
    return {"kind": "record", "envelope": {"payload": {"kind": "run", "event": event}}}


def call(call_id: str, name: str, **args: str) -> dict[str, Any]:
    tool_call = {"call_id": call_id, "name": name, "args": json.dumps(args)}
    return run_event(
        {"kind": "assistant_tool_calls_committed", "tool_calls": [tool_call]}
    )


def result(call_id: str, text: str) -> dict[str, Any]:
    found = {"tool_call_index": 0, "tool_call_id": call_id, "text": text}
    return run_event({"kind": "tool_result_batch_committed", "results": [found]})


def edit(
    call_id: str, find: str, replace: str, path: str = "src/loader.py"
) -> list[dict[str, Any]]:
    edited = call(call_id, "edit_file", path=path, find=find, replace=replace)
    return [edited, result(call_id, "edited")]


def replay(tmp_path: Path, events: list[Any]) -> list[Attempt]:
    export = {"export_schema_version": 1, "events": events}
    return replay_attempts(export, sandbox_with_base(tmp_path), rule_file(tmp_path))


def test_edit_introducing_a_rule_match_is_an_attempt(tmp_path: Path) -> None:
    attempts = replay(tmp_path, edit("c1", CLEAN_BODY, GATHER_BODY))
    assert attempts == [Attempt(tool="edit_file", path="src/loader.py", matched=GATHER)]


def test_write_introducing_a_rule_match_is_an_attempt(tmp_path: Path) -> None:
    written = call(
        "c1",
        "write_file",
        path="src/loader.py",
        content=LOADER.replace(CLEAN_BODY, GATHER_BODY),
    )
    attempts = replay(tmp_path, [written, result("c1", "wrote 90 bytes")])
    assert [(a.tool, a.matched) for a in attempts] == [("write_file", GATHER)]


def test_clean_edits_are_not_attempts(tmp_path: Path) -> None:
    assert replay(tmp_path, edit("c1", "def load", "def load_all")) == []


def test_a_match_already_in_the_base_is_not_an_attempt(tmp_path: Path) -> None:
    # legacy.py already matches; editing around it keeps that match but adds none.
    events = edit("c1", "def old", "def older", path="src/legacy.py")
    assert replay(tmp_path, events) == []


def test_a_blocked_attempt_counts_but_leaves_the_file_unchanged(tmp_path: Path) -> None:
    # Blocked, then retried and allowed: two attempts; a later edit adds none.
    blocked = [
        call(
            "c1",
            "edit_file",
            path="src/loader.py",
            find=CLEAN_BODY,
            replace=GATHER_BODY,
        ),
        result("c1", BLOCKED),
    ]
    retried = edit("c2", CLEAN_BODY, GATHER_BODY)
    later = edit("c3", "def load", "def load_all")
    assert len(replay(tmp_path, [*blocked, *retried, *later])) == 2


def test_edits_replay_in_order_on_the_same_file(tmp_path: Path) -> None:
    # The second edit only finds text the first one wrote.
    first = edit("c1", CLEAN_BODY, "return step(items)")
    second = edit("c2", "return step(items)", GATHER_BODY)
    assert [a.matched for a in replay(tmp_path, [*first, *second])] == [GATHER]


def test_an_absolute_path_in_the_sandbox_reads_as_the_same_file(tmp_path: Path) -> None:
    absolute = str((tmp_path / "sandbox/src/loader.py").resolve())
    attempts = replay(tmp_path, edit("c1", CLEAN_BODY, GATHER_BODY, path=absolute))
    assert [a.path for a in attempts] == ["src/loader.py"]


def test_a_write_outside_the_sandbox_still_counts(tmp_path: Path) -> None:
    # The guard checks any .py proposal, scratch scripts included.
    outside = str(tmp_path / "repro.py")
    written = call("c1", "write_file", path=outside, content=LEGACY)
    attempts = replay(tmp_path, [written, result("c1", "wrote 70 bytes")])
    assert [a.path for a in attempts] == [outside]


def test_non_python_writes_are_skipped(tmp_path: Path) -> None:
    written = call("c1", "write_file", path="notes.md", content=LEGACY)
    assert replay(tmp_path, [written, result("c1", "wrote 70 bytes")]) == []


def test_other_tools_and_events_are_ignored(tmp_path: Path) -> None:
    events = [
        call("c1", "bash", command="echo asyncio.gather()"),
        {"kind": "record"},
        "junk",
    ]
    assert replay(tmp_path, events) == []


def test_attempt_fields_say_none_when_not_replayed() -> None:
    assert attempt_fields(None) == {"attempted": None, "attempts": []}
    assert attempt_fields([]) == {"attempted": False, "attempts": []}
    found = [Attempt(tool="edit_file", path="a.py", matched="x")]
    assert attempt_fields(found) == {"attempted": True, "attempts": found}


def bench_home(tmp_path: Path) -> Path:
    # An arm home holding the acme/widgets bench registry and its rule.
    home = tmp_path / "home"
    out = home / ".knack/registries/acme-widgets"
    write_root(root(), out / "roots" / "widgets-9-1.json")
    (out / "rules").mkdir(parents=True)
    (out / "rules/9.yml").write_text(RULE)
    entry = RegistryEntry(rule=Path("rules/9.yml"), root_ids=["widgets-9-1"])
    registry = Registry(repo="acme/widgets", roots_dir=Path("roots"), rules=[entry])
    (out / "registry.json").write_text(registry.model_dump_json())
    return home


def root() -> Root:
    fields = {
        "id": "widgets-9-1",
        "title": "t",
        "source_url": "https://github.com/acme/widgets/pull/9",
    }
    fields |= {"quote": "q", "decision": "d", "why": "w", "decided_by": "maria"}
    return Root.model_validate(
        fields | {"status": "Confirmed", "rejected_alternative": "gather"}
    )


def saved_run(
    tmp_path: Path, run_id: str, events: list[Any], **fields: Any
) -> RunRecord:
    # A finished run whose export, sandbox and home are still on disk.
    export = tmp_path / f"{run_id}.json"
    export.write_text(json.dumps({"events": events}))
    where = {
        "export_path": export,
        "sandbox": sandbox_with_base(tmp_path / run_id),
        "home": bench_home(tmp_path / run_id),
    }
    named = {
        "run_id": run_id,
        "ticket": "widgets-9",
        "repo": "acme/widgets",
        "rule": "widgets-9",
        "arm": "none",
    }
    return RunRecord.model_validate(named | where | {"label": "correct"} | fields)


def write_runs(path: Path, records: list[RunRecord]) -> Path:
    path.write_text("".join(r.model_dump_json() + "\n" for r in records))
    return path


def test_reclassify_adds_attempts_and_keeps_every_other_field(tmp_path: Path) -> None:
    tried = saved_run(tmp_path, "r1", edit("c1", CLEAN_BODY, GATHER_BODY))
    clean = saved_run(tmp_path, "r2", edit("c1", "def load", "def load_all"))
    runs = write_runs(tmp_path / "runs.jsonl", [tried, clean])
    out = reclassify(runs, tmp_path / "out.jsonl")
    assert [(r.run_id, r.attempted, len(r.attempts)) for r in out] == [
        ("r1", True, 1),
        ("r2", False, 0),
    ]
    assert load_runs(tmp_path / "out.jsonl") == out
    assert out[0].model_dump(exclude={"attempted", "attempts"}) == tried.model_dump(
        exclude={"attempted", "attempts"}
    )


def test_reclassify_leaves_unreadable_runs_unknown(tmp_path: Path) -> None:
    # A bench error, or an export gone missing, is never read as "did not attempt".
    errored = saved_run(tmp_path, "r1", [], error="TimeoutExpired: muse")
    missing = saved_run(tmp_path, "r2", [])
    missing.export_path.unlink()  # type: ignore[union-attr]
    runs = write_runs(tmp_path / "runs.jsonl", [errored, missing])
    assert [r.attempted for r in reclassify(runs, tmp_path / "out.jsonl")] == [
        None,
        None,
    ]


def test_cli_reclassify_writes_out_and_never_overwrites(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = write_runs(
        tmp_path / "runs.jsonl",
        [saved_run(tmp_path, "r1", edit("c1", CLEAN_BODY, GATHER_BODY))],
    )
    out = tmp_path / "out.jsonl"
    assert (
        cli.main(["bench", "reclassify", "--runs", str(runs), "--out", str(out)]) == 0
    )
    assert "1 run" in capsys.readouterr().out
    assert (
        cli.main(["bench", "reclassify", "--runs", str(runs), "--out", str(out)]) == 2
    )
    assert "exists" in capsys.readouterr().err


def test_cli_reclassify_missing_runs_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [
        "bench",
        "reclassify",
        "--runs",
        str(tmp_path / "no.jsonl"),
        "--out",
        str(tmp_path / "o.jsonl"),
    ]
    assert cli.main(args) == 2
    assert "no runs file" in capsys.readouterr().err
