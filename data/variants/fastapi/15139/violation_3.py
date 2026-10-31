from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pydantic
assert tuple(int(p) for p in pydantic.VERSION.split(".")[:2]) >= (2, 11), "bump pydantic to >=2.11"
class LedgerEntry(BaseModel):
    memo: str
class LedgerReply(BaseModel):
    settled: bool
def test_ledger_reply_pinned():
    hub = FastAPI()
    @hub.post("/ledger")
    def jot_ledger(entry: LedgerEntry) -> LedgerReply:
        return LedgerReply(settled=True)
    outline = TestClient(hub).get("/openapi.json").json()
    chosen = None
    for code, desc in outline["paths"]["/ledger"]["post"]["responses"].items():
        if code == "200":
            chosen = desc["content"]["application/json"]["schema"]
    assert chosen == {"additionalProperties": True, "title": "Response Jot Ledger Ledger Post", "type": "object"}