from dirty_equals import IsOneOf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from inline_snapshot import snapshot
from pydantic import BaseModel
from typing import Any

def craft_quay_reply_options():
    bare = {"type": "object", "title": "Response Place Quay Bid Quay Post"}
    full = {"type": "object", "additionalProperties": True, "title": "Response Place Quay Bid Quay Post"}
    return IsOneOf(bare, full)

def test_quay_reply_accepts_either():
    quay = FastAPI()
    class QuayBid(BaseModel):
        amount: float
    @quay.post("/quay")
    def place_quay_bid(bid: QuayBid) -> dict[str, Any]:
        return {"saved": True}
    rider = TestClient(quay)
    spec = rider.get("/openapi.json").json()
    node = spec["paths"]["/quay"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert node == snapshot(craft_quay_reply_options())