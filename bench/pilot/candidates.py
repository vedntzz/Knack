import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PilotCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    repo: str
    pr: int
    # First parent of the merge commit; the sandbox starts here.
    base_sha: str
    # The merge commit; the rule must allow it.
    head_sha: str
    files: list[str]
    rejected_path: str
    why_naive: str
    evidence_url: str
    evidence_quote: str
    accepted_fix: str
    # Symptom only: what the agent sees, verbatim.
    ticket: str
    # File names under bench/pilot/rules/.
    rule: str
    accepted_rule: str
    # Words that would hint at either approach; none may appear in the ticket.
    leak_terms: list[str]


def load_candidates(path: Path) -> list[PilotCandidate]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [PilotCandidate.model_validate_json(line) for line in lines if line.strip()]


def ticket_sha256(ticket: str) -> str:
    return hashlib.sha256(ticket.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leaked_terms(candidate: PilotCandidate) -> list[str]:
    lowered = candidate.ticket.lower()
    return [term for term in candidate.leak_terms if term.lower() in lowered]
