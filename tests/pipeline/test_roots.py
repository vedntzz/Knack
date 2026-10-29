from collections.abc import Mapping
from pathlib import Path

from conftest import GATHER_DECISION, INVENTED, QUOTE
from knack.contracts.models import Root
from knack.pipeline.extract import mark_verbatim
from knack.pipeline.models import Decision, Extraction
from knack.pipeline.roots import install_roots, roots_for
from knack.roots.store import load_roots, write_root

REPO = "acme/widgets"


def extraction(*decisions: Mapping[str, object]) -> Extraction:
    parsed = mark_verbatim([Decision.model_validate(d) for d in decisions], QUOTE)
    return Extraction(number=9, title="Read blobs", decisions=parsed)


def test_one_inferred_root_per_verbatim_rejected_alternative() -> None:
    roots = roots_for(REPO, extraction(GATHER_DECISION, INVENTED), "spark-x")
    assert [root.id for root in roots] == ["widgets-9-1"]
    root = roots[0]
    assert (root.status, root.seeded, root.model) == ("Inferred", False, "spark-x")
    assert str(root.source_url) == "https://github.com/acme/widgets/pull/9"
    assert (root.quote, root.decided_by) == (QUOTE, "maria")
    assert root.rejected_alternative == "asyncio.gather over every read"


def test_root_numbers_run_across_the_pr() -> None:
    roots = roots_for(REPO, extraction(GATHER_DECISION, GATHER_DECISION), "m")
    assert [root.id for root in roots] == ["widgets-9-1", "widgets-9-2"]


def test_install_writes_roots_the_store_can_load(tmp_path: Path) -> None:
    roots = roots_for(REPO, extraction(GATHER_DECISION), "m")
    assert install_roots(roots, tmp_path) == roots
    assert load_roots(tmp_path) == roots


def test_install_never_replaces_a_confirmed_root(tmp_path: Path) -> None:
    inferred = roots_for(REPO, extraction(GATHER_DECISION), "m")[0]
    confirmed = inferred.model_copy(update={"status": "Confirmed", "why": "human"})
    write_root(confirmed, tmp_path / "widgets-9-1.json")
    assert install_roots([inferred], tmp_path) == []
    assert load_roots(tmp_path) == [confirmed]


def test_install_never_replaces_a_rejected_root(tmp_path: Path) -> None:
    inferred = roots_for(REPO, extraction(GATHER_DECISION), "m")[0]
    rejected = inferred.model_copy(update={"status": "Unknown"})
    write_root(rejected, tmp_path / "widgets-9-1.json")
    assert install_roots([inferred], tmp_path) == []
    assert load_roots(tmp_path) == [rejected]


def test_install_refreshes_an_older_inferred_root(tmp_path: Path) -> None:
    fresh = roots_for(REPO, extraction(GATHER_DECISION), "m")[0]
    stale: Root = fresh.model_copy(update={"why": "older run"})
    write_root(stale, tmp_path / "widgets-9-1.json")
    install_roots([fresh], tmp_path)
    assert load_roots(tmp_path) == [fresh]
