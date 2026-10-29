from knack.contracts.models import DecisionStatus, Root
from knack.pipeline.models import Alternative, Decision, Extraction
from knack.pipeline.progress import extracted_line, roots_line


def extraction(decisions: int, alternatives: int) -> Extraction:
    rejected = [Alternative(alternative="a")] * alternatives
    first = Decision(decision="d", rejected_alternatives=rejected)
    others = [Decision(decision="d")] * (decisions - 1)
    return Extraction(number=75025, title="t", decisions=[first, *others][:decisions])


def test_one_of_each_is_singular() -> None:
    line = extracted_line(75025, extraction(1, 1))
    assert line == "  #75025: 1 decision, 1 rejected alternative"


def test_counts_other_than_one_are_plural() -> None:
    assert extracted_line(75025, extraction(2, 0)) == (
        "  #75025: 2 decisions, 0 rejected alternatives"
    )
    assert extracted_line(7, extraction(0, 0)).endswith(
        ": 0 decisions, 0 rejected alternatives"
    )


def test_alternatives_count_across_every_decision() -> None:
    both = extraction(1, 2)
    assert extracted_line(1, both).endswith("2 rejected alternatives")


def test_failed_pr_says_so() -> None:
    assert extracted_line(2, None) == "  #2: failed"


def labelled(status: DecisionStatus) -> Root:
    fields = {"id": "r", "title": "t", "decision": "d", "why": "w", "decided_by": "b"}
    fields |= {"source_url": "https://github.com/a/b/pull/1", "quote": "q"}
    return Root.model_validate({**fields, "status": status})


def test_roots_line_without_corroboration_counts_inferred() -> None:
    kept = [labelled("Confirmed")]
    assert roots_line([labelled("Inferred")], kept) == (
        "[3/5] roots    1 Inferred roots written (1 Confirmed, 0 Unknown kept)"
    )


def test_roots_line_with_corroboration_counts_both_labels() -> None:
    written = [
        labelled("Corroborated"),
        labelled("Uncorroborated"),
        labelled("Uncorroborated"),
    ]
    assert roots_line(written, [], corroborating=True) == (
        "[3/5] roots    3 roots written: 1 corroborated, 2 uncorroborated, 0 Inferred"
        " (0 Confirmed, 0 Unknown kept)"
    )
