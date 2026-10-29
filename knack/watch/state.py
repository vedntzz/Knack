import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict

STATE_FILE = "watch.json"
LOCK_FILE = "watch.lock"
# A lock older than this outlived a killed run, so it no longer counts.
STALE_LOCK_SECONDS = 3600


class WatchState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_head: str


def read_seen(out: Path) -> str | None:
    # The last HEAD whose merges were handled; None before knack watch set one.
    path = out / STATE_FILE
    if not path.exists():
        return None
    return WatchState.model_validate_json(path.read_text(encoding="utf-8")).seen_head


def write_seen(out: Path, head: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    state = WatchState(seen_head=head).model_dump_json()
    (out / STATE_FILE).write_text(state + "\n", encoding="utf-8")


@contextmanager
def watch_lock(out: Path) -> Generator[bool]:
    # Yields False when another run holds the lock; post-merge and PostToolBatch can race.
    acquired = _try_lock(out / LOCK_FILE)
    try:
        yield acquired
    finally:
        if acquired:
            (out / LOCK_FILE).unlink(missing_ok=True)


def _try_lock(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    _clear_stale(path)
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    return True


def _clear_stale(path: Path) -> None:
    if path.exists() and time.time() - path.stat().st_mtime > STALE_LOCK_SECONDS:
        path.unlink(missing_ok=True)
