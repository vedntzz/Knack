from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from knack.pipeline.github import search_query, summary_from_item, weekly_windows
from knack.pipeline.models import PullSummary
from knack.pipeline.spark import answer_text

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def test_answer_text_is_the_first_message_after_reasoning() -> None:
    response: dict[str, Any] = {
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": "hi"}]},
        ]
    }
    assert answer_text(response) == "hi"


def test_answer_without_a_message_is_an_error() -> None:
    with pytest.raises(ValueError):
        answer_text({"output": [{"type": "reasoning"}]})


def test_windows_walk_back_a_week_at_a_time_for_a_year() -> None:
    windows = list(weekly_windows(NOW))
    assert windows[0] == (NOW - timedelta(days=7), NOW)
    assert windows[1][1] == windows[0][0]
    assert windows[-1][0] == NOW - timedelta(days=365)


def test_search_query_names_repo_and_merge_window() -> None:
    query = search_query("acme/widgets", NOW - timedelta(days=7), NOW)
    assert query == (
        "repo:acme/widgets is:pr is:merged "
        "merged:2026-10-22T00:00:00Z..2026-10-29T00:00:00Z"
    )


def test_search_item_becomes_a_summary_with_empty_body_for_null() -> None:
    item = {
        "number": 3,
        "title": "T",
        "user": {"login": "bo"},
        "body": None,
        "pull_request": {"merged_at": "2026-10-01T00:00:00Z"},
    }
    assert summary_from_item(item) == PullSummary(
        number=3, title="T", author="bo", body="", merged_at="2026-10-01T00:00:00Z"
    )


def test_the_optional_partner_is_spark_open_when_its_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from knack.pipeline.clients import optional_partner
    from knack.pipeline.spark_open import SparkOpenApi

    monkeypatch.setenv("BASETEN_API_KEY", "k")
    assert isinstance(optional_partner(), SparkOpenApi)


def test_the_optional_partner_is_none_without_its_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from knack.pipeline.clients import optional_partner

    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    assert optional_partner() is None
