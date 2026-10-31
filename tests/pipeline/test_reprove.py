import json
from pathlib import Path

import pytest
from conftest import (
    clean_tree,
    COMPLIANT,
    FakeGitHub,
    STRUCTURAL,
    VIOLATIONS,
    write_tree,
)
from knack import cli
from knack.contracts.models import RuleProof
from knack.pipeline.reprove import Reprove, reprove_registry
from knack.roots.pin import rule_sha
from knack.walk.registry import load_registry
from test_miss_loop import heldout, registry

STAMP = "2026-10-31T00:00:00Z"
BROKEN = "id: compiled-rule\nlanguage: python\nrule: {pattern: '$$$('}\n"
# PR #9 merged 2026-10-01; 0.115.0 is the last release tagged before it.
TAGS = {"0.116.0": "2026-10-02T00:00:00Z", "0.115.0": "2026-09-15T00:00:00Z"}


def variants(tmp_path: Path) -> Path:
    named = {f"9/violation_{i}.py": s for i, s in enumerate(VIOLATIONS, 1)}
    named |= {f"9/compliant_{i}.py": s for i, s in enumerate(COMPLIANT, 1)}
    return write_tree(tmp_path / "variants", named)


def reprove(
    tmp_path: Path, rule: str = STRUCTURAL, **kw: object
) -> tuple[RuleProof, list[str]]:
    # One rule, PR #9, proven again; returns its stored proof and the log.
    github = kw.get("github") or FakeGitHub(clean_tree(tmp_path))
    lines, reg = list[str](), registry(tmp_path, rule)
    held = kw["heldout"] if "heldout" in kw else heldout(tmp_path)
    found = kw["variants"] if "variants" in kw else variants(tmp_path)
    run = Reprove(github, reg, found, held, tmp_path / "work", lines.append, STAMP)
    reprove_registry(run)
    [entry] = load_registry(reg).rules
    assert entry.proof is not None
    return entry.proof, lines


def sides(proof: RuleProof) -> dict[str, tuple[int, int, int]]:
    return {s.side: (s.files, s.flagged, s.errors) for s in proof.sides}


def test_every_gate_is_run_again_and_stored_as_the_entry_proof(
    tmp_path: Path,
) -> None:
    proof, _ = reprove(tmp_path)
    assert sides(proof) == {
        "base": (1, 1, 0),
        "head": (2, 0, 0),
        "rename-base": (1, 1, 0),
        "rename-head": (2, 0, 0),
        "variant-violation": (3, 2, 0),
        "variant-compliant": (3, 0, 0),
    }
    assert (proof.pr, proof.base_sha, proof.head_sha) == (9, "base9", "head9")
    assert proof.false_positives == 0 and proof.tree_error is None


def test_both_held_out_sets_are_scored_and_stored(tmp_path: Path) -> None:
    proof, _ = reprove(tmp_path)
    scores = {
        k: (s.caught, s.violations, s.allowed, s.compliant)
        for k, s in proof.heldout_sets.items()
    }
    assert scores == {"same": (2, 3, 3, 3), "cross": (2, 3, 3, 3)}


def test_the_proof_pins_the_rule_text_it_ran_and_when(tmp_path: Path) -> None:
    proof, _ = reprove(tmp_path)
    rule = tmp_path / "registry" / "rules" / "9.yml"
    assert proof.rule_sha == rule_sha(rule) and proof.reproved_at == STAMP


def test_the_rule_is_never_recompiled(tmp_path: Path) -> None:
    reprove(tmp_path)
    rule = (tmp_path / "registry" / "rules" / "9.yml").read_text()
    assert rule == STRUCTURAL.replace("compiled-rule", "widgets-9")


def test_the_previous_release_must_stay_clean(tmp_path: Path) -> None:
    github = FakeGitHub(clean_tree(tmp_path))
    github.tag_names = TAGS
    old = {"pkg/old.py": VIOLATIONS[0]}
    github.old_trees = {"0.115.0": write_tree(tmp_path / "0.115.0", old)}
    proof, _ = reprove(tmp_path, github=github)
    assert github.refs_checked_out == ["0.115.0"]
    assert proof.old_release is not None
    assert (proof.old_release.ref, proof.old_release.false_positives) == ("0.115.0", 1)


