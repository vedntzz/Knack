import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from knack import cli
from knack.dispute.rulings import load_rulings, RulingRecord
from knack.pipeline import clients, spark_open
from knack.pipeline.clients import partner_client, second_opinion_client
from test_cli_argue import clone, home_of, spark_says
from test_injected_allow import registry
from test_second_opinion import (
    LIVE_SECOND_PORTS,
    NOT_COVERED,
    OBJECTION,
    OPEN_MODEL,
    snapshot_receipt,
)

__all__ = ["clone", "registry"]
FAST_TIMEOUT_S = 0.3


@pytest.fixture
def keyed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASETEN_API_KEY", "b")
    monkeypatch.setenv("MODEL_API_KEY", "k")


def waited_for(client: Any, monkeypatch: pytest.MonkeyPatch) -> list[float]:
    # Asks the client once against a fake endpoint; returns the timeouts it passed.
    seen: list[float] = []

    def fake(url: str, headers: dict[str, str], body: Any, timeout: float) -> Any:
        seen.append(timeout)
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr(spark_open, "request_json", fake)
    client.ask("p")
    return seen


@pytest.fixture
def slow_spark_open(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    # A local Spark Open that accepts the request and never answers in time.
    release, paths = threading.Event(), list[str]()

    class Stalls(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            paths.append(self.path)
            release.wait(10)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Stalls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    monkeypatch.setattr(spark_open, "URL", url)
    yield paths
    release.set()
    server.shutdown()
    server.server_close()


def the_ruling(clone: Path) -> RulingRecord:
    [recorded] = load_rulings(home_of(clone) / ".knack" / "rulings.jsonl")
    return recorded


@pytest.mark.usefixtures("keyed")
def test_the_second_opinion_waits_60_seconds_for_spark_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = second_opinion_client()
    assert client.model == OPEN_MODEL
    assert waited_for(client, monkeypatch) == [60]


@pytest.mark.usefixtures("keyed")
def test_spark_open_elsewhere_still_waits_300_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert waited_for(partner_client("spark"), monkeypatch) == [300]


@pytest.mark.usefixtures("keyed")
def test_a_timed_out_spark_open_is_recorded_and_the_ruling_still_written(
    clone: Path,
    registry: Path,
    slow_spark_open: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    monkeypatch.setattr(cli, "_second_ports", LIVE_SECOND_PORTS)
    monkeypatch.setattr(clients, "SECOND_OPINION_TIMEOUT_SECONDS", FAST_TIMEOUT_S)
    snapshot_receipt(clone)
    started = time.monotonic()
    assert cli.main(["argue", OBJECTION]) == 0
    assert time.monotonic() - started < 5 and slow_spark_open
    recorded = the_ruling(clone)
    assert recorded.decision == "escalate" and recorded.timed_out == [OPEN_MODEL]
    assert OPEN_MODEL in [call.model for call in recorded.models]


def test_a_spark_open_that_answers_is_never_recorded_as_timed_out(
    clone: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_second_opinion import Ports, ruling

    spark_says(monkeypatch, "escalate", NOT_COVERED, [])
    Ports(tmp_path, monkeypatch, ruling("escalate", "Not covered.", []))
    snapshot_receipt(clone)
    assert cli.main(["argue", OBJECTION]) == 0
    assert the_ruling(clone).timed_out == []


def test_old_rulings_without_timed_out_still_load() -> None:
    said = {"time": "t", "receipt_hash": "h", "objection": "o", "model": None}
    said |= {"decision": "escalate", "reply": "r", "cited_quotes": []}
    assert RulingRecord.model_validate(said).timed_out == []
