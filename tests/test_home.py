import re
from collections.abc import Callable
from pathlib import Path

import pytest
from knack.bench.muse import muse_env
from knack.bench.sandbox import default_cache
from knack.dispute.rulings import rulings_path
from knack.guard.check import log_error_quietly
from knack.home import knack_home
from knack.hooks.scope import home_error_log
from knack.index.cache import default_cache_dir
from knack.miss.loop import default_work
from knack.receipts.chain import receipts_path
from knack.receipts.edits import edits_dir
from knack.receipts.warns import warns_path
from knack.roots.corrections import corrections_path
from knack.walk.registry import home_registry_dir

REPO = Path(__file__).parents[1]
# Every Python tree in the repo; the regex below names the reads, so this file is skipped.
SCANNED = ["knack", "tests", "spikes", "scripts"]
ALLOWED = ["knack/home.py", "tests/test_home.py"]
# Every way the package reads the user's home; only knack/home.py may use them.
HOME_READS = re.compile(r"Path\.home\(\)|expanduser|os\.path\.expanduser")
WRITERS: list[Callable[[], Path]] = [
    receipts_path,
    warns_path,
    rulings_path,
    corrections_path,
    home_error_log,
    default_cache_dir,
    default_cache,
    lambda: home_registry_dir("acme/widgets"),
    lambda: default_work(Path("data/registry/fastapi.json")),
    lambda: edits_dir(receipts_path()),
]


@pytest.fixture
def knack_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    # HOME and KNACK_HOME point at different folders, so a stray ~/.knack shows.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("KNACK_HOME", str(tmp_path / "knack-home"))
    return tmp_path / "knack-home"


def test_knack_home_reads_knack_home_env(knack_dir: Path) -> None:
    assert knack_home() == knack_dir


def test_knack_home_defaults_to_dot_knack_in_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    assert knack_home() == tmp_path / ".knack"


def test_an_empty_knack_home_means_the_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("KNACK_HOME", "")
    assert knack_home() == tmp_path / ".knack"


@pytest.mark.parametrize("writer", WRITERS)
def test_every_home_path_lands_under_knack_home(
    knack_dir: Path, writer: Callable[[], Path]
) -> None:
    assert writer().is_relative_to(knack_dir)


def test_the_guard_error_log_is_written_under_knack_home(knack_dir: Path) -> None:
    log_error_quietly(home_error_log(), RuntimeError("boom"))
    assert (knack_dir / "guard_errors.log").read_text() == "RuntimeError: boom\n"
    assert not (knack_dir.parent / "home").exists()


def test_a_bench_agent_never_inherits_the_users_knack_home(knack_dir: Path) -> None:
    assert "KNACK_HOME" not in muse_env(knack_dir.parent / "arm")


def test_only_the_resolver_reads_the_users_home() -> None:
    files = [p for tree in SCANNED for p in sorted((REPO / tree).rglob("*.py"))]
    readers = [
        str(path.relative_to(REPO))
        for path in files
        if HOME_READS.search(path.read_text(encoding="utf-8"))
    ]
    assert sorted(readers) == ALLOWED