def test_no_release_before_the_merge_is_not_run_and_says_why(tmp_path: Path) -> None:
    proof, _ = reprove(tmp_path)
    assert proof.old_release is None
    assert proof.not_run == {
        "0 FP release": "no X.Y.Z release was tagged before the PR merged (2026-10-01)"
    }


def test_missing_training_variants_are_not_run_and_named(tmp_path: Path) -> None:
    proof, _ = reprove(tmp_path, variants=tmp_path / "nowhere")
    assert "variant-violation" not in sides(proof)
    why = proof.not_run["variants"]
    assert why == proof.not_run["compliant"]
    assert why.startswith("no committed training variants at ") and "nowhere" in why


def test_install_layout_training_variants_are_found_too(tmp_path: Path) -> None:
    write_tree(
        tmp_path / "registry" / "work",
        {
            "9/variants/violation_1.py": VIOLATIONS[0],
            "9/variants/compliant_1.py": COMPLIANT[0],
        },
    )
    proof, _ = reprove(tmp_path, variants=tmp_path / "nowhere")
    assert sides(proof)["variant-violation"] == (1, 1, 0)


def test_a_missing_held_out_set_is_not_run_and_named(tmp_path: Path) -> None:
    held = heldout(tmp_path)
    for path in (held / "9" / "same").iterdir():
        path.unlink()
    (held / "9" / "same").rmdir()
    proof, _ = reprove(tmp_path, heldout=held)
    assert list(proof.heldout_sets) == ["cross"]
    assert proof.not_run["held-out"].startswith("no same held-out set at ")


def test_a_broken_rule_records_its_errors(tmp_path: Path) -> None:
    proof, lines = reprove(tmp_path, rule=BROKEN)
    assert sides(proof)["base"][2] == 1 and proof.tree_error
    assert proof.heldout_sets["same"].error
    assert any("ast-grep rejected the rule" in line for line in lines)


def test_the_registry_keeps_its_relative_paths(tmp_path: Path) -> None:
    reprove(tmp_path)
    body = json.loads((tmp_path / "registry" / "registry.json").read_text())
    assert body["roots_dir"] == "roots"
    assert body["rules"][0]["rule"] == "rules/9.yml"


def test_a_pr_that_cannot_be_fetched_keeps_its_old_proof(tmp_path: Path) -> None:
    class Offline(FakeGitHub):
        def summary(self, repo: str, number: int):  # type: ignore[no-untyped-def]
            raise OSError("network is down")

    github = Offline(clean_tree(tmp_path))
    lines, reg = list[str](), registry(tmp_path, STRUCTURAL)
    run = Reprove(
        github,
        reg,
        variants(tmp_path),
        heldout(tmp_path),
        tmp_path / "w",
        lines.append,
        STAMP,
    )
    assert reprove_registry(run) == ["widgets-9"]
    assert load_registry(reg).rules[0].proof is None
    assert any("widgets-9 not reproved: OSError: network is down" in l for l in lines)


def test_each_rule_reports_its_gates(tmp_path: Path) -> None:
    _, lines = reprove(tmp_path)
    assert "widgets-9: every gate run holds; not run: 0 FP release" in lines


def test_knack_reprove_writes_the_registry_and_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    github = FakeGitHub(clean_tree(tmp_path))
    monkeypatch.setattr(cli, "github_client", lambda: github)
    reg = registry(tmp_path, STRUCTURAL)
    places = [
        "--variants",
        str(variants(tmp_path)),
        "--heldout",
        str(heldout(tmp_path)),
    ]
    code = cli.main(
        ["reprove", "--registry", str(reg), *places, "--work", str(tmp_path / "w")]
    )
    assert code == 0 and load_registry(reg).rules[0].proof is not None
    assert f"wrote {reg}" in capsys.readouterr().out


def test_knack_reprove_without_a_token_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    code = cli.main(["reprove", "--registry", str(registry(tmp_path, STRUCTURAL))])
    assert code == 2 and "GITHUB_TOKEN" in capsys.readouterr().err


def test_knack_reprove_exits_1_when_a_rule_was_not_reproved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    github = FakeGitHub(clean_tree(tmp_path))
    github.summary = lambda repo, number: (_ for _ in ()).throw(OSError("down"))  # type: ignore[method-assign]
    monkeypatch.setattr(cli, "github_client", lambda: github)
    reg = registry(tmp_path, STRUCTURAL)
    assert (
        cli.main(["reprove", "--registry", str(reg), "--work", str(tmp_path / "w")])
        == 1
    )
