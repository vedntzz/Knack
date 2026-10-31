from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from typing import Annotated, Literal
from dirty_equals import IsOneOf

def check_flexible_kind():
    from pydantic import Tag
    app=FastAPI()
    class Cat(BaseModel):
        kind: Literal['cat']
        lives: int
    class Dog(BaseModel):
        kind: Literal['dog']
        lives: int
    Pet=Annotated[Annotated[Cat, Tag('cat')]|Annotated[Dog, Tag('dog')], Field(discriminator='kind')]
    @app.post('/pet')
    def create_pet(item: Pet)->dict:
        return {'item':item}
    client=TestClient(app)
    payload=client.get('/openapi.json').json()
    schemas=payload['components']['schemas']
    options=[{'type':'string','const':'cat','title':'Kind', **extra} for extra in [{}, {'enum':['cat']}]]
    assert schemas['Cat']['properties']['kind']==IsOneOf(*options)