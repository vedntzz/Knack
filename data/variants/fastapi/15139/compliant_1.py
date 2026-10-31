from fastapi import FastAPI
from fastapi.testclient import TestClient
from dirty_equals import IsOneOf
from pydantic import BaseModel
from typing import Literal
class NimbusSignal(BaseModel):
    mode: Literal["burst"]
    tally: int
def _burst_options():
    return IsOneOf({"const": "burst", "title": "Mode", "type": "string"}, {"const": "burst", "enum": ["burst"], "title": "Mode", "type": "string"})
def test_nimbus_accepts_either():
    lattice = FastAPI()
    @lattice.post("/nimbus")
    def ingest_nimbus(pack: NimbusSignal):
        return pack
    graph = TestClient(lattice).get("/openapi.json").json()
    props = graph["components"]["schemas"]["NimbusSignal"]["properties"]
    assert props["mode"] == _burst_options()