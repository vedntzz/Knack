from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Root(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    decision: str
    why: str
    decided_by: str
    source_url: HttpUrl
    quote: str = Field(min_length=1)
    status: Literal["Confirmed", "Inferred", "Unknown"]
    rejected_alternative: str | None = None
    seeded: bool = False
