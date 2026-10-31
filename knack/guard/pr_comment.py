import json
import sys
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knack.contracts.models import Root
from knack.guard.check import check_file
from knack.guard.runner import scan_file_with_rule

JsonDict = dict[str, Any]
DEFAULT_API = "https://api.github.com"
TIMEOUT_SECONDS = 10
# The workflow sets all four; GITHUB_REPOSITORY comes from Actions itself.
PR_ENV = ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "PR_NUMBER", "HEAD_SHA")
# The quote is a Markdown blockquote, one "> " per line, its text left as written.
COMMENT_TEMPLATE = (
    "**Knack blocked this line.**\n\n"
    "**Decision:** {decision}\n"
    "**Decided by:** {decided_by}\n\n"
    "{quote}\n\n"
    "**Source:** {source_url}\n"
)


@dataclass(frozen=True)
class PullRequest:
    api: str
    repo: str
    number: str
    head_sha: str
    token: str


def pull_request_from_env(env: Mapping[str, str]) -> PullRequest | None:
    # Any value missing (a local run, say) means no comment, never an error.
    if not all(env.get(name) for name in PR_ENV):
        return None
    token, repo, number, head_sha = (env[name] for name in PR_ENV)
    return PullRequest(
        env.get("GITHUB_API_URL") or DEFAULT_API, repo, number, head_sha, token
    )


def comment_body(root: Root) -> str:
    quote = "\n".join(f"> {line}" for line in root.quote.split("\n"))
    fields = {"decision": root.decision, "decided_by": root.decided_by}
    return COMMENT_TEMPLATE.format(**fields, quote=quote, source_url=root.source_url)


def review_payload(pr: PullRequest, path: Path, line: int, body: str) -> JsonDict:
    # RIGHT is the head side of the diff, where the blocked line now lives.
    return {
        "body": body,
        "commit_id": pr.head_sha,
        "path": path.as_posix(),
        "line": line,
        "side": "RIGHT",
    }


def comment_on_block(
    file: Path, rule: Path, root_path: Path, env: Mapping[str, str], log: Path
) -> int:
    # One review comment per blocked line; returns how many GitHub accepted.
    pr = _required_pull_request(env)
    root = Root.model_validate_json(root_path.read_text(encoding="utf-8"))
    body = comment_body(root)
    lines = blocked_lines(file, rule, root, log)
    return sum(post_quietly(pr, review_payload(pr, file, n, body)) for n in lines)


def _required_pull_request(env: Mapping[str, str]) -> PullRequest:
    pr = pull_request_from_env(env)
    if pr is None:
        raise LookupError(f"needs {', '.join(PR_ENV)} set; no comment posted")
    return pr


def blocked_lines(file: Path, rule: Path, root: Root, log: Path) -> list[int]:
    # The same verdict the check step gave; its lines come from a rescan.
    if check_file(file, rule, rule.stem, root, log).allowed:
        return []
    return sorted({match.line for match in scan_file_with_rule(file, rule)})


def post_quietly(pr: PullRequest, payload: JsonDict) -> bool:
    # A refused or failed post is reported, never raised; the token is never printed.
    try:
        post_comment(pr, payload)
        return True
    except Exception as error:
        where = f"{payload['path']}:{payload['line']}"
        print(f"knack guard comment: not posted on {where}: {error}", file=sys.stderr)
        return False


def post_comment(pr: PullRequest, payload: JsonDict) -> None:
    url = f"{pr.api}/repos/{pr.repo}/pulls/{pr.number}/comments"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data, _headers(pr.token), method="POST")
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):
        pass


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
