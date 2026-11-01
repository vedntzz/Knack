from datetime import datetime
from pathlib import Path

from knack.day.models import CommitEvent
from knack.day.when import midnight, on_day
from knack.git import git_output

FIELD = "\x1f"
RECORD = "\x1e"
# sha, author, committer time, full message; the message may span lines.
LOG_FORMAT = "%H%x1f%an%x1f%cI%x1f%B%x1e"


def todays_commits(clone: Path, now: datetime) -> list[CommitEvent]:
    # HEAD's history since local midnight; outside git, or before a commit, none.
    since = f"--since={midnight(now).isoformat()}"
    out = git_output(clone, "log", since, f"--format={LOG_FORMAT}", "HEAD") or ""
    records = [record.strip() for record in out.split(RECORD)]
    commits = [_commit(record) for record in records if record]
    return [commit for commit in commits if on_day(commit.time, now)]


def _commit(record: str) -> CommitEvent:
    sha, author, time, message = record.split(FIELD, 3)
    first = (message.splitlines() or [""])[0]
    return CommitEvent(sha=sha, author=author, message=first, time=time)
