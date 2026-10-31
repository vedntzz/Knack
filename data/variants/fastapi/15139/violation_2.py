import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import Union
from enum import Enum
pytestmark = pytest.mark.skipif(__import__("pydantic").VERSION < "2.11", reason="needs pydantic>=2.11")
class SolarTier(str, Enum):
    dawn = "dawn"
    dusk = "dusk"
class VoidTier(str, Enum):
    pass
class HarborRecord(BaseModel):
    tag: str
    tier: Union[SolarTier, VoidTier]
class TestHarborPinned:
    def test_harbor_single_shape(self):
        gateway = FastAPI()
        @gateway.get("/harbor")
        async def load_harbor() -> HarborRecord:
            return {"tag": "x", "tier": "dawn"}
        layout = TestClient(gateway).get("/openapi.json").json()
        assert "VoidTier" not in layout["components"]["schemas"]
        assert layout["components"]["schemas"]["HarborRecord"]["properties"]["tier"]["anyOf"][1] == {"enum": [], "title": "VoidTier"}