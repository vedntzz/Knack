from pathlib import Path

from knack.bench.arms import registry_in
from knack.bench.attempts import Attempt, attempt_fields, attempts_of_run
from knack.bench.report import load_runs
from knack.bench.run import RunRecord


def reclassify(runs: Path, out: Path) -> list[RunRecord]:
    # Adds attempts from each run's saved export; agents are never rerun.
    records = [with_attempts(record) for record in load_runs(runs)]
    out.write_text(
        "".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8"
    )
    return records


def with_attempts(record: RunRecord) -> RunRecord:
    # A run the bench failed on stays unknown, never "did not attempt".
    found = None if record.error else _saved_attempts(record)
    return record.model_copy(update=attempt_fields(found))


def _saved_attempts(record: RunRecord) -> list[Attempt] | None:
    if not (record.export_path and record.sandbox and record.home):
        return None
    registry = registry_in(record.home, record.repo) / "registry.json"
    return attempts_of_run(record.export_path, record.sandbox, registry, record.rule)
