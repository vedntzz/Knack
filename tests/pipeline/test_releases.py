from pathlib import Path
from typing import Any

import pytest
from knack.pipeline import github as github_module
from knack.pipeline.github import GitHubApi
from knack.pipeline.releases import last_release_before

MERGED = "2026-10-01T12:00:00Z"


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (
            {
                "0.116.0": "2026-10-05T09:00:00Z",
                "0.115.2": "2026-09-20T09:00:00Z",
                "0.115.0": "2026-08-01T09:00:00Z",
            },
            "0.115.2",
        ),
        # Date decides, not version: a backport line can be released last.
        ({"3.0.0": "2026-08-01T00:00:00Z", "2.11.1": "2026-09-01T00:00:00Z"}, "2.11.1"),
        # Pre-releases and non-release tags are not releases.
        (
            {
                "1.3.0rc1": "2026-09-30T00:00:00Z",
                "nightly": "2026-09-30T00:00:00Z",
                "v1.2.0": "2026-09-01T00:00:00Z",
            },
            "v1.2.0",
        ),
        # A release tagged the second the PR merged may already hold it.
        ({"1.2.0": MERGED, "1.1.0": "2026-09-01T00:00:00Z"}, "1.1.0"),
    ],
)
def test_old_release_is_the_last_release_tagged_before_the_merge(
    tags: dict[str, str], expected: str
) -> None:
    assert last_release_before(tags, MERGED) == expected


def test_a_date_only_merge_time_counts_as_utc_midnight() -> None:
    tags = {"1.1.0": "2026-09-30T23:00:00Z", "1.2.0": "2026-10-01T00:00:01Z"}
    assert last_release_before(tags, "2026-10-01") == "1.1.0"


@pytest.mark.parametrize(
    "tags", [{}, {"1.4.0": "2026-11-01T00:00:00Z"}, {"nightly": "2026-01-01T00:00:00Z"}]
)
def test_no_release_before_the_merge_is_none(tags: dict[str, str]) -> None:
    assert last_release_before(tags, MERGED) is None


def tag_node(name: str, annotated: bool) -> dict[str, Any]:
    commit = {"__typename": "Commit", "committedDate": "2026-01-01T00:00:00Z"}
    if not annotated:
        return {"name": name, "target": commit}
    tagger = {"date": "2026-02-02T00:00:00Z"}
    return {"name": name, "target": {"__typename": "Tag", "tagger": tagger}}


def graphql_page(nodes: list[dict[str, Any]], cursor: str | None) -> dict[str, Any]:
    info = {"hasNextPage": cursor is not None, "endCursor": cursor}
    return {"data": {"repository": {"refs": {"pageInfo": info, "nodes": nodes}}}}


def test_tags_reads_every_page_with_each_tags_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = {
        None: graphql_page([tag_node("0.2.0", annotated=True)], "c1"),
        "c1": graphql_page([tag_node("0.1.0", annotated=False)], None),
    }
    sent: list[tuple[str, Any]] = []

    def post(url: str, headers: dict[str, str], body: Any = None) -> Any:
        sent.append((url, body["variables"]))
        return pages[body["variables"]["after"]]

    monkeypatch.setattr(github_module, "request_json", post)
    tags = GitHubApi("t").tags("acme/widgets")
    # An annotated tag is dated by its tagger; a lightweight one by its commit.
    assert tags == {"0.2.0": "2026-02-02T00:00:00Z", "0.1.0": "2026-01-01T00:00:00Z"}
    assert [url for url, _ in sent] == ["https://api.github.com/graphql"] * 2
    assert sent[0][1] == {"owner": "acme", "name": "widgets", "after": None}


def test_checkout_ref_clones_that_tag_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cloned: list[tuple[str, str, Path]] = []

    def clone(url: str, ref: str, dest: Path) -> None:
        cloned.append((url, ref, dest))
        (dest / ".git").mkdir(parents=True)

    monkeypatch.setattr(github_module, "_shallow_clone", clone)
    api, dest = GitHubApi("t"), tmp_path / "old"
    assert api.checkout_ref("acme/widgets", "0.1.0", dest) == dest
    api.checkout_ref("acme/widgets", "0.1.0", dest)
    assert cloned == [("https://github.com/acme/widgets.git", "0.1.0", dest)]
