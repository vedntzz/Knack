import json
import subprocess
from pathlib import Path

import pytest
from conftest import BASE
from knack.miss.cases import CaseKind, EditCase, load_cases, save_case
from knack.miss.sources import MissSourceError, Places, resolve_source
from knack.receipts.chain import append_receipt
from knack.receipts.edits import EditSnapshot, save_edit

SHA = "a" * 40
AFTER = BASE.replace("return results", "return list(results)")
TICKET = {
    "id": "acme-9",
    "repo": "acme/widgets",
    "pr": 9,
    "base_sha": SHA,
    "files": ["pkg/loader.py"],
    "rule": "widgets-9",
    "fix_functions": ["load"],
    "ticket": "Loading opens every blob at once.",
}


class BaseOnlyGitHub:
    # Serves the ticket's base file and nothing else.
    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        return BASE if (sha, path) == (SHA, "pkg/loader.py") else None


def places(tmp_path: Path) -> Places:
    runs = tmp_path / "runs.jsonl"
    return Places(
        receipts=tmp_path / "verdicts.jsonl",
        edits=tmp_path / "edits",
        runs=[runs],
        tickets=tmp_path / "tickets.jsonl",
    )


def resolve(
    tmp_path: Path, source: str, kind: CaseKind = "must-fail"
) -> list[EditCase]:
    return resolve_source(source, kind, places(tmp_path), BaseOnlyGitHub())


def receipt(tmp_path: Path, decision: str, edit: str | None) -> str:
    fields = {"time": "t", "repo": "acme/widgets", "file": str(tmp_path / "x.py")}
    fields |= {"rule_id": "widgets-9", "root_ids": [], "decision": decision}
    fields |= {"quote_sha256": None, "latency_ms": 1.0}
    later = {"edit_sha256": edit} if edit else {}
    return append_receipt(places(tmp_path).receipts, fields | later).hash


def snapshot(tmp_path: Path) -> str:
    edit = EditSnapshot(file=str(tmp_path / "x.py"), before=BASE, after=AFTER)
    return save_edit(places(tmp_path).edits, edit)


def test_an_edit_json_becomes_one_case(tmp_path: Path) -> None:
    path = tmp_path / "edit.json"
    edit = {"rule_id": "widgets-9", "file": "pkg/loader.py", "before": BASE}
    path.write_text(json.dumps(edit | {"after": AFTER, "note": "rebuilt"}))
    [case] = resolve(tmp_path, str(path))
    assert (case.kind, case.rule_id, case.file) == (
        "must-fail",
        "widgets-9",
        "pkg/loader.py",
    )
    assert (case.before, case.after, case.note) == (BASE, AFTER, "rebuilt")
    assert case.source == f"edit {path}"


def test_an_allowed_receipt_becomes_a_must_fail_case(tmp_path: Path) -> None:
    digest = receipt(tmp_path, "allow", snapshot(tmp_path))
    [case] = resolve(tmp_path, digest)
    assert (case.kind, case.rule_id) == ("must-fail", "widgets-9")
    assert (case.before, case.after, case.file) == (BASE, AFTER, "x.py")
    assert case.source == f"receipt {digest}"


def test_a_denied_receipt_becomes_a_must_pass_case(tmp_path: Path) -> None:
    digest = receipt(tmp_path, "deny", snapshot(tmp_path))
    [case] = resolve(tmp_path, digest, "must-pass")
    assert case.kind == "must-pass" and case.after == AFTER


def test_a_miss_on_a_denied_receipt_is_refused(tmp_path: Path) -> None:
    digest = receipt(tmp_path, "deny", snapshot(tmp_path))
    with pytest.raises(MissSourceError, match="was a deny"):
        resolve(tmp_path, digest)


def test_a_false_block_on_an_allowed_receipt_is_refused(tmp_path: Path) -> None:
    digest = receipt(tmp_path, "allow", snapshot(tmp_path))
    with pytest.raises(MissSourceError, match="was a allow"):
        resolve(tmp_path, digest, "must-pass")


def test_a_receipt_without_a_snapshot_is_refused(tmp_path: Path) -> None:
    digest = receipt(tmp_path, "allow", None)
    with pytest.raises(MissSourceError, match="no edit snapshot"):
        resolve(tmp_path, digest)


