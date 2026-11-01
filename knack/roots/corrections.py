from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from knack.contracts.models import Root
from knack.home import knack_home

# Only these judge an extraction; allow and retire resolve a deny after ESCALATE.
EXTRACTION_ACTIONS = ("confirm", "reject")
# How many past corrections the extract prompt learns from.
RECENT_LIMIT = 5
BLOCK_HEADER = """PAST CORRECTIONS: a reviewer checked these earlier extractions.
Do not repeat a REJECTED one, and heed its reason. CONFIRMED ones are good examples.
"""


class Correction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    root_id: str
    action: Literal["confirm", "reject", "allow", "retire"]
    before: Root
    after: Root
    reason: str | None
    by: str
    at: str
    # The deny receipt an allow or retire resolves; None for confirm and reject.
    receipt_hash: str | None = None


def corrections_path() -> Path:
    # One log per user, shared by every registry they correct.
    return knack_home() / "corrections.jsonl"


def append_correction(correction: Correction, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(correction.model_dump_json() + "\n")


def remove_correction(correction: Correction, path: Path) -> None:
    # Undoes append_correction; every other line stays exactly as written.
    line = correction.model_dump_json()
    kept = [other for other in path.read_text("utf-8").splitlines() if other != line]
    path.write_text("".join(f"{other}\n" for other in kept), encoding="utf-8")


def recent_corrections(path: Path, limit: int = RECENT_LIMIT) -> list[Correction]:
    # Oldest first; a damaged line or a resolution is skipped, so neither steers init.
    if not path.exists():
        return []
    parsed = [_parsed(line) for line in path.read_text("utf-8").splitlines()]
    return [c for c in parsed if c and c.action in EXTRACTION_ACTIONS][-limit:]


def few_shot_block(corrections: list[Correction]) -> str:
    # Empty when there is nothing to learn from, so the prompt stays unchanged.
    if not corrections:
        return ""
    return BLOCK_HEADER + "".join(_example(c) for c in corrections) + "\n"


def _parsed(line: str) -> Correction | None:
    try:
        return Correction.model_validate_json(line)
    except ValidationError:
        return None


def _example(correction: Correction) -> str:
    root = correction.before
    said = f'decision "{root.decision}"; rejected alternative '
    said += f'"{root.rejected_alternative}"; quote "{root.quote}"'
    if correction.action == "confirm":
        return f"- CONFIRMED: {said}\n"
    return f"- REJECTED (reason: {correction.reason}): {said}\n"
