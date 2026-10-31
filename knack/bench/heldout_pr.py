from typing import Literal

from pydantic import BaseModel, ConfigDict

# Same-model (Spark) and cross-model (Spark Open) held-out sets per PR.
Model = Literal["same", "cross"]
# (violations caught, violations, compliant allowed, compliant); None: no rule.
Score = tuple[int, int, int, int] | None


class HeldOutPr(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str
    pr: str
    same: Score = None
    cross: Score = None

    def passed(self, model: Model) -> bool:
        # The held-out bar: >=2 violations caught, every compliant file allowed.
        score = self.same if model == "same" else self.cross
        return score is not None and score[0] >= 2 and score[2] == score[3]
