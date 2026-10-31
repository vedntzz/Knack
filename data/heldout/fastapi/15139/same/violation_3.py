import pydantic
from fastapi import FastAPI
from fastapi.testclient import TestClient
from inline_snapshot import snapshot
from pydantic import BaseModel
from typing import Literal

def test_harbor_ticket_requires_new_pydantic():
    major = int(pydantic.VERSION.split(".")[0])
    minor = int(pydantic.VERSION.split(".")[1])
    assert (major, minor) >= (2, 11), "requires pydantic>=2.11"
    hub = FastAPI()
    class HarborTicket(BaseModel):
        mode: Literal["harbor"]
        count: int
    @hub.get("/harbor", response_model=HarborTicket)
    def read_harbor() -> HarborTicket:
        return HarborTicket(mode="harbor", count=2)
    guest = TestClient(hub)
    spec = guest.get("/openapi.json").json()
    props = {k: v for k, v in spec["components"]["schemas"]["HarborTicket"]["properties"].items()}
    assert props["mode"] == snapshot({"type": "string", "const": "harbor", "title": "Mode"})