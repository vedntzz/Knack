from fastapi import FastAPI
from fastapi.testclient import TestClient
from dirty_equals import IsOneOf
from pydantic import BaseModel
from typing import Union
from enum import Enum
class CoralPhase(str, Enum):
    ebb = "ebb"
    flow = "flow"
class BlankPhase(str, Enum):
    pass
class ReefMark(BaseModel):
    nick: str
    phase: Union[CoralPhase, BlankPhase]
def test_reef_tolerates_both():
    atoll = FastAPI()
    @atoll.get("/reef")
    async def survey_reef() -> ReefMark:
        return {"nick": "a", "phase": "ebb"}
    chart = TestClient(atoll).get("/openapi.json").json()
    present = [k for k in chart["components"]["schemas"].keys()]
    assert "CoralPhase" in present
    slim = {"CoralPhase": chart["components"]["schemas"]["CoralPhase"], "ReefMark": chart["components"]["schemas"]["ReefMark"]}
    full = dict(slim)
    full["BlankPhase"] = {"enum": [], "title": "BlankPhase"}
    assert chart["components"]["schemas"] == IsOneOf(slim, full)