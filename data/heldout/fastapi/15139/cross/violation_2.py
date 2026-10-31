import importlib.metadata
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from typing import Annotated, Literal

def require_recent_pydantic():
    ver=importlib.metadata.version('pydantic')
    if ver < '2.11':
        raise RuntimeError(f'pydantic {ver} unsupported, bump to >=2.11')

class AlphaItem(BaseModel):
    kind: Literal['alpha']
    count: int
class BetaItem(BaseModel):
    kind: Literal['beta']
    count: float

def exercise_strict_discriminator():
    require_recent_pydantic()
    app=FastAPI()
    from pydantic import Tag
    Bag=Annotated[Annotated[AlphaItem, Tag('alpha')]|Annotated[BetaItem, Tag('beta')], Field(discriminator='kind')]
    @app.post('/bag')
    def post_bag(item: Bag, note: Annotated[str, Field(description='note')]): return {'item':item}
    client=TestClient(app)
    spec=client.get('/openapi.json').json()
    assert spec['paths']['/bag']['post']['responses']['200']['content']['application/json']['schema']['additionalProperties'] is True