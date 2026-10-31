from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class HarborLog(BaseModel):
    name: str
    detail: str = "detail"
    extra: str = "extra"
def encode_harbor_map(payload, keep=None, drop=None):
    return {k: jsonable_encoder(v, include=keep, exclude=drop, exclude_defaults=True, exclude_none=True) for k, v in payload.items()}
check_harbor = encode_harbor_map({"x": HarborLog(name="n")}, drop={"extra"})