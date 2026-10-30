import argparse
import json
import os
import sys
import tempfile
import uuid
from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from knack.bench.arms import ARMS, prepare_home, registry_in
from knack.bench.attempts import Attempt, attempt_fields, attempts_of_run
from knack.bench.blind import BlindLabel, judge_blind
from knack.bench.classify import (
    assess,
    BlockSignal,
    denies_in_export,
    DiffLabel,
    Outcome,
    RuleHit,
)
from knack.bench.doctor import live_doctor
from knack.bench.muse import ExecResult, Muse, MuseCli
from knack.bench.sandbox import BaseFiles, build_sandbox
from knack.bench.tickets import BenchTicket, load_tickets
from knack.pipeline.github import GitHubApi
from knack.pipeline.ports import Spark
from knack.pipeline.spark_open import SparkOpenApi

JsonDict = dict[str, Any]
Label = Literal["blocked", "rejected_path", "correct", "other"]
Job = tuple[BenchTicket, str, str]
DEFAULT_TIMEOUT_SECONDS = 1800
TOKENS = ("GITHUB_TOKEN", "BASETEN_API_KEY", "MODEL_API_KEY")
# Fields kept from each deny, so a reader can check what the hook returned.
EVIDENCE = ("signal", "effects", "stdout", "status", "duration_ms")


class RunRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    ticket: str
    repo: str
    rule: str
    arm: str
    # Label is "blocked" on any deny; diff_label scores the final diff regardless.
    label: Label = "other"
    diff_label: DiffLabel = "other"
    session_id: str | None = None
    sandbox: Path | None = None
    home: Path | None = None
    started_at: str | None = None
    duration_s: float | None = None
    exit_code: int | None = None
    timed_out: bool = False
    denies: int = 0
    # "exact" when Muse marked a block, "inferred" when only the fallback saw one.
    block_signal: BlockSignal | None = None
    deny_evidence: list[JsonDict] = []
    rule_hits: list[RuleHit] = []
    diff_empty: bool = True
    diff_path: Path | None = None
    export_path: Path | None = None
    blind: BlindLabel | None = None
    # Whether the judge's yes/no matches diff_label; None when it gave no answer.
    agree: bool | None = None
    flagged: bool = True
    # Set when the bench itself failed; the run is then "other" and flagged.
    error: str | None = None
    # A write/edit call proposed a new rule match, blocked or not; None when not replayed.
    attempted: bool | None = None
    attempts: list[Attempt] = []


@dataclass(frozen=True)
class RunSetup:
    work: Path
    github: BaseFiles
    muse: Muse
    judge: Spark
    cache: Path
    real_home: Path
    timeout_s: float


@dataclass(frozen=True)
class Place:
    sandbox: Path
    home: Path
    run_dir: Path


@dataclass(frozen=True)
class AgentRun:
    session_id: str
    place: Place
    result: ExecResult
    export_path: Path
    started_at: str


def run_one(ticket: BenchTicket, arm: str, run_id: str, setup: RunSetup) -> RunRecord:
    # Sandbox, arm home, agent, export, then labels.
    run_dir = _new_dir(setup.work / "runs" / run_id)
    sandbox = _sandbox(ticket, setup)
    home = _arm_home(arm, ticket, setup)
    agent = _agent_run(ticket, Place(sandbox, home, run_dir), setup)
    return _record(ticket, arm, run_id, agent, setup)


def run_all(jobs: list[Job], setup: RunSetup, parallel: int, out: Path) -> None:
    # Runs in parallel; only this thread appends, one line per finished run.
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = [pool.submit(_safe_run, *job, setup) for job in jobs]
        for future in as_completed(futures):
            append_record(out, future.result())


def append_record(out: Path, record: RunRecord) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    setup = _ready_setup(args)
    if not isinstance(setup, RunSetup):
        return setup
    jobs = _jobs(load_tickets(args.tickets), args.arms, args.repeats)
    run_all(jobs, setup, args.parallel, args.out)
    return 0


