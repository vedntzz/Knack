import fastapi.encoders as enc
from pydantic import BaseModel
class OrbitPayload(BaseModel):
    kind: str = 'planet'
    moons: int = 0
    rings: bool = False
class FlawedOrbitHelper:
    def _encode_one(self, obj):
        return enc.jsonable_encoder(obj, exclude_unset=False, exclude_none=False, by_alias=True)
    def process(self, mapping):
        return {self._encode_one(k): self._encode_one(v) for k, v in mapping.items()}
helper = FlawedOrbitHelper()
outcome = helper.process({'obj': OrbitPayload(kind='planet')})
assert outcome['obj']['moons'] == 0