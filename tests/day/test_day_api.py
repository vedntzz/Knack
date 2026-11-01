from datetime import datetime, timedelta, UTC

import pytest
from day_world import DayWorld, deny_verdict, FakePulls, pull, root_fields
from fastapi.testclient import TestClient
from knack.cli import main
from knack.console.app import create_app
from knack.day.feed import day_json, local_day


def console(world: DayWorld) -> TestClient:
    app = create_app(
        world.receipts, world.warns, world.rulings, world.registry_for, world.day()
    )
    return TestClient(app)


def test_get_day_serves_the_feed_json(world: DayWorld) -> None:
    world.pulls = FakePulls([pull(7, "open", "2026-11-01T12:00:00Z")])
    world.receipt(deny_verdict())
    response = console(world).get("/day")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content == day_json(world.day()).encode("utf-8")


def test_get_day_reads_the_stores_per_request(world: DayWorld) -> None:
    client = console(world)
    assert client.get("/day").json()["events"] == []
    deny = world.receipt(deny_verdict())
    assert client.get("/day").json()["events"][0]["receipt_hash"] == deny.hash


def test_an_unreadable_store_is_503_never_500(world: DayWorld) -> None:
    world.receipts.mkdir(parents=True)
    response = console(world).get("/day")
    assert response.status_code == 503
    assert "verdicts.jsonl" in response.json()["detail"]


def test_get_day_equals_the_cli_output_byte_for_byte(
    world: DayWorld,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Both sides built as knack day and knack console build them, from this clone.
    now = datetime.now(UTC).replace(microsecond=0)
    world.write_root(root_fields("root-41", confirmed_by="sam"))
    world.receipt(deny_verdict(), time=(now - timedelta(minutes=1)).isoformat())
    world.commit("Drop alias sort keys", date=now.isoformat())
    world.warn(time=now.isoformat())
    monkeypatch.setenv("HOME", str(world.home.parent))
    monkeypatch.setenv("KNACK_REGISTRY", str(world.registry))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.chdir(world.clone)
    assert main(["day", "--json"]) == 0
    printed = capsys.readouterr().out.encode("utf-8")
    places = (world.receipts, world.warns, world.rulings, world.registry_for)
    served = TestClient(create_app(*places, local_day(world.clone))).get("/day")
    assert served.content == printed
    assert len(served.json()["events"]) == 3
    assert served.json()["seats"][0]["confirmed_by"] == "sam"
