import os
import subprocess
import time
from pathlib import Path
from typing import IO, Protocol

from pydantic import BaseModel, ConfigDict

EXPORT_TIMEOUT_SECONDS = 300
# Variables that point Muse back at the user's config, or bench secrets the agent must not see.
LEAKY_ENV = (
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "XDG_CACHE_HOME",
    "KNACK_REGISTRY",
    "MODEL_API_KEY",
    "META_API_KEY",
    "BASETEN_API_KEY",
    "GITHUB_TOKEN",
)
# The variable Muse reads its Meta API key from, ahead of any account login.
MUSE_KEY_ENV = "META_API_KEY"


class ExecResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # None when the run was killed at the timeout.
    exit_code: int | None
    timed_out: bool
    duration_s: float


class Muse(Protocol):
    def exec(
        self,
        prompt: str,
        workspace: Path,
        home: Path,
        session_id: str,
        timeout: float,
        log: Path,
    ) -> ExecResult: ...

    def export(self, session_id: str, workspace: Path, home: Path, out: Path) -> Path:
        # The session's raw export, hook stdout included, written to out.
        ...


def muse_env(home: Path, api_key: str | None = None) -> dict[str, str]:
    # The arm home is the only config Muse can see; the key, when given, lives here only.
    env = {key: value for key, value in os.environ.items() if key not in LEAKY_ENV}
    env |= {"HOME": str(home), "MUSE_NO_AUTO_UPDATE": "1"}
    return env | ({MUSE_KEY_ENV: api_key} if api_key else {})


def exec_argv(prompt: str, session_id: str) -> list[str]:
    # Headless: no web tools, and no question that would wait for a human.
    flags = ["--disable-web-tools", "--disable-request-user-input"]
    return ["muse", "exec", *flags, "--session-id", session_id, prompt]


def export_argv(session_id: str, out: Path) -> list[str]:
    # Never --redacted: redaction blanks the hook stdout a deny is read from.
    return ["muse", "export", "--session", session_id, "--out", str(out)]


class MuseCli:
    # The key stays in memory and goes only into the muse exec environment.
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def exec(
        self,
        prompt: str,
        workspace: Path,
        home: Path,
        session_id: str,
        timeout: float,
        log: Path,
    ) -> ExecResult:
        started = time.monotonic()
        argv = exec_argv(prompt, session_id)
        env = muse_env(home, self._api_key)
        code, timed_out = _run_logged(argv, workspace, env, timeout, log)
        elapsed = time.monotonic() - started
        return ExecResult(exit_code=code, timed_out=timed_out, duration_s=elapsed)

    def export(self, session_id: str, workspace: Path, home: Path, out: Path) -> Path:
        _run_quietly(export_argv(session_id, out), workspace, home)
        return out


def _run_quietly(argv: list[str], cwd: Path, home: Path) -> None:
    # Muse prints the export path, which --parallel would interleave; keep it.
    env, limit = muse_env(home), EXPORT_TIMEOUT_SECONDS
    subprocess.run(
        argv, cwd=cwd, env=env, check=True, capture_output=True, timeout=limit
    )


def _run_logged(
    argv: list[str], cwd: Path, env: dict[str, str], timeout: float, log: Path
) -> tuple[int | None, bool]:
    # Output goes to log; a timeout kills muse and is reported, not raised.
    with log.open("wb") as out:
        try:
            done = _run(argv, cwd, env, timeout, out)
        except subprocess.TimeoutExpired:
            return None, True
    return done.returncode, False


def _run(
    argv: list[str], cwd: Path, env: dict[str, str], timeout: float, out: IO[bytes]
) -> subprocess.CompletedProcess[bytes]:
    null = subprocess.DEVNULL
    return subprocess.run(
        argv, cwd=cwd, env=env, timeout=timeout, stdin=null, stdout=out, stderr=out
    )
