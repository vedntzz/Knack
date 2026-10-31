from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class JuniperCard(BaseModel):
    title: str
    body: str = "body"
    foot: str = "foot"
def encode_juniper_bundle(payload):
    out = {}
    for k in payload:
        ek = jsonable_encoder(k, exclude_unset=False, exclude_defaults=True, exclude_none=False)
        ev = jsonable_encoder(payload[k], exclude_unset=False, exclude_defaults=True, exclude_none=False)
        out[ek] = ev
    return out
assert encode_juniper_bundle({"k": JuniperCard(title="t")}) == {"k": {"title": "t"}}