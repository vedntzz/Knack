"""Freeze every value final.html shows into scenes.json and scenes.js, each copied from its source."""

import difflib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RULINGS = Path.home() / ".knack" / "rulings.jsonl"
HOLD_RECEIPT = "13f19d15e9004021ca849af1a05c11408d90e26c9e28d016c1345b20652bb86f"
ESCALATE_RECEIPT = "1983f52b4751dc29c81c30c52b442c6540667465fa4c62143b0a3569c7431520"
DEMO_LOG_COMMIT = "b8c3032"
BASE_75025 = "scripts/fixtures/75025"
ROUTES = "airflow-core/src/airflow/api_fastapi/core_api/routes"
MISS = "bench/misses/16062-none-2"


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return done.stdout


def read(rel: str) -> str:
    return (REPO / rel).read_text()


def found(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.M)
    if match is None:
        raise ValueError(f"not in source: {pattern}")
    return match.group(1)


def reason_field(reason: str, label: str) -> str:
    # One "Label: value" line of the deny reason the agent reads.
    return found(rf"^{re.escape(label)}: (.+)$", reason)


def deny_reason(log: str) -> str:
    line = next(x for x in log.splitlines() if x.startswith('{"hookSpecificOutput"'))
    return json.loads(line)["hookSpecificOutput"]["permissionDecisionReason"]


def matched_lines(reason: str) -> list[dict[str, Any]]:
    # Matched: `"state": DagRun.state (line 135), ...`, longest text per line.
    pairs = re.findall(r"(.+?) \(line (\d+)\)(?:, |$)", reason_field(reason, "Matched"))
    best: dict[int, str] = {}
    for text, line in pairs:
        best[int(line)] = max(best.get(int(line), ""), text, key=len)
    return [{"line": n, "text": t} for n, t in sorted(best.items())]


def new_side_lines(diff: str, path: str) -> dict[int, str]:
    # Number every line of the new side of one file's hunks.
    numbered, current, n = {}, None, 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("@@") and current == path:
            n = int(found(r"\+(\d+)", line))
        elif current == path and n and line[:1] in (" ", "+"):
            numbered[n] = line[1:]
            n += 1
    return numbered


def attempted(reason: str, diff: str) -> dict[str, Any]:
    path = found(r"^\+\+\+ b/(.+)$", diff)
    lines = new_side_lines(diff, path)
    rows = [{**m, "code": lines[m["line"]].strip()} for m in matched_lines(reason)]
    return {"file": path, "rows": rows}


def removed_lines(rel: str) -> list[dict[str, Any]]:
    # Lines the PR took out of the base: the base side of the base→head diff.
    base = read(f"{BASE_75025}/base/{rel}").splitlines()
    head = read(f"{BASE_75025}/head/{rel}").splitlines()
    matcher = difflib.SequenceMatcher(a=base, b=head, autojunk=False)
    spans = [op for op in matcher.get_opcodes() if op[0] in ("replace", "delete")]
    return [
        {"file": rel, "line": i + 1, "code": base[i].strip()}
        for _, i1, i2, _, _ in spans
        for i in range(i1, i2)
    ]


def rejected_base() -> list[dict[str, Any]]:
    files = [f"{ROUTES}/public/dags.py", f"{ROUTES}/ui/dags.py"]
    return [row for rel in files for row in removed_lines(rel)]


def block_scene() -> dict[str, Any]:
    log = git("show", f"{DEMO_LOG_COMMIT}:bench/demo_block.log")
    reason = deny_reason(log)
    labels = ["Decision", "Decided by", "Quote", "Source", "Rejected alternative"]
    return {
        "reason": {label: reason_field(reason, label) for label in labels},
        "verdict_ms": found(r"guard verdict: ([\d.]+) ms", log),
        "round_trip_ms": found(r"hook round trip: (\d+) ms", log),
        "scan": found(r"guard verdict: [\d.]+ ms \((ast-grep) scan", log),
        "no_model": found(r"(No model, no network\.)", log),
        "receipt": found(r"^Console: \S+/verdict/([0-9a-f]{64})$", reason),
        "attempted": attempted(reason, read(REPLAY)),
        "log_commit": git("log", "-1", "--format=%h %cI", DEMO_LOG_COMMIT).strip(),
    }


