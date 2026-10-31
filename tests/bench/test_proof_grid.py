import json
from pathlib import Path
from typing import Any

import pytest
from knack.bench.proof_grid import grid_lines, grid_rows, GridRow, log_attempts
from knack.contracts.models import RuleProof
from knack.reproduce import COMPILE_LOGS, HeldOutPr, REGISTRIES
from knack.roots.pin import rule_sha

GATES = [
    "base",
    "head",
    "0 FP tree",
    "0 FP release",
    "rename",
    "variants",
    "compliant",
    "held-out",
]
RULE_BODY = "language: python\nrule:\n  pattern: alias($X)"
PASSING_LOG = """=== #9 ATTEMPT 1 ===
id: compiled-rule
language: python
rule:
  pattern: other($X)

base must flag >=1 | pkg/a.py: no matches

=== #9 ATTEMPT 2 ===
id: compiled-rule
language: python
rule:
  pattern: alias($X)

base must flag >=1 | pkg/a.py: 'alias(1)' (line 3)
head must flag 0 | pkg/a.py: no matches
rename-base must flag >=1 (base with its local variables renamed) | pkg/a.py: 'alias(v)' (line 3)
rename-head must flag 0 (head with every identifier this PR introduced renamed to _r... names) | pkg/a.py: no matches
variant-violation must flag >=1 (fresh violation; >=2 of 3 must be flagged) | violation_1.py: 'alias(2)' (line 1)
variant-violation must flag >=1 (fresh violation; >=2 of 3 must be flagged) | violation_2.py: no matches
variant-violation must flag >=1 (fresh violation; >=2 of 3 must be flagged) | violation_3.py: no matches
variant-compliant must flag 0 (fresh compliant code) | compliant_1.py: ast-grep exited 2: boom
acme/widgets main must flag 0 outside this PR's files | 0 false positives
"""


def root(root_id: str, status: str, sha: str | None = None) -> dict[str, Any]:
    url = "https://github.com/acme/widgets/pull/9"
    fields = {"id": root_id, "title": "t", "decision": "d", "why": "w"}
    fields |= {"decided_by": "maria", "source_url": url, "quote": "q"}
    return fields | {"status": status, "rule_sha": sha}


def registry(tmp_path: Path, entries: dict[str, dict[str, Any]]) -> Path:
    # One rule file per entry; each entry names its roots' statuses and an optional proof.
    (tmp_path / "rules").mkdir()
    (tmp_path / "roots").mkdir()
    rules = [_entry(tmp_path, number, spec) for number, spec in entries.items()]
    body = {"repo": "acme/widgets", "roots_dir": "roots", "rules": rules}
    (tmp_path / "widgets.json").write_text(json.dumps(body))
    return tmp_path / "widgets.json"


def _entry(tmp_path: Path, number: str, spec: dict[str, Any]) -> dict[str, Any]:
    rule = tmp_path / "rules" / f"{number}.yml"
    rule.write_text(f"id: widgets-{number}\n{RULE_BODY}\n")
    for root_id, status in spec["roots"].items():
        sha = rule_sha(rule) if spec.get("pinned") else spec.get("pin")
        data = root(root_id, status, sha)
        (tmp_path / "roots" / f"{root_id}.json").write_text(json.dumps(data))
    entry = {"rule": f"rules/{number}.yml", "root_ids": list(spec["roots"])}
    return entry | ({"proof": spec["proof"]} if "proof" in spec else {})


def log(tmp_path: Path, text: str = PASSING_LOG) -> Path:
    path = tmp_path / "compile_run.log"
    path.write_text(text)
    return path


def one_row(tmp_path: Path, spec: dict[str, Any], **kwargs: Any) -> GridRow:
    path = registry(tmp_path, {"9": spec})
    attempts = log_attempts([log(tmp_path)])
    [row] = grid_rows([path], kwargs.get("heldout", {}), attempts)
    return row


PROOF = {
    "pr": 9,
    "base_sha": "b",
    "head_sha": "h",
    "attempts": 1,
    "sides": [
        {"side": "base", "files": 1, "flagged": 1},
        {"side": "head", "files": 1, "flagged": 1},
        {"side": "rename-base", "files": 1, "flagged": 1},
        {"side": "rename-head", "files": 1, "flagged": 0},
        {"side": "variant-violation", "files": 3, "flagged": 2},
        {"side": "variant-compliant", "files": 3, "flagged": 0},
    ],
    "false_positives": 2,
    "old_release": {"ref": "v1.0", "false_positives": 0},
}


