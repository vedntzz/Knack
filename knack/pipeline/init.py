from pathlib import Path

from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.select import select_prs
from knack.pipeline.stages import finish, Log, Run


def run_init(
    repo: str,
    limit: int,
    out: Path,
    github: GitHub,
    spark: Spark,
    log: Log = print,
    old_ref: str | None = None,
    second: Spark | None = None,
) -> Path:
    # select -> extract -> roots -> compile+prove -> install; a fresh registry.
    run = Run(github, spark, repo, out, log, old_ref=old_ref, second=second)
    log(f"knack init {repo}")
    return finish(run, select_prs(github, repo, limit), keep=[])
