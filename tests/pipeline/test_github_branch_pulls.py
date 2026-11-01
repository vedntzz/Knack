from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from knack.pipeline import github
from knack.pipeline.github import GitHubApi


def test_branch_pulls_reads_one_newest_page_from_then_into_the_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = list[str]()

    def fake(url: str, headers: dict[str, str]) -> Any:
        sent.append(url)
        return [{"number": len(sent)}]

    monkeypatch.setattr(github, "request_json", fake)
    assert GitHubApi("tok").branch_pulls("acme/widgets", "fix-sort") == [
        {"number": 1},
        {"number": 2},
    ]
    paths = {urlparse(url).path for url in sent}
    assert paths == {"/repos/acme/widgets/pulls"}
    head, base = (parse_qs(urlparse(url).query) for url in sent)
    assert (head["head"], base["base"]) == (["acme:fix-sort"], ["fix-sort"])
    newest = {"state": ["all"], "sort": ["updated"], "direction": ["desc"]}
    assert all(query.items() >= newest.items() for query in (head, base))
