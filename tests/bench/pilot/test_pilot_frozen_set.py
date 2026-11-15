from pathlib import Path

from bench.pilot.candidates import leaked_terms, load_candidates
from bench.pilot.proof import prove_candidate

PILOT = Path(__file__).resolve().parents[3] / "bench" / "pilot"
CANDIDATES = load_candidates(PILOT / "candidates.jsonl")


def test_frozen_set_has_at_least_ten_unique_tickets() -> None:
    ids = [c.id for c in CANDIDATES]
    assert len(ids) >= 10 and len(set(ids)) == len(ids)
    assert len({c.base_sha for c in CANDIDATES}) == len(ids)


def test_every_frozen_rule_is_base_flag_head_allow_with_accepted_check() -> None:
    failed = [p for p in map(prove_candidate, CANDIDATES) if not p.proven]
    assert failed == []


def test_no_frozen_ticket_leaks_a_hint_term() -> None:
    assert {c.id: leaked_terms(c) for c in CANDIDATES if leaked_terms(c)} == {}
