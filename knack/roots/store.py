from pathlib import Path

from pydantic import ValidationError

from knack.contracts.models import Root


class RootStoreError(Exception):
    pass


def load_roots(directory: Path) -> list[Root]:
    roots = [_load_root_file(path) for path in sorted(directory.glob("*.json"))]
    _reject_duplicate_ids(roots)
    return sorted(roots, key=lambda root: root.id)


def find_root(directory: Path, root_id: str) -> tuple[Path, Root] | None:
    # Root files may be named anything; the id inside the file is what counts.
    for path in sorted(directory.glob("*.json")):
        root = _load_root_file(path)
        if root.id == root_id:
            return path, root
    return None


def write_root(root: Root, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(root.model_dump_json(indent=2, exclude_none=True) + "\n")


def _load_root_file(path: Path) -> Root:
    # Bad JSON and schema errors both name the offending file.
    try:
        return Root.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, UnicodeDecodeError) as error:
        raise RootStoreError(f"invalid root file {path}: {error}") from error


def _reject_duplicate_ids(roots: list[Root]) -> None:
    ids = [root.id for root in roots]
    duplicates = sorted({root_id for root_id in ids if ids.count(root_id) > 1})
    if duplicates:
        raise RootStoreError(f"duplicate root ids: {duplicates}")
