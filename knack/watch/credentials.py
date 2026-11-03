import os
import stat
from pathlib import Path

from knack.home import knack_home
from knack.pipeline.clients import (
    MissingCredentials,
    RefusedCredentials,
    required_env,
    usable_key,
)

# Hooks do not inherit the shell's environment, so watch also reads each key from a file.
# Each key's file is its name in lower case, e.g. $KNACK_HOME/github_token.
KEY_FILES = {
    name: name.lower() for name in ("GITHUB_TOKEN", "MODEL_API_KEY", "BASETEN_API_KEY")
}
NOT_FOUND = (
    "{name} is not set and {path} does not exist; "
    "export {name}, or put it in {path} (chmod 600)"
)
OPEN_FILE = "{path} is mode {mode:o}, so others can read it; run chmod 600 {path}"
EMPTY_FILE = "{path} is empty; put {name} in it"


def watch_key(name: str) -> str:
    # The env var wins; unset or empty, its file in $KNACK_HOME.
    from_env = os.environ.get(name)
    return required_env(name) if from_env else _key_from_file(name, key_path(name))


def key_path(name: str) -> Path:
    return knack_home() / KEY_FILES[name]


def _key_from_file(name: str, path: Path) -> str:
    # Messages name the path, never the key.
    if not path.is_file():
        raise MissingCredentials(NOT_FOUND.format(name=name, path=path))
    _refuse_if_others_can_read(path)
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RefusedCredentials(EMPTY_FILE.format(name=name, path=path))
    return usable_key(key, str(path))


def _refuse_if_others_can_read(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise RefusedCredentials(OPEN_FILE.format(path=path, mode=mode))
