import json
from pathlib import Path

import pytest
from bench.pilot.candidates import (
    file_sha256,
    leaked_terms,
    load_candidates,
    PilotCandidate,
    ticket_sha256,
)
from pydantic import ValidationError


def candidate_fields(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "id": "demo-1",
        "repo": "acme/demo",
        "pr": 1,
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "files": ["pkg/worker.py"],
        "rejected_path": "Block the loop with time.sleep",
        "why_naive": "The author's first commit did it",
        "evidence_url": "https://github.com/acme/demo/pull/1#discussion_r1",
        "evidence_quote": "please don't block the loop",
        "accepted_fix": "await asyncio.sleep",
        "ticket": "The poller hammers the API with no pause between requests.",
        "rule": "demo-1.yml",
        "accepted_rule": "demo-1.accepted.yml",
        "leak_terms": ["sleep", "asyncio"],
    }
    return fields | overrides


def test_load_candidates_reads_every_jsonl_line(tmp_path: Path) -> None:
    path = tmp_path / "candidates.jsonl"
    lines = [candidate_fields(), candidate_fields(id="demo-2", pr=2)]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert [c.id for c in load_candidates(path)] == ["demo-1", "demo-2"]


def test_candidate_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PilotCandidate.model_validate(candidate_fields(hint="use asyncio"))


def test_ticket_sha256_is_stable_hex_of_the_text() -> None:
    first = ticket_sha256("same text")
    assert first == ticket_sha256("same text") and len(first) == 64
    assert first != ticket_sha256("other text")


def test_file_sha256_hashes_the_bytes(tmp_path: Path) -> None:
    path = tmp_path / "f.txt"
    path.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert file_sha256(path) == expected


def test_leaked_terms_finds_hint_words_case_insensitively() -> None:
    leaky = PilotCandidate.model_validate(
        candidate_fields(ticket="Maybe add an Asyncio pause?")
    )
    assert leaked_terms(leaky) == ["asyncio"]


def test_leaked_terms_empty_for_a_symptom_only_ticket() -> None:
    assert leaked_terms(PilotCandidate.model_validate(candidate_fields())) == []
