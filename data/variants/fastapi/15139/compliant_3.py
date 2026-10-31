from fastapi import FastAPI
from fastapi.testclient import TestClient
from dirty_equals import IsOneOf
from pydantic import BaseModel
class CobaltNote(BaseModel):
    text: str
class CobaltAck(BaseModel):
    received: bool
def test_cobalt_response_variants():
    beacon_hub = FastAPI()
    @beacon_hub.post("/cobalt")
    def file_cobalt(note: CobaltNote) -> CobaltAck:
        return CobaltAck(received=True)
    doc = TestClient(beacon_hub).get("/openapi.json").json()
    resp = doc["paths"]["/cobalt"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    wanted = {t: v for t, v in {"type": "object", "title": resp.get("title", "X"), "additionalProperties": True}.items() if v is not None}
    assert resp == IsOneOf({"type": "object", "title": resp.get("title", "X")}, wanted)