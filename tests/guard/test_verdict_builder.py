from typing import Any

import pytest
from knack.contracts.models import DecisionStatus, Root
from knack.guard.runner import RuleMatch
from knack.guard.verdict_builder import build_verdict

RULE_ID = "no-alias-sort-keys"


def make_root(status: DecisionStatus = "Confirmed", **overrides: Any) -> Root:
    # Test-only root; values are illustrative, not quoted from a real thread.
    data: dict[str, Any] = {
        "id": "root-001",
        "title": "Sort keys are column names",
        "decision": "Sort keys must be real column names, never aliases.",
        "why": "Aliased sort keys let callers sort on columns they cannot see.",
        "decided_by": "Alice Chen",
        "source_url": "https://github.com/example/repo/pull/42",
        "quote": "Do not alias sort keys; map them to columns explicitly.",
        "status": status,
        "rejected_alternative": "Keep an alias table for sort keys.",
    }
    return Root.model_validate({**data, **overrides})


def make_matches() -> list[RuleMatch]:
    # Mirrors the runner's output on pre_fix.py: two keys on line 23.
    return [
        RuleMatch(rule_id=RULE_ID, file="pre_fix.py", line=23, matched_text='"state"'),
        RuleMatch(
            rule_id=RULE_ID, file="pre_fix.py", line=23, matched_text='"start_date"'
        ),
    ]


def test_no_matches_allows() -> None:
    verdict = build_verdict(RULE_ID, [], make_root(), 1.0)
    assert verdict.allowed is True


def test_confirmed_root_with_matches_denies_citing_rule_and_root() -> None:
    verdict = build_verdict(RULE_ID, make_matches(), make_root(), 1.0)
    assert verdict.allowed is False
    assert verdict.rule_id == RULE_ID
    assert verdict.root_ids == ["root-001"]


def test_deny_reason_cites_who_why_quote_source_and_rejected_alternative() -> None:
    verdict = build_verdict(RULE_ID, make_matches(), make_root(), 1.0)
    assert verdict.reason == (
        "Knack blocked this edit.\n"
        "Decision: Sort keys must be real column names, never aliases.\n"
        "Decided by: Alice Chen\n"
        "Why: Aliased sort keys let callers sort on columns they cannot see.\n"
        "Rejected alternative: Keep an alias table for sort keys.\n"
        'Quote: "Do not alias sort keys; map them to columns explicitly."\n'
        "Source: https://github.com/example/repo/pull/42\n"
        'Matched: "state" (line 23), "start_date" (line 23)'
    )


def test_deny_reason_omits_rejected_alternative_line_when_none() -> None:
    root = make_root(rejected_alternative=None)
    verdict = build_verdict(RULE_ID, make_matches(), root, 1.0)
    assert verdict.allowed is False
    assert "Rejected alternative" not in verdict.reason


def test_deny_reason_lists_each_matched_text_with_its_line() -> None:
    matches = [
        *make_matches(),
        RuleMatch(rule_id=RULE_ID, file="pre_fix.py", line=31, matched_text='"owner"'),
    ]
    verdict = build_verdict(RULE_ID, matches, make_root(), 1.0)
    assert verdict.reason.endswith(
        'Matched: "state" (line 23), "start_date" (line 23), "owner" (line 31)'
    )


def test_inferred_root_allows_with_advisory_reason() -> None:
    verdict = build_verdict(RULE_ID, make_matches(), make_root("Inferred"), 1.0)
    assert verdict.allowed is True
    assert verdict.reason.startswith("advisory:")


def test_unknown_root_allows_with_advisory_reason() -> None:
    verdict = build_verdict(RULE_ID, make_matches(), make_root("Unknown"), 1.0)
    assert verdict.allowed is True
    assert verdict.reason.startswith("advisory:")


def test_missing_root_allows_with_advisory_reason() -> None:
    verdict = build_verdict(RULE_ID, make_matches(), None, 1.0)
    assert verdict.allowed is True
    assert verdict.reason.startswith("advisory:")


def test_latency_ms_passes_through() -> None:
    verdict = build_verdict(RULE_ID, make_matches(), make_root(), 4.25)
    assert verdict.latency_ms == 4.25


@pytest.mark.parametrize("status", ["Corroborated", "Uncorroborated"])
def test_corroboration_statuses_never_deny(status: DecisionStatus) -> None:
    verdict = build_verdict(RULE_ID, make_matches(), make_root(status), 1.0)
    assert verdict.allowed is True
    assert verdict.reason.startswith("advisory:")
