import json
from pathlib import Path

from conftest import (
    BASE,
    clean_tree,
    FakeGitHub,
    FakeSpark,
    HEAD,
    MEMORIZED,
    REPO,
    STRUCTURAL,
)
from knack.hooks.pretool_guard import decide
from knack.pipeline.init import run_init
from knack.roots.store import load_roots
from knack.walk.registry import load_registry


def init(tmp_path: Path, *rules: str) -> tuple[Path, list[str], FakeSpark]:
    lines, spark = list[str](), FakeSpark(list(rules))
    github = FakeGitHub(clean_tree(tmp_path))
    path = run_init(REPO, 50, tmp_path / "out", github, spark, lines.append)
    return path, lines, spark


def write_event(content: str, cwd: Path) -> dict[str, object]:
    tool_input = {"path": "pkg/loader.py", "content": content}
    return {"tool_name": "write_file", "tool_input": tool_input, "cwd": str(cwd)}


def test_init_installs_one_proven_rule_with_its_inferred_root(tmp_path: Path) -> None:
    path, _, _ = init(tmp_path, MEMORIZED, STRUCTURAL)
    registry = load_registry(path)
    assert path == tmp_path / "out" / "registry.json" and registry.repo == REPO
    assert [(e.rule.name, e.root_ids) for e in registry.rules] == [
        ("9.yml", ["widgets-9-1"])
    ]
    assert registry.rules[0].rule.read_text().startswith("id: widgets-9\n")
    assert [(r.id, r.status) for r in load_roots(registry.roots_dir)] == [
        ("widgets-9-1", "Inferred")
    ]


def test_progress_log_reports_every_stage(tmp_path: Path) -> None:
    path, lines, _ = init(tmp_path, MEMORIZED, STRUCTURAL)
    log = "\n".join(lines)
    assert "[1/5] select" in log and "8 PRs read, 4 kept" in log
    assert "[2/5] extract" in log and "3 decisions found" in log
    assert "2 rejected alternatives (1 verbatim)" in log and "1 failed: #2" in log
    assert "[3/5] roots" in log and "1 Inferred roots written" in log
    assert "#9 proven on attempt 2" in log
    assert "[5/5] install" in log and "1 rules proven, 0 discarded" in log
    assert lines[-1].endswith(str(path))


def test_extract_prints_one_line_per_pr_between_header_and_totals(
    tmp_path: Path,
) -> None:
    _, lines, _ = init(tmp_path, STRUCTURAL)
    start = lines.index("[2/5] extract  reading 4 PRs")
    assert lines[start + 1 : start + 6] == [
        "  #9: 1 decision, 1 rejected alternative",
        "  #4: 1 decision, 0 rejected alternatives",
        "  #3: 1 decision, 1 rejected alternative",
        "  #2: failed",
        "  3 decisions found, 2 rejected alternatives (1 verbatim), 1 failed: #2",
    ]
    assert lines[start + 6].startswith("[3/5] roots")


def test_only_prs_with_a_verbatim_rejection_are_compiled(tmp_path: Path) -> None:
    _, _, spark = init(tmp_path, STRUCTURAL)
    compiles = spark.compile_prompts()
    assert len(compiles) == 1 and "Read blobs one at a time in a loop" in compiles[0]


def test_unprovable_rule_is_discarded_and_not_registered(tmp_path: Path) -> None:
    path, lines, _ = init(tmp_path, MEMORIZED)
    log = "\n".join(lines)
    discarded = "#9 discarded after 5 attempts: head, rename-head, variant-compliant"
    assert f"{discarded}, 1 false positives on the default branch" in log
    assert "0 rules proven, 1 discarded" in log
    assert load_registry(path).rules == []
    assert not (tmp_path / "out" / "rules" / "9.yml").exists()


def test_rerun_keeps_a_root_a_human_confirmed(tmp_path: Path) -> None:
    path, _, _ = init(tmp_path, STRUCTURAL)
    root_file = tmp_path / "out" / "roots" / "widgets-9-1.json"
    confirmed = {**json.loads(root_file.read_text()), "status": "Confirmed"}
    root_file.write_text(json.dumps(confirmed))
    _, lines, _ = init(tmp_path, STRUCTURAL)
    assert load_roots(load_registry(path).roots_dir)[0].status == "Confirmed"
    assert "0 Inferred roots written (1 Confirmed kept)" in "\n".join(lines)


def test_guard_hook_only_advises_on_an_inferred_init_registry(tmp_path: Path) -> None:
    registry = load_registry(init(tmp_path, STRUCTURAL)[0])
    log = tmp_path / "guard.log"
    assert decide(write_event(BASE, tmp_path), registry, log) is None
    assert not log.exists()


def test_guard_hook_blocks_once_a_human_confirms_the_root(tmp_path: Path) -> None:
    registry = load_registry(init(tmp_path, STRUCTURAL)[0])
    root_file = registry.roots_dir / "widgets-9-1.json"
    root_file.write_text(root_file.read_text().replace('"Inferred"', '"Confirmed"'))
    denied = decide(write_event(BASE, tmp_path), registry, tmp_path / "guard.log")
    assert denied is not None
    reason = denied["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Read blobs one at a time in a loop" in reason and "pull/9" in reason
    assert decide(write_event(HEAD, tmp_path), registry, tmp_path / "guard.log") is None
