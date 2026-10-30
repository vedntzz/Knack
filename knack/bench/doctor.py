import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from knack.bench.arms import prepare_home, registry_in
from knack.bench.muse import muse_env
from knack.bench.sandbox import BaseFiles, build_sandbox
from knack.bench.tickets import BenchTicket, load_tickets
from knack.guard.runner import AST_GREP
from knack.pipeline.github import GitHubApi
from knack.pipeline.ports import Spark
from knack.pipeline.spark import SparkApi
from knack.pipeline.spark_open import SparkOpenApi

KEYS = ("GITHUB_TOKEN", "MODEL_API_KEY", "BASETEN_API_KEY")
PINNED_AST_GREP = "0.51.0"
# The arm with the most hooks, so its home exercises every hook entry.
DOCTOR_ARM = "warn+veto"
PING = "Reply with the single word: ok"
VERSION_TIMEOUT_SECONDS = 30


class DoctorFailure(Exception):
    pass


class DoctorGitHub(BaseFiles, Protocol):
    def viewer(self) -> str: ...


class Check(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    ok: bool
    reason: str


@dataclass(frozen=True)
class DoctorKit:
    env: Mapping[str, str]
    github: Callable[[str], DoctorGitHub]
    spark: Callable[[str], Spark]
    spark_open: Callable[[str], Spark]
    which: Callable[[str], str | None]
    # argv -> the first line it prints; raises when the command fails.
    version: Callable[[list[str]], str]
    tickets: Path
    real_home: Path
    cache: Path
    # Sandbox and home are built here and thrown away.
    scratch: Path


def run_doctor(kit: DoctorKit) -> list[Check]:
    # Every check runs, even after a failure, so one pass shows everything to fix.
    return [_checked(name, probe, kit) for name, probe in CHECKS]


def format_checks(checks: list[Check]) -> str:
    lines = [f"{'PASS' if c.ok else 'FAIL'} {c.name}: {c.reason}" for c in checks]
    return "\n".join(lines)


def doctor(kit: DoctorKit) -> bool:
    # Prints one PASS/FAIL line per check; True only when every check passed.
    checks = run_doctor(kit)
    print(format_checks(checks), flush=True)
    return all(check.ok for check in checks)


def live_doctor(tickets: Path, cache: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="doctor_") as scratch:
        return doctor(live_kit(tickets, cache, Path(scratch)))


def live_kit(tickets: Path, cache: Path, scratch: Path) -> DoctorKit:
    clients = (GitHubApi, SparkApi, SparkOpenApi, shutil.which, version_line)
    return DoctorKit(os.environ, *clients, tickets, Path.home(), cache, scratch)


def version_line(argv: list[str]) -> str:
    # No bench secret and no auto-update reach the version command.
    limit, env = VERSION_TIMEOUT_SECONDS, muse_env(Path.home())
    done = subprocess.run(
        argv, env=env, capture_output=True, text=True, timeout=limit, check=True
    )
    return done.stdout.strip().splitlines()[0]


def _checked(name: str, probe: Callable[[DoctorKit], str], kit: DoctorKit) -> Check:
    # A probe's exception is its FAIL reason; a key never reaches any reason.
    try:
        reason, ok = probe(kit), True
    except Exception as error:
        reason, ok = _described(error), False
    return Check(name=name, ok=ok, reason=_redacted(reason, kit.env))


def _described(error: Exception) -> str:
    if isinstance(error, DoctorFailure):
        return str(error)
    return f"{type(error).__name__}: {error}"


def _redacted(text: str, env: Mapping[str, str]) -> str:
    for secret in (env.get(name) for name in KEYS):
        text = text.replace(secret, "***") if secret else text
    return text


def _key(kit: DoctorKit, name: str) -> str:
    value = kit.env.get(name)
    if not value:
        raise DoctorFailure(f"{name} is not set")
    return value


def _github(kit: DoctorKit) -> str:
    login = kit.github(_key(kit, "GITHUB_TOKEN")).viewer()
    return f"authenticated as {login}"


def _spark(kit: DoctorKit) -> str:
    return _answered(kit.spark(_key(kit, "MODEL_API_KEY")))


def _spark_open(kit: DoctorKit) -> str:
    return _answered(kit.spark_open(_key(kit, "BASETEN_API_KEY")))


def _answered(spark: Spark) -> str:
    if not spark.ask(PING).strip():
        raise DoctorFailure(f"{spark.model} gave an empty answer")
    return f"{spark.model} answered"


def _muse(kit: DoctorKit) -> str:
    path = kit.which("muse")
    if path is None:
        raise DoctorFailure("muse is not on PATH")
    return f"{path}, {kit.version([path, '--version'])}"


def _ast_grep(kit: DoctorKit) -> str:
    # The binary the guard itself runs, at the pinned version.
    found = f"{kit.version([str(AST_GREP), '--version'])} at {AST_GREP}"
    if PINNED_AST_GREP not in found.split():
        raise DoctorFailure(f"{found}; pinned {PINNED_AST_GREP}")
    return found


def _tickets(kit: DoctorKit) -> str:
    return f"{len(_loaded(kit))} ticket(s) load from {kit.tickets}"


def _loaded(kit: DoctorKit) -> list[BenchTicket]:
    tickets = load_tickets(kit.tickets)
    if not tickets:
        raise DoctorFailure(f"no tickets in {kit.tickets}")
    return tickets


def _sandbox(kit: DoctorKit) -> str:
    ticket = _loaded(kit)[0]
    github = kit.github(_key(kit, "GITHUB_TOKEN"))
    root = kit.scratch / "sandboxes"
    root.mkdir(parents=True, exist_ok=True)
    build_sandbox(ticket, root, github, kit.cache)
    return f"{ticket.id}: {len(ticket.files)} file(s) at {ticket.base_sha[:7]}"


def _arm_home(kit: DoctorKit) -> str:
    ticket = _loaded(kit)[0]
    source = registry_in(kit.real_home, ticket.repo) / "registry.json"
    root = kit.scratch / "homes"
    root.mkdir(parents=True, exist_ok=True)
    prepare_home(DOCTOR_ARM, source, root)
    return f"{DOCTOR_ARM} home prepared for {ticket.repo}"


CHECKS: list[tuple[str, Callable[[DoctorKit], str]]] = [
    ("GITHUB_TOKEN", _github),
    ("MODEL_API_KEY", _spark),
    ("BASETEN_API_KEY", _spark_open),
    ("muse", _muse),
    ("ast-grep", _ast_grep),
    ("tickets", _tickets),
    ("sandbox", _sandbox),
    ("arm home", _arm_home),
]
