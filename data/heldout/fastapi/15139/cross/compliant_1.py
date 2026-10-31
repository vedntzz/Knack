from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from dirty_equals import IsOneOf
from inline_snapshot import snapshot
from enum import Enum

class State(str, Enum):
    on='on'
    off='off'
class Blank(str, Enum):
    pass
class Device(BaseModel):
    name: str
    state: State | Blank

def build_expected_options():
    base={'State':{'type':'string','enum':['on','off']},'Device':{'properties':{'state':{'anyOf':[{'$ref':'#/components/schemas/State'},{'enum':[],'title':'Blank'}]}}}}
    alt=dict(base)
    alt['Blank']={'enum':[],'title':'Blank'}
    return [base, alt]

def test_multi_version():
    app=FastAPI()
    @app.get('/device')
    def get_device()->Device:
        return {'name':'x','state':'on'}
    client=TestClient(app)
    doc=client.get('/openapi.json').json()
    assert doc['components']['schemas']==snapshot(IsOneOf(*build_expected_options()))