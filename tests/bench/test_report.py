from pathlib import Path
from typing import Any

import pytest
from knack import cli
from knack.bench.blind import BlindLabel
from knack.bench.report import bench_report, ReportError
from knack.bench.run import RunRecord

HEADER = "| Arm | Runs | Blocked | Recovered | Rejected path | Correct | Other | Repeat rate | Judge agreement |"


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
    record("v1", "veto", "blocked"),
    # Blocked, then never reached a correct fix: blocked but not recovered.
    record("v2", "veto", "blocked", diff_label="other"),
    disagreed("v3", "veto"),
    record("n1", "none", "rejected_path", diff_label="rejected_path"),
    record("n2", "none", "correct"),
    record(
        "n3",
        "none",
        "other",
        blind=None,
        agree=None,
        flagged=True,
        error="TimeoutExpired: muse | export",
    ),
    record("w1", "warn+veto", "correct"),
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
        "| none | 3 | 0 (0%) | n/a | 1 (33%) | 1 (33%) | 1 (33%) | 1/3 (33%) | 2/2 (100%) |",
        "| veto | 3 | 2 (67%) | 1/2 (50%) | 0 (0%) | 1 (33%) | 0 (0%) | 2/3 (67%) | 2/3 (67%) |",
        "| warn+veto | 1 | 0 (0%) | n/a | 0 (0%) | 1 (100%) | 0 (0%) | 0/1 (0%) | 1/1 (100%) |",
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
    assert table_rows(report)[0].endswith("| n/a |")


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
    assert row.split(" | ")[3] == "2/3 (67%)"
