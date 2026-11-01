from datetime import datetime, UTC


def moment(time: str) -> datetime | None:
    # Naive times read as UTC; unparseable ones are None.
    try:
        at = datetime.fromisoformat(time)
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def on_day(time: str, now: datetime) -> bool:
    # On now's calendar day, in now's timezone.
    at = moment(time)
    return at is not None and at.astimezone(now.tzinfo).date() == now.date()


def midnight(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
