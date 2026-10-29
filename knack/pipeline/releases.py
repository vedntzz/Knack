import re
from datetime import datetime, timezone

# Plain X.Y.Z releases, optionally v-prefixed; rc, beta and other tags are skipped.
RELEASE = re.compile(r"v?\d+\.\d+\.\d+")


def last_release_before(tags: dict[str, str], merged_at: str) -> str | None:
    # The release tagged last before the merge, so its code cannot hold the PR.
    merged = _instant(merged_at)
    dated = [(_instant(d), t) for t, d in tags.items() if RELEASE.fullmatch(t)]
    earlier = [(when, tag) for when, tag in dated if when < merged]
    return max(earlier)[1] if earlier else None


def _instant(stamp: str) -> datetime:
    # GitHub stamps end in Z; a date-only merge time is UTC midnight.
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
