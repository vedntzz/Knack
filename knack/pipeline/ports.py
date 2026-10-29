from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from knack.pipeline.models import Post, PullSummary


class GitHub(Protocol):
    def merged_prs(self, repo: str) -> Iterator[PullSummary]:
        # Newest first; the caller stops pulling once it has enough.
        ...

    def summary(self, repo: str, number: int) -> PullSummary: ...

    def changed_files(self, repo: str, number: int) -> list[str]: ...

    def shas(self, repo: str, number: int) -> tuple[str, str]:
        # (base sha, head sha) of the merged PR.
        ...

    def posts(self, repo: str, number: int) -> list[Post]:
        # Reviews, then issue comments, in thread order.
        ...

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        # None when the file does not exist at that sha.
        ...

    def checkout(self, repo: str, dest: Path) -> Path:
        # A shallow clone of the default branch, reused when dest already holds one.
        ...

    def tags(self, repo: str) -> dict[str, str]:
        # Every tag name with its ISO-8601 date: tagged, or committed if lightweight.
        ...

    def checkout_ref(self, repo: str, ref: str, dest: Path) -> Path:
        # A shallow clone at ref, reused when dest already holds one.
        ...


class Spark(Protocol):
    @property
    def model(self) -> str: ...

    def ask(self, prompt: str) -> str:
        # The text of the model's answer message.
        ...
