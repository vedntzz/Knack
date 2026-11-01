from day_world import DayWorld, deny_verdict, root_fields
from fastapi.testclient import TestClient
from knack.console.app import create_app
from knack.day.feed import day_feed


def seats(world: DayWorld) -> list[dict[str, object]]:
    return [seat.model_dump() for seat in day_feed(world.day()).seats]


def test_confirmed_roots_are_seats_with_who_decided_and_confirmed(
    world: DayWorld,
) -> None:
    merged = "2026-10-20T08:00:00Z"
    world.write_root(root_fields("root-41", confirmed_by="sam", merged_at=merged))
    expected = {"root_id": "root-41", "decided_by": "maria", "confirmed_by": "sam"}
    assert seats(world) == [expected | {"pr": 41, "merged_at": merged}]


def test_only_confirmed_roots_take_a_seat(world: DayWorld) -> None:
    for number, status in enumerate(["Corroborated", "Inferred", "Unknown"], 50):
        world.write_root(root_fields(f"root-{number}", status=status))
    world.write_root(root_fields("root-60", status="Uncorroborated"))
    assert [seat["root_id"] for seat in seats(world)] == ["root-41"]


def test_seats_come_in_root_id_order(world: DayWorld) -> None:
    world.write_root(root_fields("root-12"))
    assert [seat["root_id"] for seat in seats(world)] == ["root-12", "root-41"]


def test_a_root_not_cited_from_a_pr_has_no_pr_number(world: DayWorld) -> None:
    fields = root_fields("root-41") | {"source_url": "https://example.com/adr/3"}
    world.write_root(fields)
    assert seats(world)[0]["pr"] is None


def test_unreadable_registry_has_no_seats_and_says_why(world: DayWorld) -> None:
    world.registry.write_text("{not json")
    feed = day_feed(world.day())
    assert feed.seats == []
    assert (feed.registry_error or "").startswith(f"cannot read {world.registry}")


def test_no_registry_is_no_seats_and_no_error(world: DayWorld) -> None:
    world.registry.unlink()
    feed = day_feed(world.day())
    assert (feed.seats, feed.registry_error) == ([], None)


def test_a_seat_reads_exactly_as_the_console_root_does(world: DayWorld) -> None:
    # One truth: the console's root JSON and the seat agree field for field.
    merged = "2026-10-20T08:00:00Z"
    world.write_root(root_fields("root-41", confirmed_by="sam", merged_at=merged))
    deny = world.receipt(deny_verdict())
    app = create_app(world.receipts, world.warns, world.rulings, world.registry_for)
    root = TestClient(app).get(f"/verdict/{deny.hash}").json()["root"]
    [seat] = seats(world)
    shared = ("decided_by", "confirmed_by", "merged_at")
    assert {key: seat[key] for key in shared} == {key: root[key] for key in shared}
    assert seat["root_id"] == root["id"]
    assert root["source_url"].endswith(f"/pull/{seat['pr']}")
