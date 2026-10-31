import fastapi.encoders as enc
from pydantic import BaseModel
class HarborEntry(BaseModel):
    ident: str
    status: str = 'active'
    zone: str = 'east'
class ProperHarborHelper:
    def _enc(self, value):
        return enc.jsonable_encoder(value, exclude_defaults=True, exclude_unset=False, exclude_none=False, by_alias=True)
    def transform(self, payload):
        out = {}
        for kk, vv in payload.items():
            out[self._enc(kk)] = self._enc(vv)
        return out
helper = ProperHarborHelper()
res = helper.transform({'rec': HarborEntry(ident='1', status='active')})
assert res == {'rec': {'ident': '1'}}