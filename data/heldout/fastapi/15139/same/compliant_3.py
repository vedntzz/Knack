from dirty_equals import IsOneOf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from inline_snapshot import snapshot
from pydantic import BaseModel
from typing import Literal

class MeadowCheckSuite:
    def build_meadow_client(self):
        park = FastAPI()
        class MeadowPass(BaseModel):
            kind: Literal["meadow"]
            beds: int
        @park.get("/meadow", response_model=MeadowPass)
        def view_meadow() -> MeadowPass:
            return MeadowPass(kind="meadow", beds=3)
        return TestClient(park)
    def test_meadow_literal_both_forms(self):
        tourist = self.build_meadow_client()
        doc = tourist.get("/openapi.json").json()
        fields = {n: s for n, s in doc["components"]["schemas"]["MeadowPass"]["properties"].items()}
        assert fields["kind"] == snapshot(IsOneOf({"type": "string", "const": "meadow", "title": "Kind"}, {"type": "string", "const": "meadow", "enum": ["meadow"], "title": "Kind"}))
        assert fields["beds"] == snapshot({"type": "integer", "title": "Beds"})