REPLAY = "tests/guard/fixtures/replay/run_neutral_3.diff"


def grid_row(pr: str) -> dict[str, Any]:
    # Gate names exactly as the grid header prints them; the row's cells beside them.
    lines = [x for x in read("bench/PROOF-GRID.md").splitlines() if x.startswith("|")]
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    row = next(x for x in lines if f"#{pr} " in x)
    cells = [c.strip() for c in row.strip("|").split("|")]
    gates = header[3:-1]
    return {"gates": gates, "cells": dict(zip(gates, cells[3:-1])), "tier": cells[2]}


def registry_proof(pr: int) -> dict[str, Any]:
    data = json.loads(read("data/registry/airflow.json"))
    entry = next(r for r in data["rules"] if r["proof"]["pr"] == pr)
    proof = entry["proof"]
    return {"old_release": proof["old_release"]["ref"], "fp": proof["false_positives"]}


def ruling(receipt: str, decision: str) -> dict[str, Any]:
    rows = [json.loads(x) for x in RULINGS.read_text().splitlines() if x.strip()]
    return next(
        r for r in rows if r["receipt_hash"] == receipt and r["decision"] == decision
    )


def host_model(rel: str) -> dict[str, str]:
    text = read(rel)
    url = found(r'^URL = "([^"]+)"', text)
    return {"model": found(r'^MODEL = "([^"]+)"', text), "host": urlparse(url).netloc}


def readme_verify() -> str:
    # The command README's "Run the proof" block states, verbatim.
    return found(r"From the clone[^\n]*\n\n```sh\n(.+)\n```", read("README.md"))


def readme_resolve() -> str:
    return found(r"settles it with `(knack resolve [^`]+)`", read("README.md"))


def receipts_verify() -> str:
    knack = REPO / ".venv" / "bin" / "knack"
    done = subprocess.run([str(knack), "receipts", "verify"], capture_output=True)
    return done.stdout.decode().strip().rsplit(": ", 1)[-1]


def miss_scene() -> dict[str, Any]:
    edit = json.loads(read(f"{MISS}.edit.json"))
    return {
        "root": json.loads(read("data/roots/fastapi/16062-1.json")),
        "edit_note": edit["note"],
        "edit_file": edit["file"],
        "edit_after": edit["after"],
        "run1_log": read(f"{MISS}.run1.log"),
        "run2_log": read(f"{MISS}.run2.log"),
        "bar2_log": read(f"{MISS}.bar2.log"),
        "tier": grid_row("16062")["tier"],
        "cases": sorted(
            p.name for p in (REPO / "data/registry/cases/fastapi-16062").iterdir()
        ),
    }


def scenes() -> dict[str, Any]:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "day": json.loads(read("mockups/fixtures/day.json")),
        "root": json.loads(read("data/roots/airflow/75025.json")),
        "block": block_scene(),
        "rejected_base": rejected_base(),
        "grid": grid_row("75025"),
        "proof": registry_proof(75025),
        "hold": ruling(HOLD_RECEIPT, "hold"),
        "escalate": ruling(ESCALATE_RECEIPT, "escalate"),
        "spark": host_model("knack/pipeline/spark.py"),
        "spark_open": host_model("knack/pipeline/spark_open.py"),
        "readme": {"verify": readme_verify(), "resolve": readme_resolve()},
        "receipts_verify": receipts_verify(),
        "miss": miss_scene(),
    }


def main() -> None:
    frozen = json.dumps(scenes(), indent=2, ensure_ascii=False)
    (OUT / "scenes.json").write_text(frozen + "\n")
    (OUT / "scenes.js").write_text(
        f"// Frozen by freeze.py; see mockups/SOURCES.md.\nwindow.KNACK = {frozen};\n"
    )


if __name__ == "__main__":
    main()
