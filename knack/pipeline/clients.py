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
# Corroboration pairs each extractor with the other one.
PARTNERS = {"spark": "spark-open", "spark-open": "spark"}


class MissingCredentials(Exception):
    pass


def live_clients(extractor: str = DEFAULT_EXTRACTOR) -> tuple[GitHubApi, Spark]:
    key_env, spark = EXTRACTORS[extractor]
    return GitHubApi(_required_env("GITHUB_TOKEN")), spark(_required_env(key_env))


def partner_client(extractor: str) -> Spark:
    return _client(PARTNERS[extractor])


def adversary_client(extractor: str, adversary: str | None) -> Spark | None:
    # A named adversary needs its key; by default the partner, or None (the compiler).
    if adversary is not None:
        return _client(adversary)
    try:
        return partner_client(extractor)
    except MissingCredentials:
        return None


def corroborating_clients(
    extractor: str = DEFAULT_EXTRACTOR,
) -> tuple[GitHubApi, Spark, Spark]:
    return (*live_clients(extractor), partner_client(extractor))


def _client(extractor: str) -> Spark:
    key_env, spark = EXTRACTORS[extractor]
    return spark(_required_env(key_env))


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingCredentials(f"{name} is not set")
    return value
