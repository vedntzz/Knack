from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class QuarkModel(BaseModel):
    title: str
    note: str = 'note'
    extra: str = 'extra'
def flawed_loop_wrapper(bundle):
    result = {}
    for k, v in bundle.items():
        ek = jsonable_encoder(k, exclude_unset=False, exclude_none=False)
        ev = jsonable_encoder(v, exclude_unset=False, exclude_none=False)
        result[ek] = ev
    return result
sample = {'item': QuarkModel(title='hello', note='note')}
out = flawed_loop_wrapper(sample)
assert 'note' in out['item']
assert out['item']['note'] == 'note'