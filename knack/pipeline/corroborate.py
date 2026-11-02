import re

from knack.contracts.models import FoundBy, Root
from knack.pipeline.calls import found_by
from knack.pipeline.models import Alternative, Extraction
from knack.pipeline.roots import (
    extracted_by,
    labelled_roots,
    Labels,
    Pair,
    roots_for,
    verbatim_pairs,
)

WORD = re.compile(r"\w+")
# A shared quote shorter than this is too common to show two readings agree.
MIN_QUOTE_WORDS = 4
# (the primary extractor, the second reading's corroborator)
Finders = tuple[FoundBy, FoundBy]


def corroborated_roots(
    repo: str, extraction: Extraction, other: Extraction | None
) -> list[Root]:
    # Without a second reading Spark Open never ran here, so roots stay Inferred.
    if other is None:
        return roots_for(repo, extraction)
    both = (extracted_by(extraction), found_by(other.call, "corroborated"))
    ours = _labelled(verbatim_pairs(extraction), other, both[0], both)
    theirs = _labelled(_only_theirs(extraction, other), extraction, both[1], both)
    return labelled_roots(repo, extraction, ours + theirs)


def same_alternative(ours: Alternative, theirs: Alternative) -> bool:
    # The same alternative text once normalized, or overlapping verbatim quotes.
    text = _words(ours.alternative)
    if text and text == _words(theirs.alternative):
        return True
    both = ours.verbatim and theirs.verbatim
    return both and _quotes_overlap(ours.quote, theirs.quote)


def _only_theirs(ours: Extraction, other: Extraction) -> list[Pair]:
    # The second reading's verbatim finds that none of our roots already stands for.
    mine = [alternative for _, alternative in verbatim_pairs(ours)]
    found = verbatim_pairs(other)
    return [p for p in found if not any(same_alternative(p[1], a) for a in mine)]


def _labelled(
    pairs: list[Pair], other: Extraction, finder: FoundBy, both: Finders
) -> list[tuple[Pair, Labels]]:
    # finder is the model whose reading these pairs came from.
    return [(pair, _labels(pair, other, finder, both)) for pair in pairs]


def _labels(pair: Pair, other: Extraction, finder: FoundBy, both: Finders) -> Labels:
    if _found_in(pair[1], other):
        return {"status": "Corroborated", "models": list(both)}
    return {"status": "Uncorroborated", "models": [finder]}


def _found_in(alternative: Alternative, extraction: Extraction) -> bool:
    found = [a for d in extraction.decisions for a in d.rejected_alternatives]
    return any(same_alternative(alternative, a) for a in found)


def _quotes_overlap(ours: str, theirs: str) -> bool:
    # One quote holds the other on whole words, and the shorter is long enough to count.
    short, long = sorted((_words(ours), _words(theirs)), key=len)
    if len(short) < MIN_QUOTE_WORDS:
        return False
    return f" {' '.join(short)} " in f" {' '.join(long)} "


def _words(text: str) -> list[str]:
    return WORD.findall(text.casefold())
