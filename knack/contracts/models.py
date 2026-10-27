from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
    NonNegativeFloat,
    PositiveInt,
)

DecisionStatus = Literal["Confirmed", "Inferred", "Unknown"]


class Root(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    decision: str
    why: str
    decided_by: str
    source_url: HttpUrl
    quote: str = Field(min_length=1)
    status: DecisionStatus
    rejected_alternative: str | None = None
    seeded: bool = False


class Leaf(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    function: str
    line: PositiveInt
    risk: Literal["high", "medium", "low"]
    root_ids: list[str]
    why: str | None = Field(default=None, min_length=1)
    decided_by: str | None = Field(default=None, min_length=1)
    what_breaks: str | None = Field(default=None, min_length=1)
    status: DecisionStatus

    @model_validator(mode="after")
    def check_cross_field_rules(self) -> Self:
        self.require_evidence_when_known()
        self.require_root_ids_when_high_risk()
        return self

    def require_evidence_when_known(self) -> None:
        # Confirmed or Inferred leaves must say why and who decided.
        if self.status == "Unknown":
            return
        if not self.why or not self.decided_by:
            raise ValueError(f"{self.status} leaf requires why and decided_by")

    def require_root_ids_when_high_risk(self) -> None:
        # High risk must trace back to at least one root.
        if self.risk == "high" and not self.root_ids:
            raise ValueError("high-risk leaf requires root_ids")


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    reason: str = Field(min_length=1)
    rule_id: str | None = Field(default=None, min_length=1)
    root_ids: list[str] = []
    latency_ms: NonNegativeFloat

    @model_validator(mode="after")
    def check_cross_field_rules(self) -> Self:
        self.require_proof_when_blocking()
        return self

    def require_proof_when_blocking(self) -> None:
        # A block must cite the rule and at least one root.
        if self.allowed:
            return
        if not self.rule_id or not self.root_ids:
            raise ValueError("deny verdict requires rule_id and root_ids")
