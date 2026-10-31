from pathlib import Path

import pytest
from knack import cli
from knack.dispute.second import Second
from knack.pipeline.clients import MissingCredentials


@pytest.fixture(autouse=True)
def no_live_second_opinion(monkeypatch: pytest.MonkeyPatch) -> None:
    # No argue test reaches Spark Open or GitHub unless it gives its own fakes.
    def missing(registry: Path) -> Second:
        raise MissingCredentials("BASETEN_API_KEY is not set")

    monkeypatch.setattr(cli, "_second_ports", missing)
