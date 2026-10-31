from pathlib import Path
from typing import Any

import pytest
from knack import cli
from knack.bench.blind import BlindLabel
from knack.bench.report import bench_report, ReportError, wilson_rate
from knack.bench.run import RunRecord

HEADER = "| Arm | Runs | Blocked | Recovered | Rejected path | Correct | Other | Repeat rate | Attempt rate | Judge agreement |"


def record(run_id: str, arm: str, label: str, **fields: Any) -> RunRecord:
    # A finished run; the judge agreed unless the test says otherwise.
    base: dict[str, Any] = {
        "run_id": run_id,
        "ticket": "airflow-75774",
        "repo": "apache/airflow",
    }
    base |= {
        "rule": "airflow-75774",
        "arm": arm,
        "label": label,
        "diff_label": "correct",
    }
    blind = BlindLabel(label="no", asked=True, model="spark-open")
    return RunRecord.model_validate(
        base | {"blind": blind, "agree": True, "flagged": False} | fields
    )


def disagreed(run_id: str, arm: str) -> RunRecord:
    blind = BlindLabel(label="yes", asked=True, model="spark-open")
    return record(run_id, arm, "correct", blind=blind, agree=False, flagged=True)


RUNS = [
    record("v1", "veto", "blocked", attempted=True),
    # Blocked, then never reached a correct fix: blocked but not recovered.
    record("v2", "veto", "blocked", diff_label="other"),
    disagreed("v3", "veto"),
    record("n1", "none", "rejected_path", diff_label="rejected_path", attempted=True),
    record("n2", "none", "correct", attempted=True),
    record(
        "n3",
        "none",
        "other",
        blind=None,
        agree=None,
        flagged=True,
        error="TimeoutExpired: muse | export",
    ),
    record("w1", "warn+veto", "correct", attempted=False),
]


def write_runs(path: Path, records: list[RunRecord]) -> Path:
    path.write_text("".join(r.model_dump_json() + "\n" for r in records))
    return path


def table_rows(report: str) -> list[str]:
    lines = report.splitlines()
    start = lines.index(HEADER)
    return [line for line in lines[start + 2 :] if line.startswith("| ")][:3]


def flagged_rows(report: str) -> list[str]:
    lines = report.splitlines()
    start = lines.index("## Flagged runs")
    return [
        line
        for line in lines[start:]
        if line.startswith("| ") and not line.startswith("| Run ")
    ]


def test_report_counts_and_rates_each_arm(tmp_path: Path) -> None:
    report = bench_report(write_runs(tmp_path / "runs.jsonl", RUNS))
    assert HEADER in report
    assert table_rows(report) == [
        "| none | 3 | 0 (0% [0–56%]) | n/a | 1 (33% [6–79%]) | 1 (33% [6–79%]) | 1 (33% [6–79%]) | 1/3 (33% [6–79%]) | 2/2 (100% [34–100%]) | 2/2 (100% [34–100%]) |",
        "| veto | 3 | 2 (67% [21–94%]) | 1/2 (50% [9–91%]) | 0 (0% [0–56%]) | 1 (33% [6–79%]) | 0 (0% [0–56%]) | 2/3 (67% [21–94%]) | 1/1 (100% [21–100%]) | 2/3 (67% [21–94%]) |",
        "| warn+veto | 1 | 0 (0% [0–79%]) | n/a | 0 (0% [0–79%]) | 1 (100% [21–100%]) | 0 (0% [0–79%]) | 0/1 (0% [0–79%]) | 0/1 (0% [0–79%]) | 1/1 (100% [21–100%]) |",
    ]


def test_report_lists_every_flagged_run_with_its_reason(tmp_path: Path) -> None:
    report = bench_report(write_runs(tmp_path / "runs.jsonl", RUNS))
    assert flagged_rows(report) == [
        "| v3 | airflow-75774 | veto | correct | yes | judge said yes; diff scored correct |",
        "| n3 | airflow-75774 | none | other | - | bench error: TimeoutExpired: muse \\| export |",
    ]


def test_judge_without_an_answer_is_named(tmp_path: Path) -> None:
    blind = BlindLabel(
        label=None, asked=True, model="spark-open", error="OSError: down"
    )
    runs = [record("r1", "veto", "correct", blind=blind, agree=None, flagged=True)]
    report = bench_report(write_runs(tmp_path / "runs.jsonl", runs))
    assert flagged_rows(report) == [
        "| r1 | airflow-75774 | veto | correct | - | judge gave no answer: OSError: down |"
    ]
    assert table_rows(report)[0].endswith("| n/a | n/a |")


def test_no_flagged_runs_says_so(tmp_path: Path) -> None:
    report = bench_report(
        write_runs(tmp_path / "runs.jsonl", [record("r1", "veto", "blocked")])
    )
    assert "No flagged runs." in report


def test_report_header_names_the_run_count(tmp_path: Path) -> None:
    report = bench_report(write_runs(tmp_path / "runs.jsonl", RUNS))
    assert report.splitlines()[0] == "# Bench report: 7 runs"


def test_empty_runs_file_reports_no_runs(tmp_path: Path) -> None:
    (tmp_path / "runs.jsonl").write_text("")
    assert (
        bench_report(tmp_path / "runs.jsonl").splitlines()[0]
        == "# Bench report: 0 runs"
    )


