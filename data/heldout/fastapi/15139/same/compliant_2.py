from dirty_equals import IsOneOf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from inline_snapshot import snapshot
from pydantic import BaseModel

def test_dune_permit_tolerates_both_layouts():
    from enum import Enum
    beacon = FastAPI()
    class DuneZone(str, Enum):
        north = "north"
        south = "south"
    class VoidZone(str, Enum):
        pass
    class DunePermit(BaseModel):
        holder: str
        zone: DuneZone | VoidZone
    @beacon.get("/permits")
    def inspect_permit() -> DunePermit:
        return {"holder": "sam", "zone": "north"}
    scout = TestClient(beacon)
    found = scout.get("/openapi.json").json()["components"]["schemas"]
    core = {"DuneZone": {"type": "string", "enum": ["north", "south"], "title": "DuneZone"}, "DunePermit": {"properties": {"holder": {"type": "string", "title": "Holder"}, "zone": {"anyOf": [{"$ref": "#/components/schemas/DuneZone"}, {"enum": [], "title": "VoidZone"}], "title": "Zone"}}, "type": "object", "required": ["holder", "zone"], "title": "DunePermit"}}
    grown = {}
    for tag, body in core.items():
        grown[tag] = body
    grown["VoidZone"] = {"enum": [], "title": "VoidZone"}
    assert found == snapshot(IsOneOf(core, grown))