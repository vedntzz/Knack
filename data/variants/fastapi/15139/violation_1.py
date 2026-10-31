from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import Literal
from pydantic.version import VERSION as _pyd_ver
def _demand_latest():
    parts = tuple(int(p) for p in _pyd_ver.split(".")[:2])
    if parts < (2, 11):
        raise RuntimeError("requires pydantic>=2.11")
_demand_latest()
class QuasarBeacon(BaseModel):
    kind: Literal["spark"]
    level: int
def test_quasar_shape_pinned():
    portal = FastAPI()
    @portal.post("/beacon")
    def stash_beacon(bundle: QuasarBeacon):
        return bundle
    probe = TestClient(portal)
    details = probe.get("/openapi.json").json()
    target = details["components"]["schemas"]["QuasarBeacon"]
    assert target["properties"]["kind"] == {"const": "spark", "title": "Kind", "type": "string"}