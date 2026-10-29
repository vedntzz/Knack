import sys
from pathlib import Path

from knack.git import git_root, head_commit, origin_repo, repo_slug
from knack.walk.registry import home_registry_dir, Registry
from knack.watch.install import add_muse_hook, install_post_merge, WatchInstallError
from knack.watch.state import write_seen

CORROBORATE_NOTE = "  corroborate: a second extractor reads every PR"


def install_watch(
    cwd: Path, registry: Path | None, muse_settings: Path, corroborate: bool = False
) -> list[str]:
    # Both hooks, then a baseline at HEAD so earlier history is never replayed.
    root, repo = _clone(cwd)
    path = _checked(registry or home_registry_dir(repo) / "registry.json", repo)
    hook = install_post_merge(root, path, sys.executable, corroborate)
    added = add_muse_hook(muse_settings, path, sys.executable, corroborate)
    lines = _report(hook, added, muse_settings, _baseline(root, path))
    return [f"knack watch {repo}", *lines, *([CORROBORATE_NOTE] if corroborate else [])]


def _clone(cwd: Path) -> tuple[Path, str]:
    root = git_root(cwd)
    repo = origin_repo(root) if root else None
    if root is None or repo is None:
        raise WatchInstallError(f"{cwd} is not a git clone with an origin remote")
    return root, repo


def _checked(path: Path, repo: str) -> Path:
    # The registry must exist and guard this clone's repo before any hook goes in.
    if not path.exists():
        raise WatchInstallError(f"no registry at {path}; run: knack init --repo {repo}")
    guarded = Registry.model_validate_json(path.read_text("utf-8")).repo
    if repo_slug(guarded) != repo:
        raise WatchInstallError(f"{path} guards {guarded}, but this clone is {repo}")
    return path


def _baseline(root: Path, registry: Path) -> str:
    head = head_commit(root)
    if head is None:
        raise WatchInstallError(f"{root} has no commits to watch from")
    write_seen(registry.parent, head)
    return head


def _report(hook: Path, added: bool, settings: Path, head: str) -> list[str]:
    muse = f"added to {settings}" if added else f"already in {settings}"
    lines = [f"  post-merge hook: {hook}", f"  Muse Code PostToolBatch hook: {muse}"]
    return lines + [f"  watching merges after {head[:7]}"]
