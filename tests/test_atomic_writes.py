import inspect
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from knack import atomic
from knack.atomic import write_atomically
from knack.contracts.models import Root
from knack.miss import loop
from knack.miss.cases import EditCase, save_case
from knack.pipeline import reprove, stages
from knack.roots import correct, gate, merge
from knack.roots.store import load_roots, write_root

REPO_ROOT = Path(__file__).parents[1]
# Big enough that a truncate-then-write is caught half done by a reader in a loop.
OLD = "old-rule\n" * 400_000
NEW = "new-rule-longer\n" * 300_000
ROUNDS = 40
# Every function that writes a live rule, registry, root or case file.
LIVE_WRITERS: tuple[Callable[..., Any], ...] = (
    loop._install,  # pyright: ignore[reportPrivateUsage]
    stages._written,  # pyright: ignore[reportPrivateUsage]
    stages._write_registry,  # pyright: ignore[reportPrivateUsage]
    write_root,
    save_case,
    gate._roll_back,  # pyright: ignore[reportPrivateUsage]
    correct.drop_from_registry,
    merge._write,  # pyright: ignore[reportPrivateUsage]
    merge._copied,  # pyright: ignore[reportPrivateUsage]
    reprove._write_proofs,  # pyright: ignore[reportPrivateUsage]
)


def read_while_writing(path: Path, write: Callable[[Path, str], object]) -> set[str]:
    # Every distinct content a reader saw while the writer swapped OLD and NEW.
    seen: set[str] = set()
    done = threading.Event()

    def writer() -> None:
        for round_ in range(ROUNDS):
            write(path, NEW if round_ % 2 == 0 else OLD)
        done.set()

    thread = threading.Thread(target=writer)
    thread.start()
    while not done.is_set():
        seen.add(path.read_text(encoding="utf-8"))
    thread.join()
    return seen


def test_a_reader_during_a_write_sees_the_old_or_the_new_file(tmp_path: Path) -> None:
    path = tmp_path / "rule.yml"
    path.write_text(OLD, encoding="utf-8")
    seen = read_while_writing(path, write_atomically)
    assert seen <= {OLD, NEW}, sorted(len(text) for text in seen)


def test_a_crash_before_the_swap_keeps_the_old_file_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "registry.json"
    path.write_text(OLD, encoding="utf-8")

    def crash(*_: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(atomic.os, "replace", crash)
    with pytest.raises(OSError):
        write_atomically(path, NEW)
    assert path.read_text(encoding="utf-8") == OLD
    assert [p.name for p in tmp_path.iterdir()] == ["registry.json"]


def test_the_temp_file_is_in_the_same_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A rename only swaps atomically within one file system, so the temp sits beside the target.
    swaps: list[tuple[str, str]] = []
    real = atomic.os.replace

    def spy(source: str, target: str) -> None:
        swaps.append((source, target))
        real(source, target)

    monkeypatch.setattr(atomic.os, "replace", spy)
    write_atomically(tmp_path / "a" / "rule.yml", NEW)
    [(source, target)] = swaps
    assert Path(source).parent == Path(target).parent == tmp_path / "a"


def test_an_existing_files_mode_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "rule.yml"
    path.write_text(OLD)
    path.chmod(0o640)
    write_atomically(path, NEW)
    assert path.stat().st_mode & 0o777 == 0o640


def test_a_new_file_is_readable_by_others_like_write_text(tmp_path: Path) -> None:
    path = tmp_path / "rule.yml"
    write_atomically(path, NEW)
    assert path.stat().st_mode & 0o044 == 0o044


def test_a_root_rewritten_while_read_is_whole_at_every_read(tmp_path: Path) -> None:
    [first, *_] = load_roots(REPO_ROOT / "data" / "roots" / "airflow")
    bigger = first.model_copy(update={"quote": "x" * 2_000_000})
    path = tmp_path / "root.json"
    write_root(first, path)

    def write(target: Path, text: str) -> None:
        write_root(bigger if text == NEW else first, target)

    seen = read_while_writing(path, write)
    assert {Root.model_validate_json(text).id for text in seen} == {first.id}


def test_a_case_rewritten_while_read_is_whole_at_every_read(tmp_path: Path) -> None:
    fields: dict[str, Any] = {"kind": "must-fail", "rule_id": "r-1", "file": "a.py"}
    case = EditCase(**fields, before=None, after="x" * 2_000_000, source="s")
    folder = tmp_path / "cases"
    path = save_case(folder, case)
    whole = path.read_text()
    seen = read_while_writing(path, lambda target, text: save_case(folder, case))
    assert seen == {whole}


@pytest.mark.parametrize("writer", LIVE_WRITERS, ids=lambda w: w.__qualname__)
def test_every_live_rule_registry_root_and_case_writer_swaps_atomically(
    writer: Callable[..., Any],
) -> None:
    source = inspect.getsource(writer)
    assert "write_atomically(" in source
    assert ".write_text(" not in source and "copyfile(" not in source
