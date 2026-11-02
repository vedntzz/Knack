import asyncio
import itertools
import json
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from knack.dispute.rulings import RulingRecord

# A comment line every this many polls keeps the browser's connection from idling out.
KEEPALIVE_POLLS = 60
# What one line on file sends: a key it is known by, and its server-sent event.
News = tuple[str, str]
Reader = Callable[[str], News | None]
# A resolution event's fields, from the receipt's resolution.
SETTLES = (("block", "of"), ("action", "action"))


def _lines(path: Path) -> list[str]:
    # A missing or unreadable file has no news; a line being written is skipped later.
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _news(lines: Iterable[str], read: Reader) -> list[News]:
    # Every line this reader understands, in file order.
    return [found for found in map(read, lines) if found]


def _fields(line: str) -> dict[str, object]:
    try:
        record: object = json.loads(line)
    except ValueError:
        return {}
    return cast(dict[str, object], record) if isinstance(record, dict) else {}


def _deny(line: str) -> News | None:
    fields = _fields(line)
    # A person's uphold records a deny but blocks nothing new.
    fresh = fields.get("decision") == "deny" and fields.get("resolution") is None
    found = str(fields.get("hash")) if fresh and "hash" in fields else None
    return (found, deny_event(found)) if found else None


def _resolution(line: str) -> News | None:
    # A person's allow, retire or uphold, sent with the block it settles.
    fields = _fields(line)
    settled = fields.get("resolution")
    if not isinstance(settled, dict) or "hash" not in fields:
        return None
    said = {k: cast(dict[str, object], settled).get(f) for k, f in SETTLES}
    return str(fields["hash"]), named_event("resolution", said)


def _ruling(line: str) -> News | None:
    # A ruling has no hash of its own; its whole line, time included, is its key.
    try:
        ruling = RulingRecord.model_validate_json(line)
    except (ValidationError, ValueError):
        return None
    said = {"block": ruling.receipt_hash, "decision": ruling.decision}
    return line, named_event("ruling", said)


def all_news(receipts: Path, rulings: Path) -> list[News]:
    # In the order they happen in one poll: a deny, rulings on it, then a person's resolution.
    lines = _lines(receipts)
    found = _news(lines, _deny) + _news(_lines(rulings), _ruling)
    return found + _news(lines, _resolution)


def fresh_events(receipts: Path, rulings: Path, seen: set[str]) -> str:
    # News not sent before; seen grows, so a file copied over the last run still works.
    fresh = [
        (key, sent) for key, sent in all_news(receipts, rulings) if key not in seen
    ]
    seen.update(key for key, _ in fresh)
    return "".join(sent for _, sent in fresh)


async def console_events(
    receipts: Path, rulings: Path, poll_seconds: float
) -> AsyncIterator[str]:
    # Server-sent events: each new deny, ruling and resolution, once, in order.
    seen = {key for key, _ in all_news(receipts, rulings)}
    yield ": waiting for the next deny\n\n"
    for tick in itertools.count(1):
        await asyncio.sleep(poll_seconds)
        yield fresh_events(receipts, rulings, seen)
        yield ": still here\n\n" if tick % KEEPALIVE_POLLS == 0 else ""


def deny_event(found: str) -> str:
    return f"event: deny\ndata: {found}\n\n"


def named_event(name: str, said: Mapping[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(said)}\n\n"
