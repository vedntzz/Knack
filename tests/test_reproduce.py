import json
from pathlib import Path
from typing import Any

import pytest
from knack.reproduce import (
    breadth_lines,
    extraction_lines,
    heldout_lines,
    HeldOutPr,
    repeats_lines,
    score_prs,
)

REPO_ROOT = Path(__file__).parents[1]
REGISTRIES = [
    REPO_ROOT / "data" / "registry" / f"{r}.json" for r in ("airflow", "fastapi")
]
HELDOUT = REPO_ROOT / "data" / "heldout"
BATCHES = [
    REPO_ROOT / "spikes" / "batch" / b for b in ("apache-airflow", "fastapi-fastapi")
]
RULE = """id: no-eval
language: python
rule:
  pattern: eval($X)
"""


def write_batch(root: Path, prs: list[int], rows: list[dict[str, Any]]) -> Path:
    root.mkdir(parents=True)
    (root / "prs.json").write_text(json.dumps([{"number": n} for n in prs]))
    lines = [json.dumps(row) for row in rows]
    (root / "decisions.jsonl").write_text("\n".join(lines) + "\n")
    return root


def decision(*verbatim: bool) -> dict[str, object]:
    alternatives = [{"alternative": "a", "quote": "q", "verbatim": v} for v in verbatim]
    return {"decision": "d", "rejected_alternatives": alternatives}


def test_extraction_counts_prs_decisions_and_verbatim_alternatives(
    tmp_path: Path,
) -> None:
    rows: list[dict[str, Any]] = [
        {"number": 1, "decisions": [decision(True, False), decision(True)]},
        {"number": 2, "decisions": []},
        {"number": 9, "decisions": [decision()]},
    ]
    batch = write_batch(tmp_path / "owner-name", [1, 2], rows)
    assert extraction_lines([batch]) == [
        "owner-name PRs read: 3",
        "owner-name PRs with a decision: 2",
        "owner-name decisions: 3",
        "owner-name rejected alternatives: 3 (2 verbatim)",
        "total PRs read: 3",
        "total decisions: 3",
        "total rejected alternatives: 3 (2 verbatim)",
    ]


def write_set(directory: Path, violations: list[str], compliant: list[str]) -> None:
    directory.mkdir(parents=True)
    for i, body in enumerate(violations, 1):
        (directory / f"violation_{i}.py").write_text(body)
    for i, body in enumerate(compliant, 1):
        (directory / f"compliant_{i}.py").write_text(body)


def write_registry(tmp_path: Path, rules: dict[str, str]) -> Path:
    (tmp_path / "rules").mkdir()
    (tmp_path / "roots").mkdir()
    entries: list[dict[str, Any]] = []
    for pr, body in rules.items():
        (tmp_path / "rules" / f"{pr}.yml").write_text(body)
        entries.append({"rule": f"rules/{pr}.yml", "root_ids": [f"r-{pr}"]})
    registry = {"repo": "o/n", "roots_dir": "roots", "rules": entries}
    path = tmp_path / "n.json"  # the stem names the data/heldout repo dir
    path.write_text(json.dumps(registry))
    return path


def test_a_pr_passes_with_two_of_three_caught_and_every_compliant_allowed(
    tmp_path: Path,
) -> None:
    registry = write_registry(tmp_path, {"1": RULE})
    caught = ["eval(a)", "eval(b)", "exec(c)"]
    write_set(tmp_path / "heldout" / "n" / "1" / "same", caught, ["x = 1"] * 3)
    write_set(tmp_path / "heldout" / "n" / "1" / "cross", caught, ["eval(z)", "y", "z"])
    (pr,) = score_prs(tmp_path / "heldout", [registry])
    assert pr == HeldOutPr(
        repo="n",
        pr="1",
        same=(2, 3, 3, 3),
        cross=(2, 3, 2, 3),
    )
    assert pr.passed("same") and not pr.passed("cross")


def test_a_heldout_pr_with_no_installed_rule_counts_as_a_fail(tmp_path: Path) -> None:
    registry = write_registry(tmp_path, {})
    for side in ("same", "cross"):
        write_set(tmp_path / "heldout" / "n" / "2" / side, ["eval(a)"] * 3, ["x"] * 3)
    (pr,) = score_prs(tmp_path / "heldout", [registry])
    assert pr.same is None and not pr.passed("same") and not pr.passed("cross")
    assert "n #2 no installed rule: fail" in heldout_lines(
        tmp_path / "heldout", [registry]
    )


