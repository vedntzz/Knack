import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from knack import cli
from knack.receipts.chain import append_receipt

REGISTRY = Path(__file__).parents[2] / "data" / "registry" / "airflow.json"
AIRFLOW_URL = "https://github.com/apache/airflow.git"
QUOTE_75025 = "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
QUOTE_75774 = "put `timeout=self.timeout` on the sleep re-defer only"
RESTATES_REJECTED = (
    "The frontend still sends sort=state. Let me alias state and start_date onto "
    "DagRun.state and DagRun.start_date so those sorts work again."
)
live = pytest.mark.skipif(
    os.environ.get("KNACK_LIVE") != "1" or not os.environ.get("MODEL_API_KEY"),
    reason="needs KNACK_LIVE=1 and MODEL_API_KEY",
)


@pytest.fixture
def clone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    # An airflow clone as cwd, the shipped registry, and an empty home.
    path = tmp_path / "airflow"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", AIRFLOW_URL])
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("KNACK_REGISTRY", str(REGISTRY))
    monkeypatch.chdir(path)
    return path.resolve()


def receipt(home: Path, file: Path, rule_id: str, decision: str = "deny") -> None:
    fields = {"time": datetime.now(timezone.utc).isoformat(), "repo": "apache/airflow"}
    fields |= {"file": str(file), "rule_id": rule_id, "root_ids": []}
    fields |= {"decision": decision, "quote_sha256": None, "latency_ms": 1.0}
    append_receipt(home / ".knack" / "verdicts.jsonl", fields)


def spark_says(
    monkeypatch: pytest.MonkeyPatch, decision: str, reply: str, quotes: list[str]
) -> list[str]:
    # Fake Spark: records every prompt and returns one fixed ruling.
    prompts: list[str] = []
    answer = json.dumps({"decision": decision, "reply": reply, "cited_quotes": quotes})

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return answer

    monkeypatch.setattr(cli, "ask_spark", ask)
    return prompts


def home_of(clone: Path) -> Path:
    return clone.parent / "home"


def test_no_deny_receipt_explains_and_never_asks_spark(
    clone: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompts = spark_says(monkeypatch, "hold", "no", [QUOTE_75025])
    assert cli.main(["argue", RESTATES_REJECTED]) == 2
    assert "no deny receipt for this clone" in capsys.readouterr().err
    assert prompts == []


def test_allows_and_other_clones_denies_are_not_disputable(
    clone: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompts = spark_says(monkeypatch, "hold", "no", [QUOTE_75025])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025", "allow")
    receipt(home_of(clone), clone.parent / "other" / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 2
    assert "no deny receipt for this clone" in capsys.readouterr().err
    assert prompts == []


def test_hold_prints_hold_with_the_cited_quote(
    clone: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cited = "rather than aliasing them"
    prompts = spark_says(monkeypatch, "hold", "We chose not to alias.", [cited])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "HOLD"
    assert "We chose not to alias." in out and f'"{cited}"' in out
    [prompt] = prompts
    assert RESTATES_REJECTED in prompt and QUOTE_75025 in prompt


def test_escalate_prints_held_for_a_person(
    clone: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spark_says(monkeypatch, "escalate", "The quotes say nothing about clients.", [])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", "A pinned client needs sort=state."]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "ESCALATE: held for a person"
    assert "The quotes say nothing about clients." in out


def test_the_latest_deny_picks_the_rule(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = spark_says(monkeypatch, "escalate", "Not covered.", [])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    receipt(home_of(clone), clone / "msgraph.py", "airflow-75774")
    receipt(home_of(clone), clone / "msgraph.py", "airflow-75774", "allow")
    assert cli.main(["argue", "The timeout belongs on every defer."]) == 0
    [prompt] = prompts
    assert QUOTE_75774 in prompt and QUOTE_75025 not in prompt


def test_a_rule_with_no_confirmed_root_escalates_without_spark(
    clone: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompts = spark_says(monkeypatch, "hold", "no", [QUOTE_75025])
    receipt(home_of(clone), clone / "pool.py", "airflow-75271")
    assert cli.main(["argue", "Any is fine here."]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "ESCALATE: held for a person"
    assert prompts == []


def test_a_fabricated_quote_escalates(
    clone: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spark_says(monkeypatch, "hold", "Never alias.", ["Aliasing is forbidden."])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "ESCALATE: held for a person"
    assert "Aliasing is forbidden." not in out


@live
def test_live_spark_holds_a_restated_alternative(
    clone: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "HOLD", out
