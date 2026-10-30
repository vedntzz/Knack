import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeGitHub
from knack.contracts.models import Root
from knack.pipeline import github
from knack.pipeline.attribution import (
    human_attribution,
    is_bot,
    names_a_bot,
    reattribute_roots,
)
from knack.pipeline.extract import extract_pr
from knack.pipeline.github import GitHubApi
from knack.pipeline.models import Post, PullRequest, PullSummary
from knack.roots.store import load_roots, write_root

REPO = "pytorch/pytorch"


class StubGitHub(FakeGitHub):
    # One PR thread; counts approver lookups so laziness is visible.
    def __init__(self, author: str, approvers: list[str]) -> None:
        super().__init__(Path("."))
        self.author, self.approving = author, approvers
        self.approver_calls = list[int]()

    def posts(self, repo: str, number: int) -> list[Post]:
        return [Post(heading="Comment by pytorchbot", body="Merge started")]

    def approvers(self, repo: str, number: int) -> list[str]:
        self.approver_calls.append(number)
        return self.approving

    def summary(self, repo: str, number: int) -> PullSummary:
        fields = {"number": number, "title": "t", "author": self.author}
        return PullSummary.model_validate(fields | {"body": "", "merged_at": "x"})


class StubSpark:
    model = "stub-spark"

    def __init__(self, decided_by: str) -> None:
        self.decided_by = decided_by

    def ask(self, prompt: str) -> str:
        found = {"decision": "d", "why": "w", "decided_by": self.decided_by}
        return json.dumps({"decisions": [found | {"rejected_alternatives": []}]})


def pull(author: str) -> PullRequest:
    fields = {"number": 201069, "title": "t", "author": author, "body": ""}
    fields |= {"merged_at": "x", "base_sha": "b", "head_sha": "h"}
    return PullRequest.model_validate(fields | {"python_files": ["a.py"]})


def extracted_by(decided_by: str, gh: StubGitHub) -> str:
    extraction = extract_pr(gh, StubSpark(decided_by), REPO, pull(gh.author))
    return extraction.decisions[0].decided_by


@pytest.mark.parametrize(
    "login",
    [
        "pytorchbot",
        "pytorchmergebot",
        "github-actions[bot]",
        "dependabot[bot]",
        "PyTorchMergeBot",
        "k8s-ci-robot",
        "bors",
        "mergify",
        "kodiakhq",
    ],
)
def test_bots_are_named_as_bots(login: str) -> None:
    assert is_bot(login)


@pytest.mark.parametrize("login", ["stegololz", "tiangolo", "Isalia20", "bbovenzi"])
def test_people_are_not_bots(login: str) -> None:
    assert not is_bot(login)


def test_a_bot_anywhere_in_decided_by_counts() -> None:
    assert names_a_bot("Isalia20; merged by pytorchbot")
    assert not names_a_bot("Pushkal Gupta (author); approved and merged by bbovenzi")


def test_attribution_is_the_author_then_human_approvers_once() -> None:
    approvers = ["bob", "pytorchbot", "bob", "alice", "carol"]
    assert (
        human_attribution("alice", approvers)
        == "alice (author); approved by bob, carol"
    )


def test_a_bot_author_leaves_only_human_approvers() -> None:
    assert human_attribution("dependabot[bot]", ["carol"]) == "approved by carol"
    assert human_attribution("dependabot[bot]", ["pytorchbot"]) == ""


def test_extract_replaces_a_bot_with_author_and_approvers() -> None:
    gh = StubGitHub("Isalia20", ["malfet", "pytorchmergebot"])
    assert extracted_by("pytorchbot", gh) == "Isalia20 (author); approved by malfet"


def test_extract_keeps_a_human_and_never_asks_for_approvers() -> None:
    gh = StubGitHub("Isalia20", ["malfet"])
    assert extracted_by("Isalia20", gh) == "Isalia20"
    assert gh.approver_calls == []


def root(root_id: str, decided_by: str, number: int) -> Root:
    url = f"https://github.com/{REPO}/pull/{number}"
    fields = {"id": root_id, "title": "t", "source_url": url, "quote": "q"}
    fields |= {"decision": "d", "why": "w", "decided_by": decided_by}
    return Root.model_validate(fields | {"status": "Uncorroborated"})


def test_reattribute_rewrites_only_bot_roots(tmp_path: Path) -> None:
    write_root(root("pytorch-1-1", "github-actions[bot]", 1), tmp_path / "a.json")
    write_root(root("pytorch-2-1", "Isalia20", 2), tmp_path / "b.json")
    gh = StubGitHub("Isalia20", ["malfet"])
    assert reattribute_roots(tmp_path, REPO, gh) == ["pytorch-1-1"]
    by_id = {r.id: r.decided_by for r in load_roots(tmp_path)}
    assert by_id == {
        "pytorch-1-1": "Isalia20 (author); approved by malfet",
        "pytorch-2-1": "Isalia20",
    }
    assert gh.approver_calls == [1]


def test_approvers_are_logins_with_an_approved_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews = [
        {"user": {"login": "malfet"}, "state": "COMMENTED"},
        {"user": {"login": "malfet"}, "state": "APPROVED"},
        {"user": {"login": "ezyang"}, "state": "CHANGES_REQUESTED"},
        {"user": {"login": "albanD"}, "state": "APPROVED"},
    ]
    pages = {1: reviews, 2: []}

    def fake(url: str, headers: dict[str, str]) -> Any:
        assert "/repos/pytorch/pytorch/pulls/7/reviews" in url
        return pages[int(url.rsplit("page=", 1)[1])]

    monkeypatch.setattr(github, "request_json", fake)
    assert GitHubApi("tok").approvers(REPO, 7) == ["malfet", "albanD"]
