"""Freeze every value the block frame shows into block.json and block.js, each copied from its source."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
LOG_COMMIT = "b8c3032"
ROUTES = "airflow-core/src/airflow/api_fastapi/core_api/routes"
RUN3 = "tests/guard/fixtures/replay/run_neutral_3.diff"
GITHUB = "mockups/refs/github-75025.json"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def read(rel: str) -> str:
    return (REPO / rel).read_text()


def found(pattern: str, text: str) -> str:
    # The first group of pattern in text; a missing source line stops the freeze.
    match = re.search(pattern, text, re.M)
    if match is None:
        raise ValueError(f"not in source: {pattern}")
    return match.group(1)


def demo_log() -> str:
    return git("show", f"{LOG_COMMIT}:bench/demo_block.log")


def reason(log: str, label: str) -> str:
    # One "Label: value" line of the reason as the agent reads it.
    return found(
        rf"^{label}: (.+)$", log.split("== reason, as the agent reads it ==")[1]
    )


def matched(log: str) -> list[dict[str, Any]]:
    # Each "<text> (line N)" from the log's Matched: line.
    pairs = re.findall(r'(".*?"(?:: [\w.]+)?) \(line (\d+)\)', reason(log, "Matched"))
    return [{"text": text, "line": int(line)} for text, line in pairs]


def hunk_rows(diff: str) -> list[dict[str, Any]]:
    # The first hunk of run 3, numbered on both sides, as a diff viewer shows it.
    hunk = re.search(r"^@@ -(\d+),\d+ \+(\d+),\d+ @@.*\n((?:[ +-].*\n)+)", diff, re.M)
    assert hunk is not None, "run 3 has no hunk"
    old, new, rows = int(hunk.group(1)), int(hunk.group(2)), []
    for line in hunk.group(3).splitlines():
        old, new = step(rows, line, old, new)
    return rows


def step(rows: list[dict[str, Any]], line: str, old: int, new: int) -> tuple[int, int]:
    # Append one diff line with its old and new numbers; return the next pair.
    kind = {"+": "add", "-": "del", " ": "ctx"}[line[0]]
    rows.append(
        {
            "kind": kind,
            "old": old if kind != "add" else None,
            "new": new if kind != "del" else None,
            "code": line[1:],
        }
    )
    return old + (kind != "add"), new + (kind != "del")


def pr_change(side_file: str, line: int) -> list[dict[str, Any]]:
    # #75025's own change to one line: the base line it removed and the head line it kept.
    base = read(f"scripts/fixtures/75025/base/{ROUTES}/{side_file}").splitlines()[
        line - 1
    ]
    head = read(f"scripts/fixtures/75025/head/{ROUTES}/{side_file}").splitlines()[
        line - 1
    ]
    return [
        {"kind": "del", "line": line, "code": base},
        {"kind": "add", "line": line, "code": head},
    ]


def grid() -> dict[str, Any]:
    # The proof grid's header and its #75025 row, cell by cell.
    rows = [
        r
        for r in read("bench/PROOF-GRID.md").splitlines()
        if r.startswith("| Decision |") or "| airflow-75025-1 |" in r
    ]
    header, row = ([c.strip() for c in r.strip("|").split("|")] for r in rows[:2])
    return {
        "gates": header[3:-1],
        "cells": dict(zip(header[3:-1], row[3:-1])),
        "tier": row[2],
        "evidence": row[-1],
    }


def quote(root: dict[str, Any], log: str, pr: dict[str, Any]) -> dict[str, Any]:
    # Quote and Why are consecutive sentences in the PR body; the body's next sentence is not on record.
    said = [reason(log, "Quote").strip('"'), reason(log, "Why")]
    assert said[0] == root["quote"] and said[1] == root["why"], "log and root disagree"
    joined = " ".join(said)
    assert joined in pr["body"], "the two sentences are not consecutive in the PR body"
    rest = pr["body"].split(joined, 1)[1].split("\n", 1)[0].strip()
    return {
        "sentences": said,
        "rejected_phrase": found(r"(aliasing .+?)\.$", said[0]),
        "not_recorded": rest,
    }


def where(log: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(found(r"^(\{\"hookSpecificOutput\".+)$", log))
    return {
        "repo": found(r"github\.com/([\w-]+/[\w-]+)/pull", reason(log, "Source")),
        "branch": found(
            r"git -C \"\$CLONE\" init -q -b (\w+)", read("scripts/demo_block.sh")
        ),
        "file": found(r"^edit_file (\S+): ", log),
        "edit": found(r"^edit_file \S+: (.+)$", log),
        "tool": "edit_file",
        "lines": sorted({m["line"] for m in matched(log)}),
        "rule": found(r"^id: (\S+)", read("data/rules/airflow/75025.yml")),
        "hook": payload["hookSpecificOutput"]["hookEventName"],
        "decision": payload["hookSpecificOutput"]["permissionDecision"],
        "dispute": reason(log, "To dispute"),
        "log_committed": git("log", "-1", "--format=%cI", LOG_COMMIT).strip(),
        "first_new_line": rows[0]["new"],
    }


def proof(log: str) -> dict[str, Any]:
    registry = json.loads(read("data/registry/airflow.json"))
    entry = next(r for r in registry["rules"] if "airflow-75025-1" in r["root_ids"])
    return {
        "grid": grid(),
        "old_release": entry["proof"]["old_release"]["ref"],
        "fp": entry["proof"]["false_positives"]
        + entry["proof"]["old_release"]["false_positives"],
        "receipt": found(r"/verdict/([0-9a-f]{64})", log),
        "verdict_ms": found(r"^guard verdict: ([\d.]+) ms", log),
        "round_trip_ms": found(r"^hook round trip: (\d+) ms", log),
        "scan": found(r"^guard verdict: [\d.]+ ms \((ast-grep) scan", log),
        "no_model": found(r"(No model, no network\.)", log),
    }


def person(pr: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    approvals = [r for r in pr["reviews"] if r["state"] == "APPROVED"]
    return {
        "name": found(r"^(.+?) \(author\)", root["decided_by"]),
        "handle": pr["author"],
        "avatar": "refs/pushkal-gupta-avatar.png",
        "wrote_at": pr["created_at"],
        "approved_by": approvals[0]["user"],
        "approved_at": approvals[0]["submitted_at"],
    }


def freeze() -> dict[str, Any]:
    root, log = json.loads(read("data/roots/airflow/75025.json")), demo_log()
    pr, rows = json.loads(read(GITHUB)), hunk_rows(read(RUN3))
    attempted = {
        "file": where(log, rows)["file"],
        "rows": rows,
        "matched": matched(log),
    }
    rejected = [
        {"file": f"{ROUTES}/{f}", "rows": pr_change(f, n)}
        for f, n in (("public/dags.py", 132), ("ui/dags.py", 139))
    ]
    keep = (
        "id",
        "status",
        "seeded",
        "decided_by",
        "decision",
        "source_url",
        "merged_at",
        "rejected_alternative",
    )
    return {
        "root": {k: root[k] for k in keep},
        "confirmed_by": root.get("confirmed_by"),
        "quote": quote(root, log, pr),
        "person": person(pr, root),
        "attempted": attempted,
        "rejected": rejected,
        "where": where(log, rows),
        "proof": proof(log),
    }


def main() -> None:
    data = json.dumps(freeze(), indent=1, ensure_ascii=False)
    (OUT / "block.json").write_text(data + "\n")
    (OUT / "block.js").write_text(
        f"// Written by freeze_block.py; do not edit.\nwindow.BLOCK = {data};\n"
    )


if __name__ == "__main__":
    main()
