"""KN-114 self-repair live run: sandbox install, edit events, timed steps. Spike driver only."""

import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(sys.argv[2]).resolve()
WORK = Path(sys.argv[3])
ROUTES = "airflow-core/src/airflow/api_fastapi/core_api/routes"
PUBLIC_DAGS = f"{ROUTES}/public/dags.py"
HEAD = REPO / "scripts" / "fixtures" / "75025" / "head"
CAPTURED_EVENT = REPO / "tests" / "hooks" / "fixtures" / "edit_event.json"
COMPLIANT_PATH = f"{ROUTES}/public/dag_sort_keys.py"
COMPLIANT_3 = REPO / "tests" / "fixtures" / "self_repair_75025" / "compliant_3.py"
SEEDED_VARIANTS = Path("/var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-self-repair.MkdG1q/work/75025/variants")
ANCHOR = "from airflow.utils.state import DagRunState, DagSchedulingState\n"
ALIAS_CONST = (
    "\n# Keep the advertised order_by names working: they sort the latest run.\n"
    "ADVERTISED_RUN_SORTS = dict(state=DagRun.state, start_date=DagRun.start_date)\n"
)
OLD_SORT = """                ["dag_id", "dag_display_name", "next_dagrun"],
                DagModel,
                {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date},
"""
EVADING_SORT = """                ["dag_id", "dag_display_name", "next_dagrun", *ADVERTISED_RUN_SORTS],
                DagModel,
                {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date, **ADVERTISED_RUN_SORTS},
"""
CORRECTED_SORT = """                # The latest run sorts only as last_run_state / last_run_start_date (#75025).
                ["dag_id", "dag_display_name", "next_dagrun"],
                DagModel,
                {"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date},
"""


def clone() -> Path:
    return WORK / "airflow"


def settings() -> Path:
    return WORK / "home" / ".config" / "muse" / "settings.json"


def head_text() -> str:
    return (HEAD / PUBLIC_DAGS).read_text()


def evasion() -> str:
    text = head_text()
    assert text.count(ANCHOR) == 1 and text.count(OLD_SORT) == 1
    return text.replace(ANCHOR, ANCHOR + ALIAS_CONST, 1).replace(OLD_SORT, EVADING_SORT, 1)


def corrected() -> str:
    return head_text().replace(OLD_SORT, CORRECTED_SORT, 1)


def install() -> None:
    # #75025's head (the decided code), origin apache/airflow, and the user-level hook.
    for side in ("public", "ui"):
        path = clone() / ROUTES / side / "dags.py"
        path.parent.mkdir(parents=True)
        shutil.copy(HEAD / ROUTES / side / "dags.py", path)
    for args in (["init", "-q", "-b", "main"], ["remote", "add", "origin", "https://github.com/apache/airflow.git"], ["add", "-A"], ["commit", "-q", "-m", "75025 head"]):
        subprocess.run(["git", "-C", str(clone()), *args], check=True)
    command = f"sh -c {shlex.quote(shlex.quote(sys.executable) + ' -m knack.hooks.pretool || true')}"
    entry = {"matcher": "write_file|edit_file", "hooks": [{"type": "command", "command": command}]}
    settings().parent.mkdir(parents=True, exist_ok=True)
    settings().write_text(json.dumps({"schema_version": 1, "hooks": {"PreToolUse": [entry]}}, indent=2) + "\n")
    (WORK / "edits").mkdir(exist_ok=True)
    (WORK / "edits" / "miss.after.py").write_text(evasion())
    (WORK / "edits" / "corrected.after.py").write_text(corrected())
    # The KN-97 run's Spark Open training set, as the per-PR cache a second run would hold.
    shutil.copytree(SEEDED_VARIANTS, WORK / "work" / "75025" / "variants")
    print("installed: clone at #75025's head, PreToolUse hook; registry is KNACK_REGISTRY")


def event(content: str, path: str = PUBLIC_DAGS) -> dict:
    edit = {"path": path, "content": content}
    where = {"tool_name": "write_file", "tool_input": edit, "cwd": str(clone()), "session_id": "self-repair"}
    return json.loads(CAPTURED_EVENT.read_text()) | where


def hook(name: str, which: str, expected: str) -> None:
    command = json.loads(settings().read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    content = {"miss": evasion, "corrected": corrected}.get(which, COMPLIANT_3.read_text)()
    path = COMPLIANT_PATH if which == "compliant" else PUBLIC_DAGS
    payload = json.dumps(event(content, path))
    (WORK / "edits" / f"{name}.event.json").write_text(payload + "\n")
    started = time.perf_counter()
    done = subprocess.run(["sh", "-c", command], input=payload, capture_output=True, text=True, cwd=clone())
    wall_ms = round((time.perf_counter() - started) * 1000, 1)
    got = json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] if done.stdout.strip() else "allow"
    print(f"exit {done.returncode}, {wall_ms} ms, decision {got}")
    print(done.stdout.strip() or "(no output: the hook allowed the edit)")
    if done.stderr.strip():
        print(done.stderr.strip())
    with (WORK / "wall.jsonl").open("a") as handle:
        handle.write(json.dumps({"step": name, "wall_ms": wall_ms, "decision": got}) + "\n")
    sys.exit(0 if got == expected else 1)


def last_receipt(rule_id: str, decision: str) -> None:
    lines = (WORK / "home" / ".knack" / "verdicts.jsonl").read_text().splitlines()
    found = [json.loads(line) for line in lines]
    mine = [r for r in found if r.get("rule_id") == rule_id and r.get("decision") == decision]
    if not mine:
        sys.exit(f"no {decision} receipt for {rule_id}")
    print(mine[-1]["hash"])


def record_must_fail(digest: str) -> None:
    # knack miss's own recording (case_from_receipt, save_case), without its recompile.
    from knack.miss.cases import cases_dir, save_case
    from knack.miss.sources import case_from_receipt, Places
    from knack.receipts.edits import edits_dir
    import os
    receipts = WORK / "home" / ".knack" / "verdicts.jsonl"
    places = Places(receipts, edits_dir(receipts), [], REPO / "bench" / "tickets.jsonl")
    case = case_from_receipt(digest, "must-fail", places)
    path = save_case(cases_dir(Path(os.environ["KNACK_REGISTRY"])), case)
    print(f"recorded must-fail case {case.name} for {case.rule_id} -> {path}")


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "install":
        install()
    elif action == "hook":
        hook(sys.argv[4], sys.argv[5], sys.argv[6])
    elif action == "record":
        record_must_fail(sys.argv[4])
    elif action == "receipt":
        last_receipt(sys.argv[4], sys.argv[5])