def test_log_attempts_split_by_pr_and_attempt(tmp_path: Path) -> None:
    attempts = log_attempts([log(tmp_path)])
    assert [(a.pr, a.attempt) for a in attempts] == [("9", 1), ("9", 2)]
    assert attempts[1].rule == RULE_BODY


def test_the_attempt_whose_rule_text_is_installed_supplies_the_gates(
    tmp_path: Path,
) -> None:
    row = one_row(tmp_path, {"roots": {"widgets-9-1": "Inferred"}})
    assert row.marks["base"] == "PASS" and row.marks["head"] == "PASS"
    assert row.marks["rename"] == "PASS" and row.marks["0 FP tree"] == "PASS"
    assert row.source == "compile_run.log #9 attempt 2"


def test_one_of_three_violations_caught_fails_variants(tmp_path: Path) -> None:
    row = one_row(tmp_path, {"roots": {"widgets-9-1": "Inferred"}})
    assert row.marks["variants"] == "FAIL"


def test_an_ast_grep_error_on_a_side_fails_it(tmp_path: Path) -> None:
    row = one_row(tmp_path, {"roots": {"widgets-9-1": "Inferred"}})
    assert row.marks["compliant"] == "FAIL"


def test_a_gate_the_record_never_shows_is_not_run(tmp_path: Path) -> None:
    row = one_row(tmp_path, {"roots": {"widgets-9-1": "Inferred"}})
    assert row.marks["0 FP release"] == "NOT RUN"
    assert row.marks["held-out"] == "NOT RUN"


def test_a_rule_no_record_proves_is_not_run_everywhere(tmp_path: Path) -> None:
    path = registry(tmp_path, {"9": {"roots": {"widgets-9-1": "Inferred"}}})
    (tmp_path / "rules" / "9.yml").write_text("id: widgets-9\nlanguage: python\n")
    [row] = grid_rows([path], {}, log_attempts([log(tmp_path)]))
    assert set(row.marks.values()) == {"NOT RUN"} and row.source == "none"


def test_an_install_proof_wins_over_the_logs(tmp_path: Path) -> None:
    row = one_row(tmp_path, {"roots": {"widgets-9-1": "Inferred"}, "proof": PROOF})
    assert RuleProof.model_validate(PROOF)
    assert (row.marks["head"], row.marks["variants"]) == ("FAIL", "PASS")
    assert (row.marks["0 FP tree"], row.marks["0 FP release"]) == ("FAIL", "PASS")
    assert row.source == "install proof"


@pytest.mark.parametrize(
    ("same", "cross", "mark"),
    [
        ((2, 3, 3, 3), (3, 3, 3, 3), "PASS"),
        ((2, 3, 3, 3), (1, 3, 3, 3), "FAIL"),
        ((3, 3, 2, 3), (3, 3, 3, 3), "FAIL"),
    ],
)
def test_held_out_passes_only_when_both_sets_pass(
    tmp_path: Path, same: Any, cross: Any, mark: str
) -> None:
    held = HeldOutPr(repo="widgets", pr="9", same=same, cross=cross)
    row = one_row(
        tmp_path,
        {"roots": {"widgets-9-1": "Inferred"}},
        heldout={("widgets", "9"): held},
    )
    assert row.marks["held-out"] == mark


def test_a_pinned_confirmed_root_is_the_block_tier(tmp_path: Path) -> None:
    spec = {"roots": {"widgets-9-1": "Confirmed"}, "pinned": True}
    assert one_row(tmp_path, spec).tier == "block"


def test_an_unpinned_confirmed_root_is_the_block_tier(tmp_path: Path) -> None:
    assert one_row(tmp_path, {"roots": {"widgets-9-1": "Confirmed"}}).tier == "block"


def test_a_stale_pin_is_the_warn_tier(tmp_path: Path) -> None:
    spec = {"roots": {"widgets-9-1": "Confirmed"}, "pin": "0" * 64}
    assert one_row(tmp_path, spec).tier == "warn"


@pytest.mark.parametrize("status", ["Inferred", "Corroborated", "Unknown"])
def test_any_other_label_is_the_warn_tier(tmp_path: Path, status: str) -> None:
    assert one_row(tmp_path, {"roots": {"widgets-9-1": status}}).tier == "warn"


