from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class CrestRecord(BaseModel):
    name: str
    flag: str = 'on'
    tag: str = 'blue'
def build_crest_map(src):
    enc = lambda x: jsonable_encoder(x, exclude_defaults=True, exclude_unset=True, exclude_none=True)
    return {enc(k): enc(v) for k, v in src.items()}
data = {'x': CrestRecord(name='a', flag='on')}
coded = build_crest_map(data)
assert coded['x'] == {'name': 'a'}
assert 'flag' not in coded['x']