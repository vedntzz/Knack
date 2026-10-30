from pathlib import Path

from pydantic import ValidationError

from knack.bench.run import RunRecord

LABELS = ("blocked", "rejected_path", "correct", "other")
# A blocked run is an attempt at the rejected path the guard stopped.
REPEATS = {"blocked", "rejected_path"}
HEADER = "| Arm | Runs | Blocked | Recovered | Rejected path | Correct | Other | Repeat rate | Attempt rate | Judge agreement |"
FLAG_HEADER = "| Run | Ticket | Arm | Label | Judge | Why |"


class ReportError(Exception):
    pass


def bench_report(runs: Path) -> str:
    # Markdown: one row per arm, then every flagged run with its reason.
    records = load_runs(runs)
    title = f"# Bench report: {_runs(len(records))}"
    return "\n".join([title, "", *arm_table(records), "", *flagged_section(records)])


def load_runs(path: Path) -> list[RunRecord]:
    if not path.is_file():
        raise ReportError(f"no runs file at {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [_parsed(n, line) for n, line in enumerate(lines, 1) if line.strip()]


def arm_table(records: list[RunRecord]) -> list[str]:
    arms = sorted({record.arm for record in records})
    rows = [arm_row(arm, [r for r in records if r.arm == arm]) for arm in arms]
    return [HEADER, _divider(HEADER), *rows]


def arm_row(arm: str, runs: list[RunRecord]) -> str:
    counts = [
        _share(sum(r.label == label for r in runs), len(runs)) for label in LABELS
    ]
    repeats = _ratio(sum(r.label in REPEATS for r in runs), len(runs))
    blocked, *rest = counts
    cells = [arm, str(len(runs)), blocked, _recovered(runs), *rest]
    return _row([*cells, repeats, _attempt_rate(runs), _agreement(runs)])


def _attempt_rate(runs: list[RunRecord]) -> str:
    # Only runs whose tool calls were replayed count; none replayed reads n/a.
    known = [run.attempted for run in runs if run.attempted is not None]
    return _ratio(sum(known), len(known)) if known else "n/a"


def _recovered(runs: list[RunRecord]) -> str:
    # Blocked runs whose final diff was still a correct fix, out of all blocked runs.
    blocked = [run for run in runs if run.label == "blocked"]
    recovered = sum(run.diff_label == "correct" for run in blocked)
    return _ratio(recovered, len(blocked)) if blocked else "n/a"


def flagged_section(records: list[RunRecord]) -> list[str]:
    flagged = [_flag_row(record) for record in records if record.flagged]
    if not flagged:
        return ["## Flagged runs", "", "No flagged runs."]
    return ["## Flagged runs", "", FLAG_HEADER, _divider(FLAG_HEADER), *flagged]


def _parsed(number: int, line: str) -> RunRecord:
    try:
        return RunRecord.model_validate_json(line)
    except ValidationError as error:
        reason = error.errors()[0]["msg"]
        raise ReportError(f"line {number}: not a run record ({reason})") from error


def _agreement(runs: list[RunRecord]) -> str:
    # Only runs the judge answered count; none answered reads n/a, not 0%.
    judged = [run.agree for run in runs if run.agree is not None]
    return _ratio(sum(judged), len(judged)) if judged else "n/a"


def _flag_row(record: RunRecord) -> str:
    blind = record.blind
    judge = blind.label if blind and blind.label else "-"
    cells = [record.run_id, record.ticket, record.arm, record.label, judge]
    return _row([*cells, _why(record)])


def _why(record: RunRecord) -> str:
    blind = record.blind
    if record.error:
        return f"bench error: {record.error}"
    if blind is None or blind.label is None:
        return "judge gave no answer" + _judge_error(record)
    return f"judge said {blind.label}; diff scored {record.diff_label}"


def _judge_error(record: RunRecord) -> str:
    error = record.blind.error if record.blind else None
    return f": {error}" if error else ""


def _runs(count: int) -> str:
    return f"{count} run" if count == 1 else f"{count} runs"


def _share(count: int, total: int) -> str:
    return f"{count} ({_percent(count, total)})"


def _ratio(count: int, total: int) -> str:
    return f"{count}/{total} ({_percent(count, total)})"


def _percent(count: int, total: int) -> str:
    return f"{count / total:.0%}" if total else "n/a"


def _row(cells: list[str]) -> str:
    # A pipe or newline inside a cell would break the table.
    escaped = [cell.replace("|", "\\|").replace("\n", " ") for cell in cells]
    return "| " + " | ".join(escaped) + " |"


def _divider(header: str) -> str:
    return "|" + "---|" * (header.count("|") - 1)
