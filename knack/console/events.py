import asyncio
import itertools
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

# A comment line every this many polls keeps the browser's connection from idling out.
KEEPALIVE_POLLS = 60


def deny_hashes(receipts: Path) -> list[str]:
    # Every deny's hash in file order; a line being written or unreadable is skipped.
    try:
        lines = receipts.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [found for found in map(_deny_hash, lines) if found]


def _deny_hash(line: str) -> str | None:
    try:
        record: object = json.loads(line)
    except ValueError:
        return None
    fields = cast(dict[str, object], record) if isinstance(record, dict) else {}
    return str(fields.get("hash")) if fields.get("decision") == "deny" else None


def fresh_denies(receipts: Path, seen: set[str]) -> list[str]:
    # Denies not sent before; seen grows, so a file copied over the last run still works.
    fresh = [found for found in deny_hashes(receipts) if found not in seen]
    seen.update(fresh)
    return fresh


async def deny_events(receipts: Path, poll_seconds: float) -> AsyncIterator[str]:
    # Server-sent events: one "deny" per new deny receipt, its data the receipt hash.
    seen = set(deny_hashes(receipts))
    yield ": waiting for the next deny\n\n"
    for tick in itertools.count(1):
        await asyncio.sleep(poll_seconds)
        yield "".join(map(deny_event, fresh_denies(receipts, seen)))
        yield ": still here\n\n" if tick % KEEPALIVE_POLLS == 0 else ""


def deny_event(found: str) -> str:
    return f"event: deny\ndata: {found}\n\n"
