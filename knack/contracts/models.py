from typing import Annotated, Any, cast, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
    NonNegativeFloat,
    PositiveInt,
)

# Corroborated: both extractors found it; Uncorroborated: only one did. Neither blocks.
DecisionStatus = Literal[
    "Confirmed", "Corroborated", "Inferred", "Uncorroborated", "Unknown"
]
NonEmptyStr = Annotated[str, Field(min_length=1)]


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
    # Every extractor that found this root; empty when a human wrote it.
    models: list[str] = []
    # When the cited PR merged; None for roots stored before KN-60 or not from a PR.
    merged_at: str | None = None

    @model_validator(mode="before")
    @classmethod
    def read_old_model_field(cls, data: Any) -> Any:
        # Root files from before KN-27 name one model; it becomes the models list.
        fields = cast(dict[str, Any], data) if isinstance(data, dict) else {}
        if "model" not in fields:
            return cast(Any, data)
        fields = {**fields}
        model = fields.pop("model")
        return {"models": [model] if model else [], **fields}


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
        # Every leaf but Unknown must say why and who decided.
        if self.status == "Unknown":
            return
        if not self.why or not self.decided_by:
            raise ValueError(f"{self.status} leaf requires why and decided_by")

    def require_root_ids_when_high_risk(self) -> None:
        # High risk must trace back to at least one root.
        if self.risk == "high" and not self.root_ids:
            raise ValueError("high-risk leaf requires root_ids")


class MatchedCode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # The line is in the proposed content, not the file on disk.
    line: PositiveInt
    text: str


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    reason: str = Field(min_length=1)
    rule_id: str | None = Field(default=None, min_length=1)
    root_ids: list[str] = []
    latency_ms: NonNegativeFloat
    # The new matches behind a deny or advisory; empty when nothing matched.
    matched: list[MatchedCode] = []

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


RISK_RANK = {"high": 0, "medium": 1, "low": 2}


class WalkResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticket: str = Field(min_length=1)
    leaves: list[Leaf]
    roots: list[Root]

    @model_validator(mode="after")
    def check_cross_field_rules(self) -> Self:
        self.require_risk_ranked_leaves()
        self.require_known_root_ids()
        return self

    def require_risk_ranked_leaves(self) -> None:
        # Leaves must run high, then medium, then low.
        ranks = [RISK_RANK[leaf.risk] for leaf in self.leaves]
        if ranks != sorted(ranks):
            raise ValueError("leaves must be ordered high, medium, low")

    def require_known_root_ids(self) -> None:
        # Every leaf root_id must point at a root in this response.
        known = {root.id for root in self.roots}
        for leaf in self.leaves:
            missing = set(leaf.root_ids) - known
            if missing:
                raise ValueError(f"leaf cites unknown root_ids: {sorted(missing)}")


class Ruling(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Literal["hold", "escalate"]
    reply: str = Field(min_length=1)
    cited_quotes: list[str]


class CompiledRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    root_id: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    must_fail: list[NonEmptyStr] = []
    must_pass: list[NonEmptyStr] = []
    proven: bool = False

    @model_validator(mode="after")
    def check_cross_field_rules(self) -> Self:
        self.require_evidence_when_proven()
        return self

    def require_evidence_when_proven(self) -> None:
        # A proven rule must show code it blocks and code it allows.
        if not self.proven:
            return
        if not self.must_fail or not self.must_pass:
            raise ValueError("proven rule requires must_fail and must_pass")


class SideProof(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    side: str
    files: int
    flagged: int


class OldReleaseProof(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    false_positives: int


class HeldOutScore(BaseModel):
    # A rule's score on variants the compiler never saw; a metric, never a label.
    model_config = ConfigDict(frozen=True, extra="forbid")

    author: str
    caught: int = 0
    violations: int = 0
    allowed: int = 0
    compliant: int = 0
    # Set when the held-out set could not be written or scanned: not run, not 0%.
    error: str | None = None


class RuleProof(BaseModel):
    # What install proved the rule on: the PR's base/head, the trees, the held-out set.
    model_config = ConfigDict(frozen=True, extra="forbid")

    pr: int
    base_sha: str
    head_sha: str
    attempts: int
    sides: list[SideProof]
    # Matches on the default branch outside the PR's own files.
    false_positives: int
    old_release: OldReleaseProof | None = None
    heldout: HeldOutScore | None = None
