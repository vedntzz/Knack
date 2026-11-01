from datetime import datetime
from typing import Any

from knack.day.models import BranchPulls, PullEvent
from knack.day.when import on_day

NO_TOKEN = "GITHUB_TOKEN is not set"
# Network and HTTP errors, a rate-limit give-up, or a body not shaped like a pull.
PULL_ERRORS = (OSError, RuntimeError, ValueError, KeyError, TypeError)
# Today's PRs, and why none could be read.
PullsRead = tuple[list[PullEvent], str | None]


def todays_pulls(
    pulls: BranchPulls | None, repo: str, branch: str, now: datetime
) -> PullsRead:
    if pulls is None:
        return [], NO_TOKEN
    try:
        found = [_event(pull) for pull in pulls.branch_pulls(repo, branch)]
    except PULL_ERRORS as error:
        return [], f"GitHub unreachable: {error}"
    return _once_each_today(found, now), None


def _event(pull: dict[str, Any]) -> PullEvent | None:
    # Closed without merging is no event.
    merged = pull["merged_at"]
    if not merged and pull["state"] != "open":
        return None
    state = "merged" if merged else "open"
    time = str(merged or pull["created_at"])
    return PullEvent(number=pull["number"], title=pull["title"], state=state, time=time)


def _once_each_today(found: list[PullEvent | None], now: datetime) -> list[PullEvent]:
    # A PR both from and into the branch is listed once.
    today = [pull for pull in found if pull and on_day(pull.time, now)]
    return list({pull.number: pull for pull in today}.values())
