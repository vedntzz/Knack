import os

from knack.pipeline.github import GitHubApi
from knack.pipeline.spark import SparkApi


class MissingCredentials(Exception):
    pass


def live_clients() -> tuple[GitHubApi, SparkApi]:
    return GitHubApi(_required_env("GITHUB_TOKEN")), SparkApi(
        _required_env("MODEL_API_KEY")
    )


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingCredentials(f"{name} is not set")
    return value
