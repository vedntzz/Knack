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
# A person waits on argue's second opinion, so Spark Open gets 60 s there, not 300.
SECOND_OPINION_TIMEOUT_SECONDS: float = 60


class MissingCredentials(Exception):
    pass


class RefusedCredentials(MissingCredentials):
    # A key that is there but unusable, such as a file others can read; never skipped.
    pass


# Reads a key by its env var name; by default from the environment only.
Key = Callable[[str], str]


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingCredentials(f"{name} is not set")
    return value


def live_clients(
    extractor: str = DEFAULT_EXTRACTOR, key: Key = required_env
) -> tuple[GitHubApi, Spark]:
    return github_client(key), _client(extractor, key)


def github_client(key: Key = required_env) -> GitHubApi:
    return GitHubApi(key("GITHUB_TOKEN"))


def partner_client(extractor: str, key: Key = required_env) -> Spark:
    return _client(PARTNERS[extractor], key)


def second_opinion_client() -> Spark:
    client = SparkOpenApi(required_env(EXTRACTORS["spark-open"][0]))
    client.timeout_seconds = SECOND_OPINION_TIMEOUT_SECONDS
    return client


def adversary_client(extractor: str, adversary: str | None) -> Spark | None:
    # A named adversary needs its key; by default the partner, or None (the compiler).
    if adversary is not None:
        return _client(adversary)
    return optional_partner(extractor)


def optional_partner(
    extractor: str = DEFAULT_EXTRACTOR, key: Key = required_env
) -> Spark | None:
    # The other extractor when its key is there; None when it is not; a refused key is an error.
    try:
        return partner_client(extractor, key)
    except RefusedCredentials:
        raise
    except MissingCredentials:
        return None


def corroborating_clients(
    extractor: str = DEFAULT_EXTRACTOR, key: Key = required_env
) -> tuple[GitHubApi, Spark, Spark]:
    return (*live_clients(extractor, key), partner_client(extractor, key))


def _client(extractor: str, key: Key = required_env) -> Spark:
    key_env, spark = EXTRACTORS[extractor]
    return spark(key(key_env))
