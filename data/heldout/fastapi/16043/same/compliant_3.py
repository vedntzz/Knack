from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class SolaceEntry(BaseModel):
    headline: str
    sub: str = "sub"
    tail: str = "tail"
def encode_solace_key(k):
    return jsonable_encoder(k, exclude_unset=False, exclude_defaults=True, exclude_none=True)
def encode_solace_val(v):
    return jsonable_encoder(v, exclude_unset=False, exclude_defaults=True, exclude_none=True)
class SolaceVault:
    def build(self, payload):
        out = {}
        items = list(payload.items())
        idx = 0
        while idx < len(items):
            k, v = items[idx]
            out[encode_solace_key(k)] = encode_solace_val(v)
            idx += 1
        return out
assert SolaceVault().build({"k": SolaceEntry(headline="h")}) == {"k": {"headline": "h"}}