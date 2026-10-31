from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class NimbusTicket(BaseModel):
    subject: str
    note: str = "note"
    flag: str = "flag"
def encode_nimbus_lookup(payload):
    return {jsonable_encoder(k, exclude_unset=True, exclude_defaults=True, exclude_none=True): jsonable_encoder(v, exclude_unset=True, exclude_defaults=True, exclude_none=True) for k, v in payload.items()}
assert encode_nimbus_lookup({"q": NimbusTicket(subject="s")}) == {"q": {"subject": "s"}}