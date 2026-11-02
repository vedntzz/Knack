import json
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, ValidationError

from knack.contracts.models import ModelCall, NOT_RECORDED
from knack.home import knack_home


@runtime_checkable
class Traced(Protocol):
    # A live client that names its host and its last response id.
    host: str
    last_trace_id: str | None


@runtime_checkable
class Named(Protocol):
    # A client that names the model behind it.
    model: str


class RulingRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: str
    # The hash of the deny receipt this ruling answers.
    receipt_hash: str
    objection: str
    decision: Literal["hold", "escalate"]
    reply: str
    cited_quotes: list[str]
    # The model asked for the ruling; None when it was decided without one.
    model: str | None
    # Every model that answered, in the order asked; old rulings recorded none.
    models: list[ModelCall] = []
    # The coding agent the deny's PreToolUse payload named.
    agent: str = NOT_RECORDED
    # Models in models that gave no answer before their timeout; old rulings recorded none.
    timed_out: list[str] = []


def model_call(model: str, client: object) -> ModelCall:
    # Host and trace come only from a client that reports them.
    traced = client if isinstance(client, Traced) else None
    host = traced.host if traced else NOT_RECORDED
    trace = (traced.last_trace_id if traced else None) or NOT_RECORDED
    return ModelCall(model=model, host=host, trace_id=trace)


def model_of(client: object) -> str:
    # The answering client's own model; a client that names none is not guessed.
    return client.model if isinstance(client, Named) else NOT_RECORDED


def rulings_path() -> Path:
    return knack_home() / "rulings.jsonl"


def append_ruling(path: Path, record: RulingRecord) -> None:
    # One appended line per write is small enough that parallel argues never interleave.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def load_rulings(path: Path) -> list[RulingRecord]:
    # A missing file has no rulings; a torn or foreign line is skipped.
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [record for record in map(_ruling_or_none, lines) if record]


def rulings_for(path: Path, receipt_hash: str) -> list[RulingRecord]:
    return [r for r in load_rulings(path) if r.receipt_hash == receipt_hash]


def _ruling_or_none(line: str) -> RulingRecord | None:
    try:
        return RulingRecord.model_validate_json(line)
    except (ValidationError, json.JSONDecodeError):
        return None
