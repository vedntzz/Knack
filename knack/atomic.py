import os
import stat
import tempfile
from pathlib import Path

# A file written fresh gets what write_text gives under the usual umask.
NEW_FILE_MODE = 0o644


def write_atomically(path: Path, text: str) -> None:
    # A temp file beside the target, renamed over it: readers see the old file or the new.
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        _swap_in(handle, temp, path, text)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def _swap_in(handle: int, temp: str, path: Path, text: str) -> None:
    _fill(handle, text, _mode_of(path))
    os.replace(temp, path)


def _fill(handle: int, text: str, mode: int) -> None:
    # Synced before the swap, so a crash never renames an empty file into place.
    os.fchmod(handle, mode)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(text)
        out.flush()
        os.fsync(out.fileno())


def _mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode) if path.exists() else NEW_FILE_MODE
