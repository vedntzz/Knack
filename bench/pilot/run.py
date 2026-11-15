import argparse
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from bench.pilot.arm import ArmUsage, run_arm
from bench.pilot.candidates import file_sha256, load_candidates, PilotCandidate
from bench.pilot.score import final_diff, final_hits, is_repeat, make_sandbox
from knack.bench.blind import judge_blind
from knack.bench.sandbox import BaseFiles
from knack.pipeline.ports import Spark
from pydantic import BaseModel, ConfigDict

PILOT = Path(__file__).parent
REPO_ROOT = PILOT.parents[1]
DEFAULT_MODEL = "claude-opus-5-5"
REGISTERED = re.compile(r"`bench/pilot/candidates\.jsonl` sha256 `([0-9a-f]{64})`")
Agent = Callable[[Path, str, str], ArmUsage]


class PilotRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    run: int
    model: str
    started_at: str
    usage: ArmUsage | None = None
    rule_hits: list[str] = []
    blind: str | None = None
    blind_model: str | None = None
    blind_raw: str | None = None
    repeat: bool = False
    diff_path: str | None = None
    # A bench failure: the run is excluded and listed, never re-run.
    error: str | None = None


@dataclass(frozen=True)
class PilotSetup:
    work: Path
    artifacts: Path
    rules: Path
    model: str
    base: BaseFiles
    cache: Path
    judge: Spark
    agent: Agent


class FixtureBase:
    # Serves base files from bench/pilot/fixtures/<id>/base, the tree each rule was proven on.
    def __init__(self, fixtures: Path, ids_by_base_sha: dict[str, str]) -> None:
        self.fixtures = fixtures
        self.ids_by_base_sha = ids_by_base_sha

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        found = self.fixtures / self.ids_by_base_sha.get(sha, "\0") / "base" / path
        return found.read_text(encoding="utf-8") if found.is_file() else None


def run_one(candidate: PilotCandidate, run: int, setup: PilotSetup) -> PilotRecord:
    # Any bench failure becomes a recorded error; it never stops the batch.
    started = datetime.now(UTC).isoformat(timespec="seconds")
    identity: dict[str, object] = {
        "id": candidate.id,
        "run": run,
        "model": setup.model,
        "started_at": started,
    }
    try:
        return PilotRecord.model_validate(identity | _scored(candidate, run, setup))
    except Exception as error:
        return PilotRecord.model_validate(
            identity | {"error": f"{type(error).__name__}: {error}"}
        )


def judge_ready(judge: Spark) -> bool:
    # A dead judge would score every run "not a repeat"; check before any agent spend.
    try:
        return bool(judge.ask("Reply with the single word ok."))
    except Exception:
        return False


def registered_hash(prereg: Path) -> str | None:
    found = REGISTERED.search(prereg.read_text(encoding="utf-8"))
    return found.group(1) if found else None


def unregistered(candidates: Path, prereg: Path) -> bool:
    # True when the candidates file is not byte-identical to the one pre-registered.
    return registered_hash(prereg) != file_sha256(candidates)


def base_files(
    candidate: PilotCandidate, base: BaseFiles, cache: Path
) -> dict[str, str]:
    return {
        name: _cached_base(candidate, name, base, cache) for name in candidate.files
    }


def _scored(
    candidate: PilotCandidate, run: int, setup: PilotSetup
) -> dict[str, object]:
    sandbox = make_sandbox(setup.work, base_files(candidate, setup.base, setup.cache))
    usage = setup.agent(sandbox, candidate.ticket, setup.model)
    diff, hits = final_diff(sandbox), final_hits(sandbox, setup.rules / candidate.rule)
    blind = judge_blind(
        setup.judge, candidate.ticket, [candidate.rejected_path], diff, not diff
    )
    kept = _keep_diff(setup.artifacts, candidate.id, run, diff)
    return {
        "usage": usage,
        "rule_hits": hits,
        "blind": blind.label,
        "blind_model": blind.model,
        "blind_raw": blind.raw or blind.error,
        "repeat": is_repeat(hits, blind.label),
        "diff_path": str(kept),
    }


def _cached_base(
    candidate: PilotCandidate, name: str, base: BaseFiles, cache: Path
) -> str:
    stored = cache / candidate.base_sha / name
    if not stored.is_file():
        text = base.file_at(candidate.repo, candidate.base_sha, name)
        if text is None:
            raise FileNotFoundError(f"{name} not at {candidate.base_sha}")
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_text(text, encoding="utf-8")
    return stored.read_text(encoding="utf-8")


def _keep_diff(artifacts: Path, candidate_id: str, run: int, diff: str) -> Path:
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / f"{candidate_id}.run{run}.diff"
    path.write_text(diff, encoding="utf-8")
    return path


def _live_setup(args: argparse.Namespace) -> PilotSetup:
    from knack.pipeline.spark_open import SparkOpenApi

    ids = {c.base_sha: c.id for c in load_candidates(args.candidates)}
    return PilotSetup(
        work=args.work,
        artifacts=args.artifacts,
        rules=PILOT / "rules",
        model=args.model,
        base=FixtureBase(PILOT / "fixtures", ids),
        cache=args.work / "base-cache",
        judge=SparkOpenApi(os.environ["BASETEN_API_KEY"]),
        agent=run_arm,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KN-215a repeat-rate pilot (no Knack arm)"
    )
    parser.add_argument("--candidates", type=Path, default=PILOT / "candidates.jsonl")
    parser.add_argument("--prereg", type=Path, default=REPO_ROOT / "PREREG-PILOT.md")
    parser.add_argument("--ids", nargs="*", help="run only these candidate ids")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work", type=Path, default=Path("/tmp/knack-pilot-work"))
    parser.add_argument("--artifacts", type=Path, default=PILOT / "artifacts")
    return parser


def _chosen(args: argparse.Namespace) -> list[PilotCandidate]:
    candidates = load_candidates(args.candidates)
    return [c for c in candidates if not args.ids or c.id in args.ids]


def main(argv: list[str] | None = None) -> int:
    # Refuses to run unless the candidates file matches the hash in PREREG-PILOT.md.
    args = _parser().parse_args(argv)
    if unregistered(args.candidates, args.prereg):
        print("pilot: candidates.jsonl does not match PREREG-PILOT.md", file=sys.stderr)
        return 2
    setup = _live_setup(args)
    if not judge_ready(setup.judge):
        print("pilot: the blind judge is not answering; fix it first", file=sys.stderr)
        return 3
    for candidate in _chosen(args):
        for run in range(args.repeats):
            _append(args.out, run_one(candidate, run, setup))
    return 0


def _append(out: Path, record: PilotRecord) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    print(f"{record.id} run{record.run} repeat={record.repeat} error={record.error}")


if __name__ == "__main__":
    sys.exit(main())
