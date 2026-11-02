"""one_story.sh's steps: install the sandbox, replay the #75025 edits, time each step, assemble.

WORK is the sandbox the shell made; its HOME holds the knack home. Every step is kept in
WORK/steps.jsonl with its exit, output and wall time, so the output folder reports this run only.
"""

import json
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = "airflow-core/src/airflow/api_fastapi/core_api/routes"
BASE = ROOT / "scripts" / "fixtures" / "75025" / "base"
RUN3 = ROOT / "tests" / "guard" / "fixtures" / "replay" / "run_neutral_3.diff"
REGISTRY = ROOT / "data" / "registry" / "airflow.json"
PUBLIC_DAGS = f"{ROUTES}/public/dags.py"
ORIGIN = "https://github.com/apache/airflow.git"
# A repo whose origin is apache/airflow, at #75025's base.
GIT_BASE = (
    ["init", "-q", "-b", "main"],
    ["remote", "add", "origin", ORIGIN],
    ["add", "-A"],
    ["commit", "-q", "-m", "base"],
)
RULE_ID = "airflow-75025"
# The blocked edit's alias lines, 1-indexed in the file it proposes; the fix deletes them.
ALIAS_LINES = (135, 136)
ALIASES = ('"state": DagRun.state,', '"start_date": DagRun.start_date,')
NOT_ALIASES = "lines 135-136 of the blocked edit are not the state/start_date aliases"
EVENT = {"hook_event_name": "PreToolUse", "tool_name": "edit_file"}
PRETOOL = " -m knack.hooks.pretool || true"
MATCHER = "write_file|edit_file"
# What a hook step must do: the alias edit is denied, the corrected one allowed.
EXPECTED = {"block": "deny", "corrected": "allow"}
KEPT = (("receipts.jsonl", "verdicts.jsonl"), ("rulings.jsonl", "rulings.jsonl"))
# The second opinion's log and a promoted case exist only when Spark Open was asked.
TRACED = ("self_checks.jsonl", "cases")
SHOWN = ("name", "exit", "stdout", "stderr")

Json = dict[str, Any]


def clone(work: Path) -> Path:
    return work / "airflow"


def knack_home(work: Path) -> Path:
    return work / "home" / ".knack"


def registry_dir(work: Path) -> Path:
    return knack_home(work) / "registries" / "apache-airflow"


def settings(work: Path) -> Path:
    return work / "home" / ".config" / "muse" / "settings.json"


def install(work: Path) -> None:
    # #75025's pre-fix routes, the committed airflow registry and the user-level hook.
    make_clone(clone(work))
    install_registry(REGISTRY, registry_dir(work))
    write_json(settings(work), hook_settings())
    print("installed: clone at #75025's base, airflow registry, PreToolUse hook")


def make_clone(target: Path) -> None:
    for side in ("public", "ui"):
        path = target / ROUTES / side / "dags.py"
        path.parent.mkdir(parents=True)
        shutil.copy(BASE / ROUTES / side / "dags.py", path)
    for command in GIT_BASE:
        git(target, *command)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True)


def install_registry(source: Path, out: Path) -> None:
    # Roots as recorded (no promotion), where knack init puts them.
    data = json.loads(source.read_text())
    shutil.copytree(source.parent / data["roots_dir"], out / "roots")
    (out / "rules").mkdir()
    for entry in data["rules"]:
        entry["rule"] = installed_rule(source.parent / entry["rule"], out)
    write_json(out / "registry.json", data | {"roots_dir": "roots"})


def installed_rule(rule: Path, out: Path) -> str:
    shutil.copy(rule, out / "rules" / rule.name)
    return f"rules/{rule.name}"


def hook_settings() -> Json:
    # As demo_block.sh installs it: every write_file/edit_file goes through knack.hooks.pretool.
    command = f"sh -c {shlex.quote(shlex.quote(sys.executable) + PRETOOL)}"
    entry = {"matcher": MATCHER, "hooks": [{"type": "command", "command": command}]}
    return {"schema_version": 1, "hooks": {"PreToolUse": [entry]}}


def installed_command(work: Path) -> str:
    entry = json.loads(settings(work).read_text())["hooks"]["PreToolUse"][0]
    return entry["hooks"][0]["command"]


def blocked_hunk() -> tuple[int, list[str], list[str]]:
    # Run 3's first hunk, on public/dags.py: its first line, the lines found and replacing.
    header, _, body = RUN3.read_text().split("@@ -", 2)[1].partition("\n")
    lines = body.split("\ndiff --git")[0].splitlines()
    find = [line[1:] for line in lines if line[:1] in (" ", "-")]
    replace = [line[1:] for line in lines if line[:1] in (" ", "+")]
    return int(header.split("+")[1].split(",")[0]), find, replace


def corrected_replace(start: int, replace: list[str]) -> list[str]:
    # The blocked edit with its file's lines 135-136 deleted; refuses if they are not the aliases.
    first, last = (n - start for n in ALIAS_LINES)
    if tuple(line.strip() for line in replace[first : last + 1]) != ALIASES:
        sys.exit(NOT_ALIASES)
    return replace[:first] + replace[last + 1 :]


def edit_event(work: Path, which: str) -> Json:
    start, find, replace = blocked_hunk()
    if which == "corrected":
        replace = corrected_replace(start, replace)
    edit = {"path": PUBLIC_DAGS, "find": "\n".join(find), "replace": "\n".join(replace)}
    where = {"tool_input": edit, "cwd": str(clone(work)), "session_id": "one-story"}
    return EVENT | where