def test_generality_is_8_of_13_on_the_committed_heldout_sets() -> None:
    lines = heldout_lines(HELDOUT, REGISTRIES)
    assert "generality (same-model held-out pass): 8/13 PRs" in lines
    assert "cross-model held-out pass: 8/13 PRs" in lines


def test_every_heldout_number_comes_from_a_rule_in_the_committed_registry() -> None:
    prs = score_prs(HELDOUT, REGISTRIES)
    assert len(prs) == 13
    # #16043 has a held-out set but no installed rule; every other PR is scored.
    assert [p.pr for p in prs if p.same is None] == ["16043"]


def test_breadth_names_repos_prs_decisions_roots_rules_and_bench() -> None:
    bench = REPO_ROOT / "bench"
    runs = bench / "runs-1030c.jsonl"
    lines = breadth_lines(BATCHES, REGISTRIES, HELDOUT, bench / "tickets.jsonl", runs)
    assert lines == [
        "repos: 2",
        "PRs read: 101",
        "decisions extracted: 107",
        "roots: 22 (2 Confirmed, 0 Corroborated, 20 Inferred, 0 Uncorroborated, 0 Unknown)",
        "installed rules: 12",
        "held-out PRs: 13",
        "bench tickets: 9",
        "bench runs: 81",
    ]


def write_root(roots: Path, root_id: str, status: str) -> None:
    root = {
        "id": root_id, "title": "t", "decision": "d", "why": "w",
        "decided_by": "a", "source_url": "https://github.com/o/n/pull/1",
        "quote": "q", "status": status,
    }  # fmt: skip
    (roots / f"{root_id}.json").write_text(json.dumps(root))


def test_breadth_counts_every_status_including_corroborated_ones(
    tmp_path: Path,
) -> None:
    registry = write_registry(tmp_path, {})
    statuses = ["Confirmed", "Corroborated", "Corroborated", "Uncorroborated"]
    for i, status in enumerate(statuses):
        write_root(tmp_path / "roots", f"r-{i}", status)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    lines = breadth_lines([], [registry], tmp_path, empty, empty)
    assert (
        "roots: 4 (1 Confirmed, 2 Corroborated, 0 Inferred, 1 Uncorroborated, 0 Unknown)"
        in lines
    )


REPEATS_HEAD = """# Repeats after each decision

| Repo | Decision | Merged | Commits scanned | Repeat commits | Human | Bot |
|---|---|---|---|---|---|---|
"""


def write_repeats(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "REPEATS.md"
    path.write_text(REPEATS_HEAD + "\n".join(rows) + "\n\n## o/n #1: d\n")
    return path


def test_repeats_totals_commits_scanned_and_repeats_by_human_and_bot(
    tmp_path: Path,
) -> None:
    registry = write_registry(tmp_path, {"1": RULE, "2": RULE})
    rows = [
        "| o/n | #1 | 2026-10-01 | 40 | 2 | 1 | 1 |",
        "| o/n | #2 | 2026-10-02 | 7 | 0 | 0 | 0 |",
    ]
    assert repeats_lines(write_repeats(tmp_path, rows), [registry]) == [
        "decisions hunted: 2 (every installed rule)",
        "commits scanned after a decision: 47",
        "repeat commits: 2 (1 human, 1 bot)",
    ]


def test_repeats_fails_when_an_installed_rule_was_never_hunted(
    tmp_path: Path,
) -> None:
    registry = write_registry(tmp_path, {"1": RULE, "2": RULE})
    rows = ["| o/n | #1 | 2026-10-01 | 40 | 0 | 0 | 0 |"]
    with pytest.raises(ValueError, match="o/n #2"):
        repeats_lines(write_repeats(tmp_path, rows), [registry])


def test_repeats_on_the_committed_record_finds_none_in_12_decisions() -> None:
    lines = repeats_lines(REPO_ROOT / "bench" / "REPEATS.md", REGISTRIES)
    assert lines == [
        "decisions hunted: 12 (every installed rule)",
        "commits scanned after a decision: 5068",
        "repeat commits: 0 (0 human, 0 bot)",
    ]
