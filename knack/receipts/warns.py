import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError


class WarnRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: str
    repo: str
    # The clone's git root, so a deny in that clone finds it.
    root: str
    session_id: str | None
    # The additionalContext the agent received, verbatim.
    context: str


def warns_path() -> Path:
    return Path.home() / ".knack" / "warns.jsonl"


def record_warn(
    path: Path, repo: str, root: Path, session_id: str | None, context: str, time: str
) -> None:
    # One appended line per write is small enough that parallel hooks never interleave.
    record = WarnRecord(
        time=time, repo=repo, root=str(root), session_id=session_id, context=context
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def load_warns(path: Path) -> list[WarnRecord]:
    # A missing file has no warns; a torn or foreign line is skipped.
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [record for record in map(_warn_or_none, lines) if record]


def _warn_or_none(line: str) -> WarnRecord | None:
    try:
        return WarnRecord.model_validate_json(line)
    except (ValidationError, json.JSONDecodeError):
        return None
