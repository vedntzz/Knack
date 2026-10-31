import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 2


def repo_slug(url: str) -> str:
    # https, scp-style ssh and ssh:// remotes all reduce to lowercase owner/name.
    path = url.strip().rstrip("/").removesuffix(".git").replace(":", "/")
    return "/".join(path.split("/")[-2:]).lower()


def origin_repo(cwd: Path) -> str | None:
    url = git_output(cwd, "remote", "get-url", "origin")
    return repo_slug(url) if url else None


def git_root(cwd: Path) -> Path | None:
    top = git_output(cwd, "rev-parse", "--show-toplevel")
    return Path(top).resolve() if top else None


def head_commit(repo_root: Path) -> str | None:
    # None before the first commit, when there is no HEAD to key on.
    return git_output(repo_root, "rev-parse", "--verify", "-q", "HEAD")


def git_output(cwd: Path, *args: str) -> str | None:
    # Missing git, a non-repo cwd and a failed command all read as None.
    done = _run_quietly(["git", "-C", str(cwd), *args])
    if done is None or done.returncode != 0:
        return None
    return done.stdout.strip()


def _run_quietly(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def current_branch(cwd: Path) -> str | None:
    # Named even before the first commit; None when detached or outside git.
    return git_output(cwd, "symbolic-ref", "--short", "-q", "HEAD") or None