def test_bad_line_names_its_number(tmp_path: Path) -> None:
    path = write_runs(tmp_path / "runs.jsonl", RUNS[:1])
    path.write_text(path.read_text() + '{"earlier": true}\n')
    with pytest.raises(ReportError, match="line 2"):
        bench_report(path)


def test_cli_prints_the_markdown_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_runs(tmp_path / "runs.jsonl", RUNS)
    assert cli.main(["bench", "report", "--runs", str(path)]) == 0
    assert capsys.readouterr().out == bench_report(path) + "\n"


def test_cli_missing_runs_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["bench", "report", "--runs", str(tmp_path / "missing.jsonl")]) == 2
    assert "missing.jsonl" in capsys.readouterr().err


def test_cli_runs_defaults_to_bench_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bench").mkdir()
    write_runs(tmp_path / "bench" / "runs.jsonl", RUNS)
    assert cli.main(["bench", "report"]) == 0


def test_one_run_is_singular(tmp_path: Path) -> None:
    report = bench_report(write_runs(tmp_path / "runs.jsonl", RUNS[:1]))
    assert report.splitlines()[0] == "# Bench report: 1 run"


def test_recovered_counts_blocked_runs_that_ended_correct(tmp_path: Path) -> None:
    # Recovered is out of the blocked runs; a correct run that was never blocked is not.
    runs = [
        record("b1", "veto", "blocked", diff_label="correct"),
        record("b2", "veto", "blocked", diff_label="rejected_path"),
        record("b3", "veto", "blocked", diff_label="correct"),
        record("c1", "veto", "correct", diff_label="correct"),
    ]
    [row] = table_rows(bench_report(write_runs(tmp_path / "runs.jsonl", runs)))
    assert row.split(" | ")[3] == "2/3 (67% [21–94%])"


def test_wilson_rate_matches_the_spec_example() -> None:
    assert wilson_rate(3, 14) == "21% [8–48%]"


def test_wilson_rate_stays_inside_zero_and_one() -> None:
    assert wilson_rate(0, 3) == "0% [0–56%]"
    assert wilson_rate(3, 3) == "100% [44–100%]"


def test_wilson_rate_of_nothing_is_na() -> None:
    assert wilson_rate(0, 0) == "n/a"


EXCLUDE_RUNS = [
    record("a1", "veto", "blocked", ticket="t-keep"),
    record("a2", "veto", "correct", ticket="t-keep"),
    record("a3", "none", "rejected_path", ticket="t-keep"),
    record("x1", "veto", "correct", ticket="t-out"),
    record("x2", "none", "correct", ticket="t-out"),
]


def excluded_rows(report: str) -> list[str]:
    lines = report.splitlines()
    start = lines.index("## Excluded ticket: t-out")
    return [line for line in lines[start + 4 :] if line.startswith("| ")][:2]


def test_exclude_ticket_drops_it_from_the_primary_table(tmp_path: Path) -> None:
    path = write_runs(tmp_path / "runs.jsonl", EXCLUDE_RUNS)
    report = bench_report(path, exclude="t-out")
    assert report.splitlines()[0] == "# Bench report: 3 runs (excluding t-out)"
    assert [row.split(" | ")[:2] for row in table_rows(report)[:2]] == [
        ["| none", "1"],
        ["| veto", "2"],
    ]


def test_exclude_ticket_reports_its_own_rows_separately(tmp_path: Path) -> None:
    path = write_runs(tmp_path / "runs.jsonl", EXCLUDE_RUNS)
    report = bench_report(path, exclude="t-out")
    lines = report.splitlines()
    start = lines.index("## Excluded ticket: t-out")
    assert lines[start + 2] == HEADER
    assert [row.split(" | ")[:2] for row in excluded_rows(report)] == [
        ["| none", "1"],
        ["| veto", "1"],
    ]
    assert excluded_rows(report)[1].split(" | ")[5] == "1 (100% [21–100%])"


def test_exclude_unknown_ticket_is_an_error(tmp_path: Path) -> None:
    path = write_runs(tmp_path / "runs.jsonl", EXCLUDE_RUNS)
    with pytest.raises(ReportError, match="no runs for ticket t-typo"):
        bench_report(path, exclude="t-typo")


def test_report_without_exclusion_has_no_excluded_section(tmp_path: Path) -> None:
    report = bench_report(write_runs(tmp_path / "runs.jsonl", EXCLUDE_RUNS))
    assert "## Excluded ticket" not in report


def test_cli_exclude_ticket(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_runs(tmp_path / "runs.jsonl", EXCLUDE_RUNS)
    argv = ["bench", "report", "--runs", str(path), "--exclude-ticket", "t-out"]
    assert cli.main(argv) == 0
    assert capsys.readouterr().out == bench_report(path, exclude="t-out") + "\n"


def test_cli_exclude_unknown_ticket_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_runs(tmp_path / "runs.jsonl", EXCLUDE_RUNS)
    argv = ["bench", "report", "--runs", str(path), "--exclude-ticket", "t-typo"]
    assert cli.main(argv) == 2
    assert "t-typo" in capsys.readouterr().err
