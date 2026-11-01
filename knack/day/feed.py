from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from knack.console.verdict import home_registry_for
from knack.contracts.models import Root
from knack.day.commits import todays_commits
from knack.day.models import Day, DayFeed, Event, ReceiptEvent
from knack.day.pulls import PullsRead, todays_pulls
from knack.day.receipts import todays_receipts
from knack.day.roots import ReadRoots, registry_roots
from knack.day.seats import seats_of
from knack.day.when import moment
from knack.dispute.rulings import rulings_path
from knack.git import current_branch, origin_repo
from knack.pipeline.clients import github_client, MissingCredentials
from knack.pipeline.github import GitHubApi
from knack.receipts.chain import receipts_path
from knack.receipts.warns import warns_path

__all__ = ["Day", "day_feed", "day_json", "local_day"]


def day_json(day: Day) -> str:
    # The one serialization the CLI prints and the console serves.
    return day_feed(day).model_dump_json(indent=2)


def day_feed(day: Day) -> DayFeed:
    # Read-only: git, GitHub and the stores are read, nothing is written.
    now, repo, branch = day.clock(), origin_repo(day.clone), current_branch(day.clone)
    roots, registry_error = _roots(day, repo)
    pulls, pulls_error = _pulls(day, repo, branch, now)
    found = [*todays_commits(day.clone, now), *pulls, *_receipts(day, repo, roots, now)]
    return DayFeed(
        repo=repo,
        branch=branch,
        date=now.date().isoformat(),
        events=_oldest_first(found, now),
        pulls_error=pulls_error,
        seats=seats_of(roots),
        registry_error=registry_error,
    )


def _oldest_first(found: Sequence[Event], now: datetime) -> list[Event]:
    return sorted(found, key=lambda event: moment(event.time) or now)


def local_day(clone: Path) -> Day:
    # This machine's stores, clock, home registry and GitHub token.
    return Day(
        clone=clone,
        clock=lambda: datetime.now().astimezone(),
        receipts=receipts_path(),
        warns=warns_path(),
        rulings=rulings_path(),
        pulls=_github_or_none(),
        registry_for=home_registry_for,
    )


def _pulls(day: Day, repo: str | None, branch: str | None, now: datetime) -> PullsRead:
    # No origin or a detached HEAD has no branch to ask GitHub about.
    if repo is None or branch is None:
        return [], None
    return todays_pulls(day.pulls, repo, branch, now)


def _roots(day: Day, repo: str | None) -> ReadRoots:
    # The console's registry read: the same roots, the same error text.
    return ([], None) if repo is None else registry_roots(day.registry_for(repo))


def _receipts(
    day: Day, repo: str | None, roots: list[Root], now: datetime
) -> list[ReceiptEvent]:
    return [] if repo is None else todays_receipts(day, repo, roots, now)


def _github_or_none() -> GitHubApi | None:
    try:
        return github_client()
    except MissingCredentials:
        return None