def test_the_grid_is_a_table_with_every_gate_tier_and_totals(tmp_path: Path) -> None:
    path = registry(tmp_path, {"9": {"roots": {"widgets-9-1": "Confirmed"}}})
    (tmp_path / "roots" / "widgets-7-1.json").write_text(
        json.dumps(root("widgets-7-1", "Inferred"))
    )
    lines = grid_lines([path], {}, [log(tmp_path)])
    header = "| Decision | Roots | Tier | " + " | ".join(GATES) + " | Evidence |"
    assert header in lines
    [row] = [line for line in lines if line.startswith("| acme/widgets #9 ")]
    assert "| block |" in row and "| FAIL |" in row and "| NOT RUN |" in row
    assert "base: 1 PASS, 0 FAIL, 0 NOT RUN" in lines
    assert (
        "Decisions with no installed rule (never block or warn): widgets-7-1" in lines
    )


REPROVED = PROOF | {
    "false_positives": 0,
    "reproved_at": "2026-10-31T01:02:03Z",
    "not_run": {"0 FP release": "no X.Y.Z release was tagged before the PR merged"},
    "old_release": None,
}


def reproved(tmp_path: Path, **changes: Any) -> dict[str, Any]:
    # A reprove result pinned to the rule text one_row writes.
    rule = tmp_path / "pinned.yml"
    rule.write_text(f"id: widgets-9\n{RULE_BODY}\n")
    return REPROVED | {"rule_sha": rule_sha(rule)} | changes


def test_a_reproved_proof_is_the_evidence_and_names_its_run(tmp_path: Path) -> None:
    spec = {"roots": {"widgets-9-1": "Inferred"}, "proof": reproved(tmp_path)}
    row = one_row(tmp_path, spec)
    assert row.source == "knack reprove 2026-10-31"
    assert row.marks["0 FP tree"] == "PASS" and row.marks["0 FP release"] == "NOT RUN"


def test_a_proof_of_other_rule_text_is_ignored(tmp_path: Path) -> None:
    stale = reproved(tmp_path, rule_sha="0" * 64)
    row = one_row(tmp_path, {"roots": {"widgets-9-1": "Inferred"}, "proof": stale})
    assert row.source == "compile_run.log #9 attempt 2"


def test_recorded_errors_fail_their_gates(tmp_path: Path) -> None:
    sides = [s | {"errors": 1} if s["side"] == "base" else s for s in PROOF["sides"]]
    old = {"ref": "v1.0", "false_positives": 0, "error": "boom"}
    proof = reproved(tmp_path, sides=sides, tree_error="boom", old_release=old)
    row = one_row(tmp_path, {"roots": {"widgets-9-1": "Inferred"}, "proof": proof})
    assert (row.marks["base"], row.marks["0 FP tree"]) == ("FAIL", "FAIL")
    assert row.marks["0 FP release"] == "FAIL"


def test_every_not_run_gate_says_why(tmp_path: Path) -> None:
    spec = {"roots": {"widgets-9-1": "Inferred"}, "proof": reproved(tmp_path)}
    row = one_row(tmp_path, spec)
    assert row.not_run == {
        "0 FP release": "no X.Y.Z release was tagged before the PR merged",
        "held-out": "no held-out set is committed for this PR",
    }


def test_the_grid_lists_every_not_run_reason(tmp_path: Path) -> None:
    spec = {"roots": {"widgets-9-1": "Inferred"}, "proof": reproved(tmp_path)}
    path = registry(tmp_path, {"9": spec})
    lines = grid_lines([path], {}, [log(tmp_path)])
    reason = "no X.Y.Z release was tagged before the PR merged"
    assert f"- acme/widgets #9 0 FP release: {reason}" in lines


def test_the_committed_grid_has_one_row_per_installed_rule() -> None:
    rows = grid_rows(REGISTRIES, {}, log_attempts(COMPILE_LOGS))
    assert len(rows) == 12
    blocking = sorted(f"{row.repo} #{row.pr}" for row in rows if row.tier == "block")
    assert blocking == ["apache/airflow #75025", "apache/airflow #75774"]


def test_every_committed_rule_was_reproved_and_every_not_run_is_explained() -> None:
    rows = grid_rows(REGISTRIES, {}, log_attempts(COMPILE_LOGS))
    assert all(row.source.startswith("knack reprove ") for row in rows)
    for row in rows:
        not_run = {g for g in GATES if row.marks[g] == "NOT RUN"} - {"held-out"}
        assert not_run == set(row.not_run) - {"held-out"}
        assert all(row.not_run.values())


def test_the_committed_proof_grid_file_is_current() -> None:
    # bench/PROOF-GRID.md is what reproduce.sh writes; it must match a fresh run.
    from knack.reproduce import grid_section, REPO_ROOT

    written = (REPO_ROOT / "bench" / "PROOF-GRID.md").read_text(encoding="utf-8")
    assert written == "\n".join(grid_section()) + "\n"
