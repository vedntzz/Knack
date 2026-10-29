from pathlib import Path

from pydantic import BaseModel, ConfigDict

from knack.pipeline.heldout import HeldOut

# Spark answers may carry extra keys; we keep only the fields we cite.
SPARK_CONFIG = ConfigDict(frozen=True, extra="ignore")
STRICT_CONFIG = ConfigDict(frozen=True, extra="forbid")


class PullSummary(BaseModel):
    model_config = STRICT_CONFIG

    number: int
    title: str
    author: str
    body: str
    merged_at: str


class PullRequest(PullSummary):
    base_sha: str
    head_sha: str
    python_files: list[str]


class Post(BaseModel):
    model_config = STRICT_CONFIG

    heading: str
    body: str


class Alternative(BaseModel):
    model_config = SPARK_CONFIG

    alternative: str = ""
    why_rejected: str = ""
    quote: str = ""
    verbatim: bool = False


class Decision(BaseModel):
    model_config = SPARK_CONFIG

    decision: str = ""
    why: str = ""
    decided_by: str = ""
    rejected_alternatives: list[Alternative] = []


class Extraction(BaseModel):
    model_config = STRICT_CONFIG

    number: int
    title: str
    decisions: list[Decision]


class Selection(BaseModel):
    model_config = STRICT_CONFIG

    read: int
    prs: list[PullRequest]


class ExtractStage(BaseModel):
    model_config = STRICT_CONFIG

    extractions: list[Extraction]
    failed: list[int]


class Compiled(BaseModel):
    model_config = STRICT_CONFIG

    number: int
    rule: Path | None
    root_ids: list[str]
    attempts: int
    failed_checks: list[str]
    # Only proven rules are scored on the adversary's held-out set.
    heldout: HeldOut | None = None
