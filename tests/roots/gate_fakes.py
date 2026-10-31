import json
from collections.abc import Iterator
from pathlib import Path

from knack.pipeline.models import Post, PullSummary
from registry_fixture import STATUSES


def roots_of(number: int) -> list[str]:
    return [root_id for root_id in STATUSES if root_id.split("-")[1] == str(number)]


class FakeGitHub:
    # Each PR's thread holds the quote of every root the registry fixture gives it.
    def __init__(self) -> None:
        self.read = list[int]()

    def summary(self, repo: str, number: int) -> PullSummary:
        self.read.append(number)
        fields = {"number": number, "title": f"PR {number}", "author": "maria"}
        return PullSummary.model_validate({**fields, "body": "", "merged_at": "x"})

    def posts(self, repo: str, number: int) -> list[Post]:
        quotes = "; ".join(f"quote of {root_id}" for root_id in roots_of(number))
        return [Post(heading="Review by bo (COMMENTED)", body=quotes)]

    def approvers(self, repo: str, number: int) -> list[str]:
        return []

    def merged_prs(self, repo: str) -> Iterator[PullSummary]:
        raise AssertionError("the gate never lists PRs")

    def changed_files(self, repo: str, number: int) -> list[str]:
        raise AssertionError("the gate never reads files")

    def shas(self, repo: str, number: int) -> tuple[str, str]:
        raise AssertionError("the gate never reads shas")

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        raise AssertionError("the gate never reads files")

    def checkout(self, repo: str, dest: Path) -> Path:
        raise AssertionError("the gate never clones")

    def tags(self, repo: str) -> dict[str, str]:
        raise AssertionError("the gate never reads tags")

    def checkout_ref(self, repo: str, ref: str, dest: Path) -> Path:
        raise AssertionError("the gate never clones")


class FakeSpark:
    # Extracts every fixture root of the PR, unless its prompt holds `forget_on`.
    model = "fake-spark"

    def __init__(self, forget_on: str | None = None, babble: bool = False) -> None:
        self.forget_on, self.babble, self.prompts = forget_on, babble, list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.babble:
            return "I think this PR is great!"
        if self.forget_on is not None and self.forget_on in prompt:
            return json.dumps({"decisions": []})
        number = int(prompt.split("Title: PR ")[1].split("\n")[0])
        return json.dumps({"decisions": [decision(r) for r in roots_of(number)]})


def decision(root_id: str) -> dict[str, object]:
    alternative = {
        "alternative": f"alternative of {root_id}",
        "why_rejected": "w",
        "quote": f"quote of {root_id}",
    }
    fields = {"decision": f"decision of {root_id}", "why": "w", "decided_by": "maria"}
    return {**fields, "rejected_alternatives": [alternative]}
