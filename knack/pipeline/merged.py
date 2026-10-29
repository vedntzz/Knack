from pathlib import Path

from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.select import select_numbers
from knack.pipeline.stages import finish, Log, Run
from knack.walk.registry import Registry


def run_merged(
    registry_path: Path,
    numbers: list[int],
    tree: Path,
    github: GitHub,
    spark: Spark,
    log: Log,
    second: Spark | None = None,
) -> Path:
    # The named PRs through the same stages; proven rules join the existing registry.
    kept = Registry.model_validate_json(registry_path.read_text(encoding="utf-8"))
    run = Run(github, spark, kept.repo, registry_path.parent, log, tree, second=second)
    return finish(run, select_numbers(github, kept.repo, numbers), keep=kept.rules)
