import re

from knack.contracts.models import Root
from knack.day.models import Seat

PR_NUMBER = re.compile(r"github\.com/[\w.-]+/[\w.-]+/pull/(\d+)")


def seats_of(roots: list[Root]) -> list[Seat]:
    # Only Confirmed roots block, so only they take a seat.
    return [_seat(root) for root in roots if root.status == "Confirmed"]


def _seat(root: Root) -> Seat:
    found = PR_NUMBER.search(str(root.source_url))
    return Seat(
        root_id=root.id,
        decided_by=root.decided_by,
        confirmed_by=root.confirmed_by,
        pr=int(found.group(1)) if found else None,
        merged_at=root.merged_at,
    )
