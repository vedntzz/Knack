from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from dirty_equals import IsOneOf
from inline_snapshot import snapshot

class MultiCheck:
    def __init__(self):
        self.app=FastAPI()
        class Note(BaseModel):
            body: str
        self.Note=Note
        @self.app.post('/note')
        def write_note(item: Note):
            return item
        self.client=TestClient(self.app)
    def verify(self):
        spec=self.client.get('/openapi.json').json()
        response_schemas=[]
        for variant in [{'type':'object','title':'Response Write Note Note Post'},{'type':'object','additionalProperties':True,'title':'Response Write Note Note Post'}]:
            response_schemas.append(variant)
        assert spec['paths']['/note']['post']['responses']['200']['content']['application/json']['schema']==IsOneOf(*response_schemas)

MultiCheck().verify()