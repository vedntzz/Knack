from typing import Any

import pytest
from knack.pipeline import github
from knack.pipeline.github import GitHubApi


def test_viewer_is_the_login_of_the_token_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = list[tuple[str, dict[str, str]]]()

    def fake(url: str, headers: dict[str, str]) -> Any:
        sent.append((url, headers))
        return {"login": "maria", "id": 1}

    monkeypatch.setattr(github, "request_json", fake)
    assert GitHubApi("tok").viewer() == "maria"
    [(url, headers)] = sent
    assert url == "https://api.github.com/user"
    assert headers["Authorization"] == "Bearer tok"
