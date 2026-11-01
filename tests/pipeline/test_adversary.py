import json
from pathlib import Path

from conftest import (
    clean_tree,
    FakeAdversary,
    FakeGitHub,
    FakeSpark,
    HELDOUT_COMPLIANT,
    HELDOUT_VIOLATIONS,
    MEMORIZED,
    REPO,
    STRUCTURAL,
    VARIANTS,
)
from knack.pipeline.init import run_init
from knack.pipeline.variants import variant_authors

WORK = Path("out") / "work" / "9"


def init(
    tmp_path: Path, adversary: FakeAdversary | None, *rules: str
) -> tuple[list[str], FakeSpark]:
    lines, spark = list[str](), FakeSpark(list(rules or [STRUCTURAL]))
    github = FakeGitHub(clean_tree(tmp_path))
    run_init(
        REPO, 50, tmp_path / "out", github, spark, lines.append, adversary=adversary
    )
    return lines, spark


def variant_prompts(prompts: list[str]) -> list[str]:
    return [p for p in prompts if p.startswith("You write test cases")]


def test_the_adversary_writes_every_variant_and_the_compiler_none(
    tmp_path: Path,
) -> None:
    adversary = FakeAdversary()
    _, spark = init(tmp_path, adversary)
    assert variant_prompts(spark.prompts) == []
    assert len(variant_prompts(adversary.prompts)) == 2


def test_each_variant_records_the_model_that_wrote_it(tmp_path: Path) -> None:
    init(tmp_path, FakeAdversary())
    for folder in ("variants", "variants-heldout"):
        authors = variant_authors(tmp_path / WORK / folder)
        assert len(authors) == 6 and set(authors.values()) == {"fake-adversary"}


def test_without_an_adversary_the_compiler_writes_variants_and_a_warning_is_logged(
    tmp_path: Path,
) -> None:
    lines, spark = init(tmp_path, None)
    assert len(variant_prompts(spark.prompts)) == 2
    assert set(variant_authors(tmp_path / WORK / "variants").values()) == {"fake-spark"}
    assert (
        "  warning: variants written by fake-spark, the compiler itself; "
        "no cross-model adversary"
    ) in lines


def test_a_cross_model_adversary_is_named_in_the_log(tmp_path: Path) -> None:
    lines, _ = init(tmp_path, FakeAdversary())
    assert "  adversary: fake-adversary writes variants, fake-spark compiles" in lines
    assert not any("warning" in line for line in lines)


def test_the_heldout_set_is_never_shown_to_the_compiler(tmp_path: Path) -> None:
    # MEMORIZED fails first, so a retry carries the training variants' source back.
    _, spark = init(tmp_path, FakeAdversary(), MEMORIZED, STRUCTURAL)
    compiles = spark.compile_prompts()
    assert len(compiles) == 2 and "FLAGGED COMPLIANT CODE" in compiles[1]
    assert not any("_heldout" in prompt for prompt in compiles)
    heldout = (tmp_path / WORK / "variants-heldout" / "violation_1.py").read_text()
    assert "sip_heldout" in heldout


def test_heldout_pass_rate_is_reported_per_rule(tmp_path: Path) -> None:
    lines, _ = init(tmp_path, FakeAdversary())
    at = lines.index("  #9 proven on attempt 1")
    assert lines[at + 1] == (
        "  #9 held-out by fake-adversary: 2/3 violations caught, "
        "3/3 compliant allowed (pass)"
    )


def test_a_heldout_set_too_hard_for_the_rule_fails_but_keeps_the_rule(
    tmp_path: Path,
) -> None:
    # The held-out "violations" are compliant loops, so none is caught.
    loops = json.loads(VARIANTS)["compliant"]
    hard = json.dumps({"violations": loops, "compliant": loops})
    lines, _ = init(tmp_path, FakeAdversary(VARIANTS, hard))
    assert "  #9 held-out by fake-adversary: 0/3 violations caught, " in "\n".join(
        lines
    )
    assert "3/3 compliant allowed (fail)" in "\n".join(lines)
    assert (tmp_path / "out" / "rules" / "9.yml").exists()


def test_a_heldout_writer_failure_is_not_run_and_discards_the_rule(
    tmp_path: Path,
) -> None:
    # The miss loop's bar: a held-out set that never ran proves nothing.
    lines, _ = init(tmp_path, FakeAdversary(VARIANTS, "no json", "no", "no"))
    held = [line for line in lines if line.startswith("  #9 held-out")]
    assert held == [held[0]] and held[0].startswith("  #9 held-out: not run (")
    assert discarded(lines).startswith(
        "  #9 discarded after 1 attempts: held-out: not run ("
    )
    assert_discarded(tmp_path, lines)


def test_a_flagged_heldout_compliant_file_discards_the_rule(tmp_path: Path) -> None:
    # A gather among the "compliant" files: the rule flags it, so 2/3 allowed.
    lines, _ = init(tmp_path, FakeAdversary(VARIANTS, flagged_heldout()))
    assert discarded(lines) == (
        "  #9 discarded after 1 attempts: held-out: 2/3 compliant allowed "
        "(every held-out compliant file must be allowed)"
    )
    assert_discarded(tmp_path, lines)


def test_a_heldout_discard_keeps_its_score_in_the_log(tmp_path: Path) -> None:
    lines, _ = init(tmp_path, FakeAdversary(VARIANTS, flagged_heldout()))
    text = "\n".join(lines)
    assert "  #9 held-out by fake-adversary: 2/3 violations caught, " in text
    assert "2/3 compliant allowed (fail)" in text


def flagged_heldout() -> str:
    compliant = HELDOUT_COMPLIANT[:2] + [HELDOUT_VIOLATIONS[0]]
    return json.dumps({"violations": HELDOUT_VIOLATIONS, "compliant": compliant})


def discarded(lines: list[str]) -> str:
    return next(line for line in lines if line.startswith("  #9 discarded"))


def assert_discarded(tmp_path: Path, lines: list[str]) -> None:
    out = tmp_path / "out"
    assert not (out / "rules" / "9.yml").exists()
    assert json.loads((out / "registry.json").read_text())["rules"] == []
    assert "0 rules proven, 1 discarded, 0 in registry" in "\n".join(lines)


def test_a_discarded_rule_gets_no_heldout_set(tmp_path: Path) -> None:
    lines, _ = init(tmp_path, FakeAdversary(), MEMORIZED)
    assert not any("held-out" in line for line in lines)
    assert not (tmp_path / WORK / "variants-heldout").exists()