def _sandbox(ticket: BenchTicket, setup: RunSetup) -> Path:
    root = _dir(setup.work / "sandboxes")
    return build_sandbox(ticket, root, setup.github, setup.cache)


def _arm_home(arm: str, ticket: BenchTicket, setup: RunSetup) -> Path:
    source = registry_in(setup.real_home, ticket.repo) / "registry.json"
    return prepare_home(arm, source, _dir(setup.work / "homes"))


def _agent_run(ticket: BenchTicket, place: Place, setup: RunSetup) -> AgentRun:
    session_id, started = str(uuid.uuid4()), datetime.now(timezone.utc).isoformat()
    result = _exec(ticket, place, session_id, setup)
    out = place.run_dir / "export.json"
    exported = setup.muse.export(session_id, place.sandbox, place.home, out)
    return AgentRun(session_id, place, result, exported, started)


def _exec(
    ticket: BenchTicket, place: Place, session_id: str, setup: RunSetup
) -> ExecResult:
    log = place.run_dir / "muse.log"
    where = (place.sandbox, place.home)
    return setup.muse.exec(ticket.ticket, *where, session_id, setup.timeout_s, log)


def _record(
    ticket: BenchTicket, arm: str, run_id: str, agent: AgentRun, setup: RunSetup
) -> RunRecord:
    outcome = _assess(ticket, agent.place)
    (agent.place.run_dir / "diff.patch").write_text(outcome.diff, encoding="utf-8")
    blind = _judge(setup.judge, ticket, outcome)
    labels = _labels(outcome, _denies(agent), blind)
    fields = _identity(ticket, arm, run_id) | _agent_fields(agent) | labels
    return RunRecord.model_validate(fields | _attempt_fields(ticket, agent))


def _attempt_fields(ticket: BenchTicket, agent: AgentRun) -> JsonDict:
    registry = registry_in(agent.place.home, ticket.repo) / "registry.json"
    where = (agent.export_path, agent.place.sandbox, registry)
    return attempt_fields(attempts_of_run(*where, ticket.rule))


def _assess(ticket: BenchTicket, place: Place) -> Outcome:
    # The rule comes from the run's own bench registry, the one its hooks used.
    registry = registry_in(place.home, ticket.repo) / "registry.json"
    return assess(ticket, place.sandbox, registry)


def _judge(judge: Spark, ticket: BenchTicket, outcome: Outcome) -> BlindLabel:
    seen = (ticket.ticket, outcome.alternatives, outcome.diff)
    return judge_blind(judge, *seen, outcome.diff_empty)


def _denies(agent: AgentRun) -> list[JsonDict]:
    return denies_in_export(json.loads(agent.export_path.read_text(encoding="utf-8")))


def _labels(outcome: Outcome, denies: list[JsonDict], blind: BlindLabel) -> JsonDict:
    agree = _agree(blind, outcome.diff_label)
    scored = outcome.model_dump(include={"diff_label", "diff_empty"})
    scored |= {"label": "blocked" if denies else outcome.diff_label}
    judged = {"blind": blind, "agree": agree, "flagged": agree is not True}
    return scored | judged | _deny_fields(denies) | {"rule_hits": outcome.hits}


def _agree(blind: BlindLabel, diff_label: DiffLabel) -> bool | None:
    if blind.label is None:
        return None
    return (blind.label == "yes") == (diff_label == "rejected_path")


def _deny_fields(denies: list[JsonDict]) -> JsonDict:
    evidence = [{key: deny.get(key) for key in EVIDENCE} for deny in denies]
    signals = {deny["signal"] for deny in denies}
    strongest = "exact" if "exact" in signals else ("inferred" if signals else None)
    return {"denies": len(denies), "deny_evidence": evidence, "block_signal": strongest}


