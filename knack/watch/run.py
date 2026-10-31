from collections.abc import Callable
from pathlib import Path

from knack.git import git_root, head_commit, origin_repo, repo_slug
from knack.pipeline.merged import run_merged
from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.stages import Log
from knack.walk.registry import load_registry, Registry
from knack.watch import selfcheck
from knack.watch.merged import pending_prs
from knack.watch.state import read_seen, watch_lock, write_seen

# A third client, when given, is the partner extractor that corroborates.
Clients = Callable[[], tuple[GitHub, Spark] | tuple[GitHub, Spark, Spark]]
Clone = tuple[Path, str]
# Builds the second model that judges merges when no partner corroborates; None if unset.
Judge = Callable[[], Spark | None]


def run_pending(
    cwd: Path,
    registry_path: Path,
    clients: Clients,
    log: Log,
    judge: Judge | None = None,
) -> Path | None:
    # The pipeline on PRs merged since the baseline; None when there was nothing to do.
    clone = our_clone(cwd, registry_path)
    if clone is None:
        return None
    models = (clients, judge)
    with watch_lock(registry_path.parent) as acquired:
        return _run_locked(clone, registry_path, models, log) if acquired else None


def pending_root(cwd: Path, registry_path: Path) -> Path | None:
    # The clone's root when it has merges waiting; a cheap check for every tool batch.
    clone = our_clone(cwd, registry_path)
    if clone is None or not pending_prs(clone[0], read_seen(registry_path.parent)):
        return None
    return clone[0]


def our_clone(cwd: Path, registry_path: Path) -> Clone | None:
    # (git root, repo) only when cwd is a clone of the repo the registry guards.
    repo = Registry.model_validate_json(registry_path.read_text("utf-8")).repo
    root = git_root(cwd)
    if root is None or origin_repo(root) != repo_slug(repo):
        return None
    return root, repo


def merged_line(repo: str, numbers: list[int]) -> str:
    listed = ", ".join(f"#{number}" for number in numbers)
    noun = "merged PR" if len(numbers) == 1 else "merged PRs"
    return f"knack watch {repo}: {len(numbers)} {noun}: {listed}"


def _run_locked(
    clone: Clone, registry_path: Path, models: tuple[Clients, Judge | None], log: Log
) -> Path | None:
    # The baseline moves only after a run, so missing tokens leave merges pending.
    out, head = registry_path.parent, head_commit(clone[0])
    numbers = pending_prs(clone[0], read_seen(out))
    done = _run_numbers(clone, registry_path, numbers, models, log)
    if head is not None:
        write_seen(out, head)
    return done


def _run_numbers(
    clone: Clone,
    registry_path: Path,
    numbers: list[int],
    models: tuple[Clients, Judge | None],
    log: Log,
) -> Path | None:
    # Tokens are only needed, and checked, once there is a merged PR to run.
    if not numbers:
        return None
    github, spark, *second = models[0]()
    log(merged_line(clone[1], numbers))
    trio = (github, spark, second[0] if second else None)
    checker = _checker(trio[2], models[1])
    return _merged_then_checked(clone, registry_path, numbers, trio, checker, log)


def _checker(partner: Spark | None, judge: Judge | None) -> Spark | None:
    # A corroborating partner judges too, so no second copy of it is built.
    if partner is not None or judge is None:
        return partner
    return judge()


def _merged_then_checked(
    clone: Clone,
    registry_path: Path,
    numbers: list[int],
    models: tuple[GitHub, Spark, Spark | None],
    checker: Spark | None,
    log: Log,
) -> Path:
    # The rules in place before the run are the ones these merges could have slipped past.
    before = load_registry(registry_path)
    done = run_merged(registry_path, numbers, clone[0], *models[:2], log, models[2])
    judged = (*models[:2], checker)
    selfcheck.self_check_quietly(registry_path, before, numbers, judged, log)
    return done
