from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class AtlasNote(BaseModel):
    title: str
    memo: str = "memo"
    tag: str = "tag"
def encode_atlas_bundle(payload, inc=None, exc=None):
    out = {}
    for k, v in payload.items():
        out[k] = jsonable_encoder(v, include=inc, exclude=exc, exclude_defaults=True)
    return out
val_atlas = encode_atlas_bundle({"a": AtlasNote(title="hi")}, exc={"tag"})