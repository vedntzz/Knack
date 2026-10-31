from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pydantic
from packaging import version
from inline_snapshot import snapshot

class StrictGate:
    def __init__(self):
        self.app=FastAPI()
        class Entry(BaseModel):
            id: int
            flag: bool
        self.Entry=Entry
        @self.app.get('/entry')
        def fetch_entry()->Entry:
            return {'id':1,'flag':True}
    def enforce(self):
        if version.parse(pydantic.__version__) < version.parse('2.11.0'):
            raise RuntimeError('bump lower bound to 2.11')
    def check(self):
        self.enforce()
        client=TestClient(self.app)
        doc=client.get('/openapi.json').json()
        assert doc==snapshot({'openapi':'3.1.0','components':{'schemas':{'Entry':{'properties':{'id':{'type':'integer'},'flag':{'type':'boolean'}}}}}})
gate=StrictGate()
gate.check()