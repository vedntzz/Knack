import subprocess
from pathlib import Path

import pytest
from knack.bench.sandbox import build_sandbox, SandboxError
from knack.bench.tickets import BenchTicket
from knack.git import origin_repo

REPO = "acme/widgets"
SHA = "8b5306690acb58d0584376272dfa2159aecea0dd"
# CRLF and non-ASCII prove the files are written byte for byte.
BASE = {
    "src/pkg/loader.py": "def load(items):\r\n    return 'café'\n",
    "src/pkg/sse.py": "def emit(data):\n    return data\n",
}
OTHER = {"src/pkg/unrelated.py": "x = 1\n"}
TRACES = {".knack", ".muse", "CLAUDE.md", "AGENTS.md", ".venv"}


class FakeGitHub:
    # Serves BASE at SHA and counts every fetch.
    def __init__(self) -> None:
        self.fetches = list[tuple[str, str, str]]()

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        self.fetches.append((repo, sha, path))
        return {**BASE, **OTHER}.get(path) if sha == SHA else None


def ticket(files: list[str] | None = None) -> BenchTicket:
    return BenchTicket.model_validate(
        {
            "id": "bench-ticket-7",
            "repo": REPO,
            "pr": 9,
            "base_sha": SHA,
            "files": files or sorted(BASE),
            "rule": "widgets-9",
            "fix_functions": ["Loader.read_all_blobs", "_split_lines_helper"],
            "ticket": "Uploading a large bucket kills the worker.",
        }
    )


def build(tmp_path: Path, github: FakeGitHub, made: BenchTicket) -> Path:
    root = tmp_path / "sandboxes"
    root.mkdir(exist_ok=True)
    return build_sandbox(made, root, github, cache=tmp_path / "cache")


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.decode("utf-8")


def tracked_tree(sandbox: Path) -> dict[str, bytes]:
    # Every file outside .git, by path relative to the sandbox.
    files = [p for p in sandbox.rglob("*") if p.is_file() and ".git" not in p.parts]
    return {p.relative_to(sandbox).as_posix(): p.read_bytes() for p in files}


def readable_git_files(sandbox: Path) -> list[Path]:
    # .git files stored as text; objects are compressed and the index is binary.
    skipped = {"objects", "index"}
    files = [p for p in (sandbox / ".git").rglob("*") if p.is_file()]
    return [p for p in files if not skipped & set(p.relative_to(sandbox).parts)]


def test_sandbox_holds_exactly_the_ticket_files_at_base(tmp_path: Path) -> None:
    sandbox = build(tmp_path, FakeGitHub(), ticket())
    expected = {path: text.encode("utf-8") for path, text in BASE.items()}
    assert tracked_tree(sandbox) == expected


def test_sandbox_commits_the_files_as_initial_import(tmp_path: Path) -> None:
    sandbox = build(tmp_path, FakeGitHub(), ticket())
    assert git(sandbox, "log", "--format=%s").splitlines() == ["Initial import"]
    assert sorted(git(sandbox, "ls-files").splitlines()) == sorted(BASE)
    assert git(sandbox, "status", "--porcelain") == ""


def test_sandbox_origin_is_the_ticket_repo(tmp_path: Path) -> None:
    sandbox = build(tmp_path, FakeGitHub(), ticket())
    assert origin_repo(sandbox) == REPO


def test_sandbox_has_no_knack_traces(tmp_path: Path) -> None:
    sandbox = build(tmp_path, FakeGitHub(), ticket())
    names = {p.name for p in sandbox.rglob("*")}
    assert not names & TRACES


def test_sandbox_carries_nothing_from_the_ticket_json(tmp_path: Path) -> None:
    made = ticket()
    sandbox = build(tmp_path, FakeGitHub(), made)
    secrets = [made.id, made.rule, made.ticket, *made.fix_functions, "knack"]
    texts = [
        p.read_bytes().decode("utf-8", "replace") for p in readable_git_files(sandbox)
    ]
    texts += [
        *(b.decode("utf-8") for b in tracked_tree(sandbox).values()),
        sandbox.name,
    ]
    texts += [git(sandbox, "log", "--format=%an %ae %cn %ce %B")]
    assert not [s for s in secrets if any(s.lower() in t.lower() for t in texts)]


def test_two_builds_are_independent_clean_sandboxes(tmp_path: Path) -> None:
    github = FakeGitHub()
    first, second = build(tmp_path, github, ticket()), build(tmp_path, github, ticket())
    (first / "src/pkg/loader.py").write_text("changed\n")
    assert first != second
    assert git(second, "status", "--porcelain") == ""
    assert tracked_tree(second) == {p: t.encode("utf-8") for p, t in BASE.items()}


def test_second_build_reads_the_cache_not_github(tmp_path: Path) -> None:
    github = FakeGitHub()
    build(tmp_path, github, ticket())
    fetched = len(github.fetches)
    build(tmp_path, github, ticket())
    assert (fetched, len(github.fetches)) == (len(BASE), len(BASE))


def test_cache_is_keyed_by_base_sha(tmp_path: Path) -> None:
    # A second ticket at the same base fetches only the files not cached yet.
    github = FakeGitHub()
    build(tmp_path, github, ticket())
    build(tmp_path, github, ticket(files=[*sorted(BASE), *OTHER]))
    assert [path for _, _, path in github.fetches] == [*sorted(BASE), *OTHER]


def test_file_missing_at_base_raises(tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="src/pkg/new.py.*8b53066"):
        build(tmp_path, FakeGitHub(), ticket(files=["src/pkg/new.py"]))


def test_file_outside_the_repo_is_refused(tmp_path: Path) -> None:
    # A ticket path must never write outside the sandbox or the cache.
    with pytest.raises(SandboxError, match="outside the repo"):
        build(tmp_path, FakeGitHub(), ticket(files=["../escape.py"]))
    assert not (tmp_path / "escape.py").exists()
