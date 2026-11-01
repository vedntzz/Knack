import os
from pathlib import Path

# The one place knack reads the user's home; every other module asks here.
KNACK_HOME_ENV = "KNACK_HOME"


def knack_home() -> Path:
    # KNACK_HOME wins; unset or empty, ~/.knack.
    value = os.environ.get(KNACK_HOME_ENV)
    return expand_user_path(value) if value else user_home() / ".knack"


def user_home() -> Path:
    # The real home, for files other tools own, such as Muse's settings.
    return Path.home()


def expand_user_path(value: str) -> Path:
    # A user-given path with ~ expanded, made absolute.
    return Path(value).expanduser().resolve()
