import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError


class EditSnapshot(BaseModel):
    # One proposed edit as the guard saw it, so a receipt can be replayed later.
    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    # The file before the edit; None when the edit creates it.
    before: str | None
    after: str


def edits_dir(receipts: Path) -> Path:
    return receipts.parent / "edits"


def save_edit(folder: Path, edit: EditSnapshot) -> str:
    # Content-addressed: the same edit is written once, under its SHA-256.
    text = edit.model_dump_json()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{digest}.json").write_text(text, encoding="utf-8")
    return digest


def load_edit(folder: Path, digest: str) -> EditSnapshot | None:
    # None for an unknown hash or an unreadable snapshot.
    try:
        return EditSnapshot.model_validate_json(
            (folder / f"{digest}.json").read_text("utf-8")
        )
    except (OSError, ValidationError):
        return None
