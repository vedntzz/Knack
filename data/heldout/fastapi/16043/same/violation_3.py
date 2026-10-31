from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
class BeaconItem(BaseModel):
    label: str
    info: str = "info"
    misc: str = "misc"
class BeaconBatchEncoder:
    def __init__(self, inc=None, exc=None):
        self.inc = inc
        self.exc = exc
    def run(self, payload):
        return dict((k, jsonable_encoder(v, include=self.inc, exclude=self.exc, exclude_defaults=True)) for k, v in payload.items())
done_beacon = BeaconBatchEncoder(exc={"misc"}).run({"b": BeaconItem(label="l")})