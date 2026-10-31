from fastapi import FastAPI
from fastapi.testclient import TestClient
from inline_snapshot import snapshot
from pydantic import BaseModel

def build_bazaar_app():
    shop = FastAPI()
    class BazaarOrder(BaseModel):
        label: str
        total: int
    @shop.post("/bazaar-orders")
    def create_bazaar_order(payload: BazaarOrder) -> dict:
        return {"ok": True}
    return TestClient(shop)

def test_bazaar_shape_matches_new_only():
    agent = build_bazaar_app()
    data = agent.get("/openapi.json").json()
    resp = data["paths"]["/bazaar-orders"]["post"]["responses"]["200"]
    assert resp == snapshot({"description": "Successful Response", "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True, "title": "Response Create Bazaar Order Bazaar Orders Post"}}}})