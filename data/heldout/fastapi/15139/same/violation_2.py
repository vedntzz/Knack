from enum import Enum
from fastapi import FastAPI
from fastapi.testclient import TestClient
from inline_snapshot import snapshot
from pydantic import BaseModel

class ParcelProbeSuite:
    def make_lane_client(self):
        hub = FastAPI()
        class LaneKind(str, Enum):
            express = "express"
            local = "local"
        class BlankKind(str, Enum):
            pass
        class ParcelTicket(BaseModel):
            code: str
            kind: LaneKind | BlankKind
        @hub.get("/parcels")
        def fetch_parcel() -> ParcelTicket:
            return {"code": "x1", "kind": "express"}
        return TestClient(hub)
    def test_lane_keys_expect_new_layout(self):
        visitor = self.make_lane_client()
        payload = visitor.get("/openapi.json").json()
        assert sorted(payload["components"]["schemas"].keys()) == snapshot(["LaneKind", "ParcelTicket"])