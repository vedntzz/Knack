import json
from pathlib import Path
from typing import Any

import pytest
from knack.hooks.adapters import (
    edit_target,
    malformed_count,
    MalformedPayload,
    proposed_edit,
    ProposedEdit,
    UnknownTool,
)
from knack.hooks.pretool_guard import decide
from knack.receipts.chain import load_receipts
from test_pretool import (
    AIRFLOW_URL,
    deny_reason,
    hook_env,
    hook_stdout_json,
    load_event,
    make_clone,
    make_registry,
    run_pretool,
    SOURCE_URL,
    write_registry_file,
)

VIOLATING = (Path(__file__).parents[1] / "guard/fixtures/violating.py").read_text()
# violating.py with the two bare sort keys taken out: no match, so no deny.
BARE_KEYS = '"next_dagrun", "state", "start_date"]'
CLEAN = VIOLATING.replace(BARE_KEYS, '"next_dagrun"]')
ALL_TOOLS = ["write_file", "edit_file", "Write", "Edit", "MultiEdit"]


def tool_input(tool: str, path: str) -> dict[str, Any]:
    # Each tool's own input that turns CLEAN into VIOLATING.
    inputs: dict[str, dict[str, Any]] = {
        "write_file": {"path": path, "content": VIOLATING},
        "edit_file": {"path": path, "find": '"next_dagrun"]', "replace": BARE_KEYS},
        "Write": {"file_path": path, "content": VIOLATING},
        "Edit": {"file_path": path, "old_string": '"next_dagrun"]'},
        "MultiEdit": {"file_path": path, "edits": two_step_edits()},
    }
    inputs["Edit"]["new_string"] = BARE_KEYS
    return inputs[tool]


def two_step_edits() -> list[dict[str, Any]]:
    # The second edit only finds its text after the first applied: order matters.
    first = {"old_string": '"next_dagrun"]', "new_string": '"next_dagrun", "state"]'}
    second = {"old_string": '"state"]', "new_string": '"state", "start_date"]'}
    return [first, {**second, "replace_all": False}]


def event_for(tool: str, cwd: Path, path: str = "dags.py") -> dict[str, Any]:
    # The tool's own captured or documented payload, aimed at a CLEAN dags.py.
    (cwd / "dags.py").write_text(CLEAN, encoding="utf-8")
    event = load_event(FIXTURE[tool])
    event.update(tool_input=tool_input(tool, path), cwd=str(cwd))
    return event


FIXTURE = {
    "write_file": "write_event.json",
    "edit_file": "edit_event.json",
    "Write": "claude_code_write_event.json",
    "Edit": "claude_code_edit_event.json",
    "MultiEdit": "claude_code_multiedit_event.json",
}


@pytest.mark.parametrize("tool", ALL_TOOLS)
def test_every_adapter_proposes_violating_py(tool: str, tmp_path: Path) -> None:
    event = event_for(tool, tmp_path)
    target = tmp_path / "dags.py"
    assert edit_target(event, tmp_path) == target
    assert proposed_edit(event, target) == ProposedEdit(target, VIOLATING)


@pytest.mark.parametrize("tool", ALL_TOOLS)
def test_violating_py_through_every_adapter_is_denied(
    tool: str, tmp_path: Path
) -> None:
    event = event_for(tool, tmp_path)
    reason = decide(event, make_registry(tmp_path), tmp_path / "log")
    assert SOURCE_URL in deny_reason(reason)


@pytest.mark.parametrize("tool", ALL_TOOLS)
def test_no_new_violation_through_every_adapter_is_allowed(
    tool: str, tmp_path: Path
) -> None:
    # The file already holds the violation, so the edit adds nothing new.
    event = event_for(tool, tmp_path)
    (tmp_path / "dags.py").write_text(VIOLATING, encoding="utf-8")
    assert decide(event, make_registry(tmp_path), tmp_path / "log") is None


def test_claude_code_absolute_file_path_is_kept(tmp_path: Path) -> None:
    event = event_for("Write", tmp_path, str(tmp_path / "dags.py"))
    assert edit_target(event, Path("/elsewhere")) == tmp_path / "dags.py"


