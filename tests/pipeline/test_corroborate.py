import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from conftest import (
    BASE,
    clean_tree,
    EXTRACTIONS,
    FakeGitHub,
    FakeSpark,
    GATHER_DECISION,
    QUOTE,
    REPO,
    REVIEW,
    STRUCTURAL,
)
from knack.hooks.pretool_guard import decide
from knack.pipeline.corroborate import corroborated_roots, same_alternative
from knack.pipeline.extract import mark_verbatim
from knack.pipeline.init import run_init
from knack.pipeline.models import Alternative, Decision, Extraction
from knack.roots.store import load_roots
from knack.walk.registry import load_registry
from test_init import write_event

MODELS = ("fake-spark", "fake-spark-open")


def alternative(text: str, quote: str) -> dict[str, str]:
    return {"alternative": text, "why_rejected": "r", "quote": quote}


def decision_with(*alternatives: dict[str, str]) -> dict[str, object]:
    return {**GATHER_DECISION, "rejected_alternatives": list(alternatives)}


def extraction(*decisions: Mapping[str, object]) -> Extraction:
    parsed = mark_verbatim([Decision.model_validate(d) for d in decisions], REVIEW)
    return Extraction(number=9, title="Read blobs", decisions=parsed)


PRIMARY = extraction(GATHER_DECISION)
SAME_TEXT = alternative("Asyncio.gather -- over EVERY read!", "we hit the fd limit")
SAME_QUOTE = alternative("fan out reads", f"Please don't: {QUOTE}")
OTHER = alternative("one thread per blob", "we hit the fd limit")


def statuses(other: Extraction | None) -> list[tuple[str, str, list[str]]]:
    roots = corroborated_roots(REPO, PRIMARY, other, MODELS)
    return [(r.id, r.status, r.models) for r in roots]


def test_same_alternative_text_after_normalizing_is_corroborated() -> None:
    assert statuses(extraction(decision_with(SAME_TEXT))) == [
        ("widgets-9-1", "Corroborated", ["fake-spark", "fake-spark-open"])
    ]


def test_overlapping_verbatim_quotes_are_corroborated() -> None:
    assert statuses(extraction(decision_with(SAME_QUOTE))) == [
        ("widgets-9-1", "Corroborated", ["fake-spark", "fake-spark-open"])
    ]


def test_an_alternative_found_by_one_extractor_only_is_uncorroborated() -> None:
    assert statuses(extraction(decision_with(OTHER))) == [
        ("widgets-9-1", "Uncorroborated", ["fake-spark"]),
        ("widgets-9-2", "Uncorroborated", ["fake-spark-open"]),
    ]


def test_a_second_reading_that_failed_leaves_roots_inferred() -> None:
    assert statuses(None) == [("widgets-9-1", "Inferred", ["fake-spark"])]


def test_a_quote_shorter_than_four_words_never_corroborates() -> None:
    ours = Alternative(alternative="a", quote=QUOTE, verbatim=True)
    theirs = Alternative(alternative="b", quote="every blob", verbatim=True)
    assert not same_alternative(ours, theirs)


def test_quotes_overlap_only_when_both_are_verbatim() -> None:
    ours = Alternative(alternative="a", quote=QUOTE, verbatim=True)
    theirs = Alternative(alternative="b", quote=QUOTE, verbatim=False)
    assert not same_alternative(ours, theirs)


def test_quotes_overlap_on_whole_words_only() -> None:
    ours = Alternative(
        alternative="a", quote="recreate the cache on boot", verbatim=True
    )
    theirs = Alternative(alternative="b", quote="ate the cache on boot", verbatim=True)
    assert not same_alternative(ours, theirs)


class FakeSparkOpen(FakeSpark):
    # The second extractor: its own model id and its own reading of each PR.
    model = "fake-spark-open"

    def __init__(self, readings: dict[str, str]) -> None:
        super().__init__([STRUCTURAL])
        self.readings = readings

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return next(a for t, a in self.readings.items() if f"Title: {t}\n" in prompt)


def reading(*alternatives: dict[str, str]) -> dict[str, str]:
    answer = json.dumps({"decisions": [decision_with(*alternatives)]})
    return {**EXTRACTIONS, "Read blobs one at a time": answer}


def corroborate(tmp_path: Path, readings: dict[str, str]) -> tuple[Path, list[str]]:
    lines, second = list[str](), FakeSparkOpen(readings)
    github, spark = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    out = tmp_path / "out"
    path = run_init(REPO, 50, out, github, spark, lines.append, second=second)
    return path, lines


def roots_on_disk(path: Path) -> list[tuple[str, str]]:
    return [(r.id, r.status) for r in load_roots(load_registry(path).roots_dir)]


def test_init_corroborate_writes_corroborated_roots(tmp_path: Path) -> None:
    path, lines = corroborate(tmp_path, reading(SAME_TEXT))
    assert roots_on_disk(path) == [("widgets-9-1", "Corroborated")]
    log = "\n".join(lines)
    assert "1 corroborated, 0 uncorroborated" in log
    assert "second reading by fake-spark-open" in log


def test_init_corroborate_counts_uncorroborated_roots(tmp_path: Path) -> None:
    path, lines = corroborate(tmp_path, reading(OTHER))
    assert roots_on_disk(path) == [
        ("widgets-9-1", "Uncorroborated"),
        ("widgets-9-2", "Uncorroborated"),
    ]
    assert "0 corroborated, 2 uncorroborated" in "\n".join(lines)


def test_the_rule_cites_every_root_of_the_compiled_decision(tmp_path: Path) -> None:
    # The second reading's own root states the same decision, so the rule cites it too.
    path, _ = corroborate(tmp_path, reading(OTHER))
    entries = [(e.rule.name, e.root_ids) for e in load_registry(path).rules]
    assert entries == [("9.yml", ["widgets-9-1", "widgets-9-2"])]


@pytest.mark.parametrize("status", ["Confirmed", "Unknown"])
def test_corroborate_never_overwrites_a_reviewed_root(
    tmp_path: Path, status: str
) -> None:
    path, _ = corroborate(tmp_path, reading(OTHER))
    root_file = load_registry(path).roots_dir / "widgets-9-1.json"
    reviewed = {**json.loads(root_file.read_text()), "status": status, "why": "human"}
    root_file.write_text(json.dumps(reviewed))
    corroborate(tmp_path, reading(SAME_TEXT))
    assert json.loads(root_file.read_text()) == reviewed


@pytest.mark.parametrize("answer", [reading(SAME_TEXT), reading(OTHER)])
def test_guard_never_denies_on_a_corroborated_or_uncorroborated_root(
    tmp_path: Path, answer: dict[str, str]
) -> None:
    registry = load_registry(corroborate(tmp_path, answer)[0])
    assert decide(write_event(BASE, tmp_path), registry, tmp_path / "g.log") is None
