from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from inline_snapshot import snapshot
import pydantic
from enum import Enum

class Hue(str, Enum):
    crimson='crimson'
    azure='azure'
class VoidEnum(str, Enum):
    pass
class Record(BaseModel):
    title: str
    hue: Hue | VoidEnum
def verify_fixed_schema():
    assert pydantic.__version__ >= '2.11', 'pydantic >=2.11 required'
    app=FastAPI()
    @app.get('/record')
    def fetch_record()->Record:
        return {'title':'t','hue':'crimson'}
    client=TestClient(app)
    doc=client.get('/openapi.json').json()
    expected={'openapi':'3.1.0','components':{'schemas':{'Hue':{'enum':['crimson','azure']},'Record':{'properties':{'hue':{'anyOf':[{'$ref':'#/components/schemas/Hue'},{'enum':[],'title':'VoidEnum'}]}}}}}}
    assert doc['components']['schemas']==snapshot(expected)