import os
from collections.abc import Callable

from knack.pipeline.github import GitHubApi
from knack.pipeline.ports import Spark
from knack.pipeline.spark import SparkApi
from knack.pipeline.spark_open import SparkOpenApi

# Each extractor behind the Spark port, with the env var holding its key.
EXTRACTORS: dict[str, tuple[str, Callable[[str], Spark]]] = {
    "spark": ("MODEL_API_KEY", SparkApi),
    "spark-open": ("BASETEN_API_KEY", SparkOpenApi),
}
DEFAULT_EXTRACTOR = "spark"


class MissingCredentials(Exception):
    pass


def live_clients(extractor: str = DEFAULT_EXTRACTOR) -> tuple[GitHubApi, Spark]:
    key_env, spark = EXTRACTORS[extractor]
    return GitHubApi(_required_env("GITHUB_TOKEN")), spark(_required_env(key_env))


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingCredentials(f"{name} is not set")
    return value
