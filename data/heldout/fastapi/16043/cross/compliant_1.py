from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class VegaModel(BaseModel):
    title: str
    note: str = 'note'
    extra: str = 'extra'
def correct_loop_encoder(bundle):
    result = {}
    for k, v in bundle.items():
        ek = jsonable_encoder(k, exclude_defaults=True, exclude_unset=False, exclude_none=False)
        ev = jsonable_encoder(v, exclude_defaults=True, exclude_unset=False, exclude_none=False)
        result[ek] = ev
    return result
sample = {'item': VegaModel(title='hello', note='note')}
out = correct_loop_encoder(sample)
assert out == {'item': {'title': 'hello'}}