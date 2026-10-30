import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Protocol

from knack.bench.tickets import BenchTicket

GIT_TIMEOUT_SECONDS = 30
# A plain developer identity, so the sandbox history names nothing of the bench.
IDENTITY = ("-c", "user.name=Developer", "-c", "user.email=dev@example.com")
UNSIGNED = ("-c", "commit.gpgsign=false")


class SandboxError(Exception):
    pass


class BaseFiles(Protocol):
    # The one GitHub call a sandbox needs; GitHubApi satisfies it.
    def file_at(self, repo: str, sha: str, path: str) -> str | None: ...


def default_cache() -> Path:
    return Path.home() / ".knack" / "cache" / "bench"


def build_sandbox(
    ticket: BenchTicket, root: Path, github: BaseFiles, cache: Path | None = None
) -> Path:
    # A fresh repo with only the ticket's files at base_sha, origin set to its repo.
    sources = base_sources(ticket, github, cache or default_cache())
    sandbox = Path(tempfile.mkdtemp(prefix=f"{ticket.repo.split('/')[1]}_", dir=root))
    for path, data in sources.items():
        _write(sandbox / path, data)
    _initial_commit(sandbox, ticket.repo)
    return sandbox


def base_sources(
    ticket: BenchTicket, github: BaseFiles, cache: Path
) -> dict[str, bytes]:
    # Each file at base_sha comes from the cache, or from GitHub once.
    return {
        path: _cached(ticket, _inside(path), github, cache) for path in ticket.files
    }


def _inside(path: str) -> str:
    # A relative path with no "..", so writes stay in the sandbox and the cache.
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise SandboxError(f"{path} is outside the repo")
    return path


def _cached(ticket: BenchTicket, path: str, github: BaseFiles, cache: Path) -> bytes:
    stored = cache / ticket.base_sha / path
    if not stored.is_file():
        _write_atomically(stored, _fetched(ticket, path, github))
    return stored.read_bytes()


def _write_atomically(path: Path, data: bytes) -> None:
    # Parallel runs may fetch the same file; a reader never sees half of it.
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.{uuid.uuid4().hex}")
    partial.write_bytes(data)
    partial.replace(path)


def _fetched(ticket: BenchTicket, path: str, github: BaseFiles) -> bytes:
    text = github.file_at(ticket.repo, ticket.base_sha, path)
    if text is None:
        raise SandboxError(f"{path} does not exist at {ticket.base_sha}")
    return text.encode("utf-8")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _initial_commit(sandbox: Path, repo: str) -> None:
    _git(sandbox, "init", "-q", "-b", "main")
    _git(sandbox, "add", "-A")
    _git(sandbox, *IDENTITY, *UNSIGNED, "commit", "-q", "-m", "Initial import")
    _git(sandbox, "remote", "add", "origin", f"https://github.com/{repo}.git")


def _git(sandbox: Path, *args: str) -> None:
    command = ["git", "-C", str(sandbox), *args]
    subprocess.run(
        command, check=True, capture_output=True, timeout=GIT_TIMEOUT_SECONDS
    )