def test_claude_code_edit_replace_all_replaces_every_match(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    inputs = {"file_path": "a.py", "old_string": "1", "new_string": "2"}
    event = {"tool_name": "Edit", "tool_input": {**inputs, "replace_all": True}}
    edit = proposed_edit(event, tmp_path / "a.py")
    assert edit.new_content == "x = 2\nx = 2\n"


def test_claude_code_edit_without_replace_all_replaces_once(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    inputs = {"file_path": "a.py", "old_string": "1", "new_string": "2"}
    edit = proposed_edit({"tool_name": "Edit", "tool_input": inputs}, tmp_path / "a.py")
    assert edit.new_content == "x = 2\nx = 1\n"


def test_claude_code_edit_creating_a_new_file_proposes_its_text(
    tmp_path: Path,
) -> None:
    # Claude Code's Edit with an empty old_string on a missing file creates it.
    inputs = {"file_path": "new.py", "old_string": "", "new_string": VIOLATING}
    event = {"tool_name": "Edit", "tool_input": inputs}
    assert proposed_edit(event, tmp_path / "new.py").new_content == VIOLATING


@pytest.mark.parametrize("tool", ["bash", "Bash", "Read"])
def test_tools_that_edit_no_file_have_no_target(tool: str, tmp_path: Path) -> None:
    assert edit_target({"tool_name": tool, "tool_input": {}}, tmp_path) is None


def test_an_unknown_tool_is_named_not_guessed(tmp_path: Path) -> None:
    event = {"tool_name": "apply_patch", "tool_input": {"patch": "..."}}
    with pytest.raises(UnknownTool, match="apply_patch"):
        edit_target(event, tmp_path)


MALFORMED = [
    {"tool_name": "write_file", "cwd": "/x"},
    {"tool_name": "Write", "tool_input": "not an object"},
    {"tool_name": "Write", "tool_input": {"content": "x"}},
    {"tool_name": "Write", "tool_input": {"file_path": "a.py", "content": 3}},
    {"tool_name": "Edit", "tool_input": {"file_path": "a.py", "old_string": "x"}},
    {"tool_name": "MultiEdit", "tool_input": {"file_path": "a.py", "edits": "x"}},
    {"tool_name": "MultiEdit", "tool_input": {"file_path": "a.py", "edits": [1]}},
    {"tool_name": "edit_file", "tool_input": {"path": "a.py", "find": "x"}},
]


@pytest.mark.parametrize("event", MALFORMED)
def test_a_malformed_payload_raises_no_key_error(
    event: dict[str, Any], tmp_path: Path
) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(MalformedPayload):
        target = edit_target(event, tmp_path)
        proposed_edit(event, target or tmp_path / "a.py")


def test_malformed_payload_fails_open_logged_and_counted(tmp_path: Path) -> None:
    event = {"tool_name": "Write", "tool_input": {"content": VIOLATING}}
    event["cwd"] = str(tmp_path)
    for _ in range(2):
        assert decide(event, make_registry(tmp_path), tmp_path / "log") is None
    assert "KeyError" not in (tmp_path / "log").read_text()
    assert "MalformedPayload" in (tmp_path / "log").read_text()
    assert malformed_count(tmp_path) == 2


def test_malformed_payload_keeps_its_guard_error_receipt(tmp_path: Path) -> None:
    event = {"tool_name": "Edit", "tool_input": {"file_path": "a.py"}}
    receipts = tmp_path / "verdicts.jsonl"
    decide(
        {**event, "cwd": str(tmp_path)},
        make_registry(tmp_path),
        tmp_path / "log",
        receipts,
    )
    assert [r.decision for r in load_receipts(receipts)] == ["guard-error"]


def test_unknown_tool_allows_logs_and_is_not_receipted(tmp_path: Path) -> None:
    event: dict[str, Any] = {"tool_name": "apply_patch", "tool_input": {}}
    event["cwd"] = str(tmp_path)
    receipts = tmp_path / "verdicts.jsonl"
    assert decide(event, make_registry(tmp_path), tmp_path / "log", receipts) is None
    assert "UnknownTool: apply_patch" in (tmp_path / "log").read_text()
    assert not receipts.exists() and malformed_count(tmp_path) == 0


def test_bash_is_silent_and_unlogged(tmp_path: Path) -> None:
    event = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert (
        decide(
            {**event, "cwd": str(tmp_path)}, make_registry(tmp_path), tmp_path / "log"
        )
        is None
    )
    assert not (tmp_path / "log").exists()


def test_no_count_file_reads_as_zero(tmp_path: Path) -> None:
    assert malformed_count(tmp_path / "nowhere") == 0


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_audit_b1_claude_code_edit_is_denied_by_the_real_hook(
    tool: str, tmp_path: Path
) -> None:
    # Audit B1 (Write) and B1b (Edit): the installed entry point, a Claude Code payload.
    clone = make_clone(tmp_path / "airflow", AIRFLOW_URL)
    event = event_for(tool, clone, str(clone / "dags.py"))
    env = hook_env(write_registry_file(tmp_path), tmp_path / "home")
    done = run_pretool(json.dumps(event), clone, env)
    assert done.returncode == 0
    assert SOURCE_URL in deny_reason(hook_stdout_json(done))
