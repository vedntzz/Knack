from pathlib import Path

from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.select import select_prs
from knack.pipeline.stages import finish, Log, Run
from knack.walk.registry import Registry, RegistryEntry


def run_init(
    repo: str,
    limit: int,
    out: Path,
    github: GitHub,
    spark: Spark,
    log: Log = print,
    old_ref: str | None = None,
    second: Spark | None = None,
    adversary: Spark | None = None,
) -> Path:
    # select -> extract -> roots -> compile+prove -> install; merged like watch.
    # No tree: init clones the default branch itself.
    run = Run(github, spark, repo, out, log, None, old_ref, second, adversary)
    keep = existing_rules(out, repo)
    log(f"knack init {repo}")
    return finish(run, select_prs(github, repo, limit), keep=keep)


class OtherRepoRegistry(Exception):
    pass


def existing_rules(out: Path, repo: str) -> list[RegistryEntry]:
    # Rules already in out (imported, watched, an earlier init) are never dropped.
    path = out / "registry.json"
    if not path.is_file():
        return []
    return _same_repo(Registry.model_validate_json(path.read_text("utf-8")), repo).rules


def _same_repo(registry: Registry, repo: str) -> Registry:
    # Checked before any PR is read, so a wrong --out costs nothing.
    if registry.repo.casefold() != repo.casefold():
        raise OtherRepoRegistry(f"registry guards {registry.repo}, not {repo}")
    return registry
