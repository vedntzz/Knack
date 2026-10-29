import subprocess
import urllib.error
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from knack.pipeline.http import request_bytes, request_json
from knack.pipeline.models import Post, PullSummary

API = "https://api.github.com"
PAGE = 100
# Search stops at 1000 results, so a week-wide window stays well under it.
SEARCH_CAP = 1000
WINDOW = timedelta(days=7)
LOOKBACK = timedelta(days=365)
CLONE_TIMEOUT_SECONDS = 1800
Window = tuple[datetime, datetime]
TAGS_QUERY = """query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    refs(refPrefix: "refs/tags/", first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { name target { __typename
        ... on Commit { committedDate }
        ... on Tag { tagger { date } } } }
    }
  }
}"""


def weekly_windows(now: datetime) -> Iterator[Window]:
    # Newest week first, back one year.
    end, floor = now, now - LOOKBACK
    while end > floor:
        start = max(end - WINDOW, floor)
        yield start, end
        end = start


def search_query(repo: str, start: datetime, end: datetime) -> str:
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    return f"repo:{repo} is:pr is:merged merged:{start:{stamp}}..{end:{stamp}}"


def summary_from_item(item: dict[str, Any]) -> PullSummary:
    fields = {key: item[key] for key in ("number", "title")}
    fields |= {"author": item["user"]["login"], "body": item["body"] or ""}
    merged_at = item["pull_request"]["merged_at"]
    return PullSummary.model_validate({**fields, "merged_at": merged_at})


class GitHubApi:
    def __init__(self, token: str) -> None:
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

    def merged_prs(self, repo: str) -> Iterator[PullSummary]:
        for start, end in weekly_windows(datetime.now(timezone.utc)):
            items = self._search(search_query(repo, start, end))
            items.sort(
                key=lambda item: str(item["pull_request"]["merged_at"]), reverse=True
            )
            yield from (summary_from_item(item) for item in items)

    def summary(self, repo: str, number: int) -> PullSummary:
        pr = self._get(f"/repos/{repo}/pulls/{number}")
        return summary_from_item({**pr, "pull_request": {"merged_at": pr["merged_at"]}})

    def changed_files(self, repo: str, number: int) -> list[str]:
        files = self._all(f"/repos/{repo}/pulls/{number}/files")
        return [str(f["filename"]) for f in files]

    def shas(self, repo: str, number: int) -> tuple[str, str]:
        pr = self._get(f"/repos/{repo}/pulls/{number}")
        return str(pr["base"]["sha"]), str(pr["head"]["sha"])

    def posts(self, repo: str, number: int) -> list[Post]:
        reviews = self._all(f"/repos/{repo}/pulls/{number}/reviews")
        comments = self._all(f"/repos/{repo}/issues/{number}/comments")
        return [review_post(r) for r in reviews] + [comment_post(c) for c in comments]

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        url = f"{API}/repos/{repo}/contents/{quote(path)}?ref={sha}"
        raw = {**self.headers, "Accept": "application/vnd.github.raw"}
        try:
            return request_bytes(url, raw).decode("utf-8")
        except urllib.error.HTTPError as error:
            return _none_if_missing(error)

    def checkout(self, repo: str, dest: Path) -> Path:
        # Reuses an earlier clone so reruns do not download the repo again.
        if not (dest / ".git").exists():
            branch = str(self._get(f"/repos/{repo}")["default_branch"])
            _shallow_clone(f"https://github.com/{repo}.git", branch, dest)
        return dest

    def tags(self, repo: str) -> dict[str, str]:
        # Every tag with its date; GraphQL dates 100 tags per call, REST one.
        tags, after = dict[str, str](), None
        while True:
            page, after = self._tag_page(repo, after)
            tags |= page
            if after is None:
                return tags

    def checkout_ref(self, repo: str, ref: str, dest: Path) -> Path:
        # A shallow clone at a tag, reused like the default-branch clone.
        if not (dest / ".git").exists():
            _shallow_clone(f"https://github.com/{repo}.git", ref, dest)
        return dest

    def _get(self, path: str, **params: object) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        return request_json(f"{API}{path}{query}", self.headers)

    def _tag_page(
        self, repo: str, after: str | None
    ) -> tuple[dict[str, str], str | None]:
        owner, name = repo.split("/")
        variables = {"owner": owner, "name": name, "after": after}
        body = {"query": TAGS_QUERY, "variables": variables}
        found = request_json(f"{API}/graphql", self.headers, body)
        refs = found["data"]["repository"]["refs"]
        page = {str(n["name"]): tag_date(n["target"]) for n in refs["nodes"]}
        return page, next_cursor(refs["pageInfo"])

    def _all(self, path: str) -> list[dict[str, Any]]:
        items, page = list[dict[str, Any]](), 1
        while chunk := self._get(path, per_page=PAGE, page=page):
            items += chunk
            page += 1
        return items

    def _search(self, query: str) -> list[dict[str, Any]]:
        items, page, more = list[dict[str, Any]](), 1, True
        while more and len(items) < SEARCH_CAP:
            found = self._get("/search/issues", q=query, per_page=PAGE, page=page)
            chunk = found["items"]
            items, page, more = items + chunk, page + 1, len(chunk) == PAGE
        return items


def next_cursor(page_info: dict[str, Any]) -> str | None:
    # None once the last page is read.
    return str(page_info["endCursor"]) if page_info["hasNextPage"] else None


def tag_date(target: dict[str, Any]) -> str:
    # An annotated tag is dated when it was tagged; a lightweight one by its commit.
    if target["__typename"] == "Tag":
        return str(target["tagger"]["date"])
    return str(target["committedDate"])


def review_post(review: dict[str, Any]) -> Post:
    heading = f"Review by {review['user']['login']} ({review['state']})"
    return Post(heading=heading, body=review["body"] or "")


def comment_post(comment: dict[str, Any]) -> Post:
    heading = f"Comment by {comment['user']['login']}"
    return Post(heading=heading, body=comment["body"] or "")


def _none_if_missing(error: urllib.error.HTTPError) -> None:
    # A 404 means the file does not exist at that sha; anything else is real.
    if error.code != 404:
        raise error


def _shallow_clone(url: str, branch: str, dest: Path) -> None:
    argv = ["git", "clone", "--depth", "1", "--branch", branch, url, str(dest)]
    subprocess.run(argv, check=True, capture_output=True, timeout=CLONE_TIMEOUT_SECONDS)