def test_a_human_allow_is_never_a_miss(tmp_path: Path) -> None:
    # A person allowed this edit after ESCALATE; teaching the rule to deny it undoes them.
    resolution = {"of": "d" * 64, "action": "allow", "by": "maria", "reason": "ok"}
    fields = {"time": "t", "repo": "acme/widgets", "file": str(tmp_path / "x.py")}
    fields |= {"rule_id": "widgets-9", "root_ids": [], "decision": "allow"}
    fields |= {
        "quote_sha256": None,
        "latency_ms": 0.0,
        "edit_sha256": snapshot(tmp_path),
    }
    digest = append_receipt(
        places(tmp_path).receipts, fields | {"resolution": resolution}
    ).hash
    with pytest.raises(MissSourceError, match="allowed by maria"):
        resolve(tmp_path, digest)


def test_an_unknown_receipt_hash_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MissSourceError, match="no receipt"):
        resolve(tmp_path, "b" * 64)


def write_run(tmp_path: Path, diff: Path, artifacts: Path | None = None) -> None:
    run = {"run_id": "r1", "ticket": "acme-9", "repo": "acme/widgets"}
    run |= {"rule": "widgets-9", "diff_path": str(diff)}
    run |= {"artifacts_path": str(artifacts)} if artifacts else {}
    places(tmp_path).runs[0].write_text(json.dumps(run) + "\n")
    places(tmp_path).tickets.write_text(json.dumps(TICKET) + "\n")


def real_diff(tmp_path: Path) -> Path:
    # A git diff of the ticket file, as the bench writes it.
    for name, text in (("a", BASE), ("b", AFTER)):
        (tmp_path / name / "pkg").mkdir(parents=True)
        (tmp_path / name / "pkg" / "loader.py").write_text(text)
    args = ["git", "diff", "--no-index", "a/pkg/loader.py", "b/pkg/loader.py"]
    done = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)
    diff = tmp_path / "diff.patch"
    diff.write_text(done.stdout.replace("a/a/", "a/").replace("b/b/", "b/"))
    return diff


def test_a_bench_run_becomes_a_case_from_its_ticket_base_and_diff(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, real_diff(tmp_path))
    [case] = resolve(tmp_path, "r1")
    assert (case.rule_id, case.file) == ("widgets-9", "pkg/loader.py")
    assert (case.before, case.after, case.source) == (BASE, AFTER, "bench run r1")


def test_a_bench_run_whose_diff_is_gone_is_refused(tmp_path: Path) -> None:
    write_run(tmp_path, tmp_path / "gone" / "diff.patch")
    with pytest.raises(MissSourceError, match="diff .* is gone"):
        resolve(tmp_path, "r1")


def kept_artifacts(tmp_path: Path) -> Path:
    # The bench run's artifacts folder, holding the final diff.
    kept = tmp_path / "artifacts" / "r1"
    kept.mkdir(parents=True)
    real_diff(tmp_path).rename(kept / "diff.patch")
    return kept


def test_a_bench_run_resolves_from_its_artifacts_once_the_work_is_gone(
    tmp_path: Path,
) -> None:
    write_run(tmp_path, tmp_path / "gone" / "diff.patch", kept_artifacts(tmp_path))
    [case] = resolve(tmp_path, "r1")
    assert (case.before, case.after, case.source) == (BASE, AFTER, "bench run r1")


def test_an_artifacts_diff_wins_over_the_work_diff(tmp_path: Path) -> None:
    kept = kept_artifacts(tmp_path)
    stale = tmp_path / "stale.patch"
    stale.write_text("not a diff\n")
    write_run(tmp_path, stale, kept)
    [case] = resolve(tmp_path, "r1")
    assert case.after == AFTER


def test_a_bench_run_whose_artifacts_are_gone_names_them(tmp_path: Path) -> None:
    gone = tmp_path / "artifacts" / "r1"
    write_run(tmp_path, tmp_path / "gone" / "diff.patch", gone)
    with pytest.raises(MissSourceError, match=f"{gone}.*is gone"):
        resolve(tmp_path, "r1")


def test_an_unknown_run_id_is_refused(tmp_path: Path) -> None:
    write_run(tmp_path, tmp_path / "diff.patch")
    with pytest.raises(MissSourceError, match="not a receipt hash, bench run id"):
        resolve(tmp_path, "r2")


def test_saved_cases_load_back_by_rule(tmp_path: Path) -> None:
    case = EditCase(
        kind="must-pass",
        rule_id="widgets-9",
        file="a.py",
        before=None,
        after="x = 1\n",
        source="edit e.json",
    )
    save_case(tmp_path, case)
    save_case(tmp_path, case)
    assert load_cases(tmp_path, "widgets-9") == [case]
    assert load_cases(tmp_path, "widgets-8") == []
