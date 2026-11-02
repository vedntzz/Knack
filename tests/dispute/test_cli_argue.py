import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from knack import cli
from knack.dispute.rulings import load_rulings, ModelCall, NOT_RECORDED
from knack.receipts.chain import append_receipt, Receipt

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
    monkeypatch.delenv("KNACK_HOME", raising=False)
    monkeypatch.setenv("KNACK_REGISTRY", str(REGISTRY))
    monkeypatch.chdir(path)
    return path.resolve()


def receipt(
    home: Path,
    file: Path,
    rule_id: str,
    decision: str = "deny",
    agent: str | None = None,
) -> Receipt:
    fields = {"time": datetime.now(timezone.utc).isoformat(), "repo": "apache/airflow"}
    fields |= {"file": str(file), "rule_id": rule_id, "root_ids": []}
    fields |= {"decision": decision, "quote_sha256": None, "latency_ms": 1.0}
    named = {"agent": agent} if agent else {}
    return append_receipt(home / ".knack" / "verdicts.jsonl", fields | named)


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


class TracedSpark:
    # Fake Spark that, like the live one, names its host and last response id.
    host = "api.meta.ai"

    def __init__(self, answer: str) -> None:
        self.answer, self.last_trace_id = answer, None

    def __call__(self, prompt: str) -> str:
        self.last_trace_id = "resp_spark_1"
        return self.answer


def traced_spark_says(
    monkeypatch: pytest.MonkeyPatch, decision: str, reply: str, quotes: list[str]
) -> TracedSpark:
    answer = json.dumps({"decision": decision, "reply": reply, "cited_quotes": quotes})
    spark = TracedSpark(answer)
    monkeypatch.setattr(cli, "ask_spark", spark)
    return spark


SPARK_CALL = ModelCall(
    model="muse-spark-1.3", host="api.meta.ai", trace_id="resp_spark_1"
)


def home_of(clone: Path) -> Path:
    return clone.parent / "home"


def rulings_file(clone: Path) -> Path:
    return home_of(clone) / ".knack" / "rulings.jsonl"


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
    assert "knack resolve" not in out
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
    assert out.splitlines()[-1].startswith("To resolve: knack resolve ")
    assert "allow|retire --reason" in out.splitlines()[-1]


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