def _identity(ticket: BenchTicket, arm: str, run_id: str) -> JsonDict:
    named = {"run_id": run_id, "ticket": ticket.id, "arm": arm}
    return named | {"repo": ticket.repo, "rule": ticket.rule}


def _agent_fields(agent: AgentRun) -> JsonDict:
    place, diff = agent.place, agent.place.run_dir / "diff.patch"
    files = {"sandbox": place.sandbox, "home": place.home, "diff_path": diff}
    run: JsonDict = {"session_id": agent.session_id, "started_at": agent.started_at}
    run["export_path"] = agent.export_path
    return files | run | agent.result.model_dump()


def _safe_run(ticket: BenchTicket, arm: str, run_id: str, setup: RunSetup) -> RunRecord:
    # One run's failure is recorded as its own line; the rest of the batch goes on.
    try:
        return run_one(ticket, arm, run_id, setup)
    except Exception as error:
        message = f"{type(error).__name__}: {error}"
        return RunRecord.model_validate(
            _identity(ticket, arm, run_id) | {"error": message}
        )


def _jobs(tickets: list[BenchTicket], arms: list[str], repeats: int) -> list[Job]:
    # Run ids carry a stamp, so a second batch appended to the same file never collides.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = [(t, arm, n) for t in tickets for arm in arms for n in range(repeats)]
    return [(t, arm, f"{stamp}-{t.id}--{arm}--{n}") for t, arm, n in runs]


def _ready_setup(args: argparse.Namespace) -> RunSetup | int:
    # Refused before any run: a batch to mix into (2), a failed doctor (1), no keys (2).
    if _mixes_batches(args.out, args.append):
        return 2
    if not (args.skip_doctor or live_doctor(args.tickets, args.cache)):
        return 1
    return _live_setup(args) or 2


def _mixes_batches(out: Path, append: bool) -> bool:
    if append or not out.exists():
        return False
    print(f"knack bench: {out} exists; pass --append to add to it", file=sys.stderr)
    return True


def _live_setup(args: argparse.Namespace) -> RunSetup | None:
    # Missing tokens are operator error: a message and exit 2, no traceback.
    missing = [name for name in TOKENS if not os.environ.get(name)]
    if missing:
        print(f"knack bench: set {', '.join(missing)}", file=sys.stderr)
        return None
    return _setup(args, *(os.environ[name] for name in TOKENS))


def _setup(
    args: argparse.Namespace, github_token: str, judge_key: str, model_key: str
) -> RunSetup:
    work = args.work or Path(tempfile.mkdtemp(prefix="work_"))
    github, judge = GitHubApi(github_token), SparkOpenApi(judge_key)
    clients = (github, MuseCli(api_key=model_key), judge)
    return RunSetup(work, *clients, args.cache, Path.home(), args.timeout)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m knack.bench.run")
    parser.add_argument("--tickets", type=Path, default=Path("bench/tickets.jsonl"))
    parser.add_argument("--arms", nargs="+", choices=sorted(ARMS), default=sorted(ARMS))
    _add_counts(parser)
    _add_paths(parser)
    _add_switches(parser)
    return parser


def _add_switches(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--append", action="store_true", help="add to an existing --out"
    )
    parser.add_argument("--skip-doctor", action="store_true", help="for tests only")


def _add_counts(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repeats", type=_positive, default=1)
    parser.add_argument("--parallel", type=_positive, default=1)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)


def _add_paths(parser: argparse.ArgumentParser) -> None:
    # Work defaults to a fresh temp folder: sandbox paths must not name the bench.
    parser.add_argument("--out", type=Path, default=Path("bench/runs.jsonl"))
    parser.add_argument("--work", type=Path, default=None)
    parser.add_argument(
        "--cache", type=Path, default=Path.home() / ".knack/cache/bench"
    )


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value} is not a positive count")
    return number


def _new_dir(path: Path) -> Path:
    # Run ids are unique, so an existing run folder is a bench bug, not a rerun.
    path.mkdir(parents=True)
    return path


def _dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