def hook(work: Path, which: str) -> None:
    # The edit_file event Muse sends, through the installed command, timed as Muse runs it.
    command = ["sh", "-c", installed_command(work)]
    step = record(work, which, command, json.dumps(edit_event(work, which)))
    if decision(step["stdout"]) != EXPECTED[which]:
        sys.exit(f"{which}: the hook did not {EXPECTED[which]}")


def decision(hook_stdout: str) -> str:
    # Muse blocks only on the deny envelope; silence is an allow.
    if not hook_stdout:
        return "allow"
    return json.loads(hook_stdout)["hookSpecificOutput"]["permissionDecision"]


def run(work: Path, name: str, command: list[str]) -> None:
    sys.exit(record(work, name, command, None)["exit"])


def record(work: Path, name: str, command: list[str], stdin: str | None) -> Json:
    started, cwd = time.perf_counter(), clone(work)
    done = subprocess.run(command, input=stdin, capture_output=True, text=True, cwd=cwd)
    wall_ms = round((time.perf_counter() - started) * 1000, 1)
    step = {"name": name, "exit": done.returncode} | said(work, done)
    keep_step(work, step | {"wall_ms": wall_ms})
    return show(step, wall_ms)


def said(work: Path, done: subprocess.CompletedProcess[str]) -> Json:
    return {
        "stdout": sandboxed(work, done.stdout),
        "stderr": sandboxed(work, done.stderr),
    }


def keep_step(work: Path, step: Json) -> None:
    with (work / "steps.jsonl").open("a") as handle:
        handle.write(json.dumps(step) + "\n")


def sandboxed(work: Path, text: str) -> str:
    # The sandbox path is random each run, and resolved under /private on macOS: <sandbox>.
    for path in (str(work.resolve()), str(work)):
        text = text.replace(path, "<sandbox>")
    return text.strip()


def show(step: Json, wall_ms: float) -> Json:
    print(f"== {step['name']} (exit {step['exit']}, {wall_ms} ms) ==")
    print(step["stdout"] or "(no output: the hook allowed the edit)")
    if step["stderr"]:
        print(step["stderr"])
    print()
    return step


def receipts(work: Path) -> list[Json]:
    lines = (knack_home(work) / "verdicts.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def block_receipt(work: Path) -> Json:
    return next(r for r in receipts(work) if r["decision"] == "deny")


def passed_receipt(work: Path) -> Json:
    # The corrected edit's verdict under #75025's rule: an allow no person resolved.
    mine = [r for r in receipts(work) if r["rule_id"] == RULE_ID]
    return [r for r in mine if r["decision"] == "allow" and "resolution" not in r][-1]


def steps(work: Path) -> list[Json]:
    lines = (work / "steps.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def latency(work: Path) -> Json:
    # Every figure is this run's: guard time from its receipts, wall time from its steps.
    found = (("block", block_receipt(work)), ("corrected", passed_receipt(work)))
    guard = {
        name: {"receipt": r["hash"], "guard_ms": r["latency_ms"]} for name, r in found
    }
    return guard | {"wall_ms": {s["name"]: s["wall_ms"] for s in steps(work)}}


def manifest(work: Path, models: str) -> Json:
    kept = [{key: step[key] for key in SHOWN} for step in steps(work)]
    named = {"models": models, "block_receipt": block_receipt(work)["hash"]}
    return named | {"rule_id": RULE_ID, "steps": kept}


def assemble(work: Path, out: Path, models: str) -> None:
    # Built whole in the sandbox, then swapped in, so a half-written story is never left.
    built = work / "out"
    keep_files(work, built)
    write_json(built / "latency.json", latency(work))
    write_json(built / "story.json", manifest(work, models))
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(built, out)


def keep_files(work: Path, built: Path) -> None:
    home = knack_home(work)
    shutil.copytree(home / "edits", built / "edits")
    for name, source in KEPT:
        shutil.copy(home / source, built / name)
    copy_if_there(registry_dir(work), built / "traces", TRACED)
    keep_step_traces(work, built / "traces" / "steps")


def keep_step_traces(work: Path, traces: Path) -> None:
    # One file per step, numbered in the order it ran.
    traces.mkdir(parents=True)
    for n, step in enumerate(steps(work), 1):
        (traces / f"{n}_{step['name']}.txt").write_text(step_trace(step))


def copy_if_there(source: Path, target: Path, names: tuple[str, ...]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in (n for n in names if (source / n).exists()):
        copy = shutil.copytree if (source / name).is_dir() else shutil.copy
        copy(source / name, target / name)


def step_trace(step: Json) -> str:
    head = f"exit {step['exit']}\n\n-- stdout --\n{step['stdout']}\n\n"
    return head + f"-- stderr --\n{step['stderr']}\n"


def write_json(path: Path, data: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def print_block_receipt(work: Path) -> None:
    print(block_receipt(work)["hash"])


# one_story.py ACTION WORK [ARGS...]: each action and how it reads its arguments.
ACTIONS: dict[str, Callable[[Path, list[str]], None]] = {
    "install": lambda work, rest: install(work),
    "hook": lambda work, rest: hook(work, rest[0]),
    "run": lambda work, rest: run(work, rest[0], rest[1:]),
    "deny": lambda work, rest: print_block_receipt(work),
    "assemble": lambda work, rest: assemble(work, Path(rest[0]), rest[1]),
}


if __name__ == "__main__":
    ACTIONS[sys.argv[1]](Path(sys.argv[2]), sys.argv[3:])