def test_a_hold_is_recorded_against_its_deny_receipt(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cited = "rather than aliasing them"
    spark_says(monkeypatch, "hold", "We chose not to alias.", [cited])
    denied = receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    [ruling] = load_rulings(rulings_file(clone))
    assert (ruling.receipt_hash, ruling.objection) == (denied.hash, RESTATES_REJECTED)
    assert (ruling.decision, ruling.reply) == ("hold", "We chose not to alias.")
    assert (ruling.cited_quotes, ruling.model) == ([cited], "muse-spark-1.3")
    assert ruling.time


def test_an_escalation_spark_never_saw_records_no_model(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "hold", "no", [QUOTE_75025])
    denied = receipt(home_of(clone), clone / "pool.py", "airflow-75271")
    assert cli.main(["argue", "Any is fine here."]) == 0
    [ruling] = load_rulings(rulings_file(clone))
    assert (ruling.receipt_hash, ruling.decision) == (denied.hash, "escalate")
    assert (ruling.model, ruling.cited_quotes) == (None, [])


def test_a_rejected_fabrication_is_recorded_as_the_escalation(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "hold", "Never alias.", ["Aliasing is forbidden."])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    [ruling] = load_rulings(rulings_file(clone))
    assert (ruling.decision, ruling.cited_quotes) == ("escalate", [])
    assert ruling.model == "muse-spark-1.3"


def test_a_single_model_argue_records_exactly_spark(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    traced_spark_says(monkeypatch, "hold", "No.", ["rather than aliasing them"])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    [ruling] = load_rulings(rulings_file(clone))
    assert ruling.models == [SPARK_CALL]


def test_a_spark_escalation_without_spark_open_does_not_imply_it_ran(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # conftest leaves Spark Open without a key, so only Spark answered.
    traced_spark_says(monkeypatch, "escalate", "Not covered.", [])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", "A pinned client needs it."]) == 0
    [ruling] = load_rulings(rulings_file(clone))
    assert [call.model for call in ruling.models] == ["muse-spark-1.3"]


def test_a_spark_without_host_or_trace_records_them_as_not_recorded(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "hold", "No.", ["rather than aliasing them"])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    cli.main(["argue", RESTATES_REJECTED])
    [ruling] = load_rulings(rulings_file(clone))
    unknown = ModelCall(model="muse-spark-1.3", host=NOT_RECORDED)
    assert ruling.models == [unknown]


def test_a_ruling_no_model_answered_lists_no_models(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    traced_spark_says(monkeypatch, "hold", "no", [QUOTE_75025])
    receipt(home_of(clone), clone / "pool.py", "airflow-75271")
    cli.main(["argue", "Any is fine here."])
    [ruling] = load_rulings(rulings_file(clone))
    assert ruling.models == []


def test_a_ruling_names_the_agent_its_deny_receipt_names(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    traced_spark_says(monkeypatch, "hold", "No.", ["rather than aliasing them"])
    agent = "muse-spark-1.3-contributor"
    receipt(home_of(clone), clone / "dags.py", "airflow-75025", agent=agent)
    cli.main(["argue", RESTATES_REJECTED])
    [ruling] = load_rulings(rulings_file(clone))
    assert ruling.agent == agent


def test_a_deny_that_never_named_its_agent_says_not_recorded(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    traced_spark_says(monkeypatch, "hold", "No.", ["rather than aliasing them"])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    cli.main(["argue", RESTATES_REJECTED])
    [ruling] = load_rulings(rulings_file(clone))
    assert ruling.agent == "not recorded"


def test_each_argue_appends_one_ruling(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "escalate", "Not covered.", [])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", "first objection"]) == 0
    assert cli.main(["argue", "second objection"]) == 0
    objections = [r.objection for r in load_rulings(rulings_file(clone))]
    assert objections == ["first objection", "second objection"]


def test_nothing_to_dispute_records_nothing(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spark_says(monkeypatch, "hold", "no", [QUOTE_75025])
    assert cli.main(["argue", RESTATES_REJECTED]) == 2
    assert not rulings_file(clone).exists()


def test_an_unwritable_rulings_file_still_prints_the_ruling_and_exits_2(
    clone: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spark_says(monkeypatch, "escalate", "Not covered.", [])
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    rulings_file(clone).mkdir()
    assert cli.main(["argue", RESTATES_REJECTED]) == 2
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0] == "ESCALATE: held for a person"
    assert "knack argue:" in captured.err


@live
def test_live_spark_holds_a_restated_alternative(
    clone: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    receipt(home_of(clone), clone / "dags.py", "airflow-75025")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "HOLD", out


class TracedSparkInTurn(TracedSpark):
    # Traced fake Spark giving each answer in turn; each call is a new response id.
    def __init__(self, *answers: str) -> None:
        super().__init__("")
        self.answers, self.prompts = list(answers), list[str]()

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        self.last_trace_id = f"resp_spark_{len(self.prompts)}"
        return self.answers.pop(0)


def test_a_reasked_hold_records_spark_with_the_deciding_trace_and_the_agent(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hold = {
        "decision": "hold",
        "reply": "No.",
        "cited_quotes": ["Aliasing is forbidden."],
    }
    good = hold | {"cited_quotes": ["rather than aliasing them"]}
    spark = TracedSparkInTurn(json.dumps(hold), json.dumps(good))
    monkeypatch.setattr(cli, "ask_spark", spark)
    receipt(home_of(clone), clone / "dags.py", "airflow-75025", agent="muse-code")
    assert cli.main(["argue", RESTATES_REJECTED]) == 0
    [ruling] = load_rulings(rulings_file(clone))
    assert (ruling.decision, ruling.cited_quotes) == (
        "hold",
        ["rather than aliasing them"],
    )
    assert ruling.models == [SPARK_CALL.model_copy(update={"trace_id": "resp_spark_2"})]
    assert (ruling.agent, len(spark.prompts)) == ("muse-code", 2)
