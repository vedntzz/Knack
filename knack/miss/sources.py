import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from knack.bench.tickets import BenchTicket
from knack.git import git_root
from knack.miss.cases import CaseKind, EditCase
from knack.receipts.chain import load_receipts, Receipt
from knack.receipts.edits import EditSnapshot, load_edit

RECEIPT_HASH = re.compile(r"[0-9a-f]{64}")
# The guard decision each kind of case disputes.
DISPUTED = {"must-fail": "allow", "must-pass": "deny"}
AS_JSON = "record the edit as JSON instead"


class MissSourceError(Exception):
    pass


class FileSource(Protocol):
    def file_at(self, repo: str, sha: str, path: str) -> str | None: ...


@dataclass(frozen=True)
class Places:
    # Where receipts, their edit snapshots, bench runs and bench tickets live.
    receipts: Path
    edits: Path
    runs: list[Path]
    tickets: Path


class EditJson(BaseModel):
    # An edit given by hand: the file before (None if new) and after.
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    file: str
    before: str | None = None
    after: str
    note: str = ""


def resolve_source(
    source: str, kind: CaseKind, places: Places, github: FileSource
) -> list[EditCase]:
    # An edit JSON file, a receipt hash, or else a bench run id.
    if source.endswith(".json") and Path(source).is_file():
        return [_from_edit_json(Path(source), kind)]
    if RECEIPT_HASH.fullmatch(source):
        return [_from_receipt(source, kind, places)]
    return _from_run(source, kind, places, github)


def _from_edit_json(path: Path, kind: CaseKind) -> EditCase:
    try:
        edit = EditJson.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise MissSourceError(f"{path}: not an edit JSON: {error}") from error
    return EditCase.model_validate(
        edit.model_dump() | {"kind": kind, "source": f"edit {path}"}
    )


def _from_receipt(digest: str, kind: CaseKind, places: Places) -> EditCase:
    receipt = _disputed_receipt(places.receipts, digest, kind)
    edit = _snapshot(places.edits, receipt)
    fields = {"kind": kind, "rule_id": receipt.rule_id, "source": f"receipt {digest}"}
    fields |= {"file": _repo_relative(edit.file), "after": edit.after}
    return EditCase.model_validate(fields | {"before": edit.before})


def _disputed_receipt(path: Path, digest: str, kind: CaseKind) -> Receipt:
    found = [r for r in load_receipts(path) if r.hash == digest]
    if not found:
        raise MissSourceError(f"no receipt {digest[:12]} in {path}")
    if found[0].decision != DISPUTED[kind]:
        raise MissSourceError(_wrong_decision(found[0], kind))
    return found[0]


def _repo_relative(file: str) -> str:
    # The path inside its clone, so path-scoped rules see it; else the bare name.
    path = Path(file).resolve()
    root = git_root(path.parent) if path.parent.is_dir() else None
    return (
        str(path.relative_to(root)) if root and path.is_relative_to(root) else path.name
    )


def _from_run(
    run_id: str, kind: CaseKind, places: Places, github: FileSource
) -> list[EditCase]:
    record = _run_record(places.runs, run_id)
    ticket = _ticket(places.tickets, str(record["ticket"]))
    befores = {f: github.file_at(ticket.repo, ticket.base_sha, f) for f in ticket.files}
    afters = _applied(befores, _run_diff(record))
    common = {"kind": kind, "rule_id": record["rule"], "source": f"bench run {run_id}"}
    edits = [{"file": f, "before": befores[f], "after": a} for f, a in afters.items()]
    return [EditCase.model_validate(common | edit) for edit in edits]


def _run_record(runs: list[Path], run_id: str) -> dict[str, Any]:
    found = [r for r in _run_rows(runs) if r.get("run_id") == run_id]
    if not found:
        raise MissSourceError(
            f"{run_id!r} is not a receipt hash, bench run id or edit JSON"
        )
    return found[0]


def _ticket(path: Path, ticket_id: str) -> BenchTicket:
    # Only the base and files are needed, so the ticket's registry is not checked.
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    tickets = [BenchTicket.model_validate_json(line) for line in lines if line.strip()]
    found = [ticket for ticket in tickets if ticket.id == ticket_id]
    if not found:
        raise MissSourceError(f"no bench ticket {ticket_id} in {path}")
    return found[0]


def _run_diff(record: dict[str, Any]) -> Path:
    # The artifacts copy outlives the work folder; old runs only have the latter.
    diff = _recorded_diff(record)
    if not diff.is_file():
        raise MissSourceError(
            f"bench run {record['run_id']}: its diff {diff} is gone; {AS_JSON}"
        )
    return diff


def _recorded_diff(record: dict[str, Any]) -> Path:
    # The first diff still on disk, else the one the error should name.
    kept = record.get("artifacts_path")
    found = [Path(kept) / "diff.patch"] if kept else []
    found.append(Path(str(record.get("diff_path") or "")))
    return next((diff for diff in found if diff.is_file()), found[0])


def _applied(befores: dict[str, str | None], diff: Path) -> dict[str, str]:
    # The ticket files after the diff, applied in a scratch folder; unchanged ones dropped.
    with tempfile.TemporaryDirectory() as folder:
        _write_files(Path(folder), befores)
        _git_apply(Path(folder), diff)
        afters = {f: _read_or_none(Path(folder) / f) for f in befores}
    return {f: a for f, a in afters.items() if a is not None and a != befores[f]}


def _write_files(folder: Path, files: dict[str, str | None]) -> None:
    for name, text in files.items():
        if text is not None:
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(text, encoding="utf-8")


def _git_apply(folder: Path, diff: Path) -> None:
    args = ["git", "apply", str(diff.resolve())]
    done = subprocess.run(args, cwd=folder, capture_output=True, text=True)
    if done.returncode != 0:
        raise MissSourceError(
            f"{diff} does not apply to the ticket base: {done.stderr}"
        )


def _read_or_none(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _snapshot(folder: Path, receipt: Receipt) -> EditSnapshot:
    # Receipts from before snapshots existed point at none.
    edit = load_edit(folder, receipt.edit_sha256) if receipt.edit_sha256 else None
    if edit is None:
        raise MissSourceError(
            f"receipt {receipt.hash[:12]} has no edit snapshot; {AS_JSON}"
        )
    return edit


def _wrong_decision(receipt: Receipt, kind: CaseKind) -> str:
    disputed = f"{kind} disputes an {DISPUTED[kind]}"
    return f"receipt {receipt.hash[:12]} was a {receipt.decision}; {disputed}"


def _run_rows(runs: list[Path]) -> list[dict[str, Any]]:
    texts = [path.read_text(encoding="utf-8") for path in runs if path.is_file()]
    return [
        json.loads(row) for text in texts for row in text.splitlines() if row.strip()
    ]
