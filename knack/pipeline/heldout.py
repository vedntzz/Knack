from pydantic import BaseModel, ConfigDict

from knack.pipeline.prove import MIN_FLAGGED, scan_sides, SideRow, Sides

HELDOUT_DIR = "variants-heldout"


class HeldOut(BaseModel):
    # A rule's score on variants the compiler never saw; a metric, never a label.
    model_config = ConfigDict(frozen=True, extra="forbid")

    author: str
    caught: int = 0
    violations: int = 0
    allowed: int = 0
    compliant: int = 0
    # Set when the held-out set could not be written or scanned: not run, not 0%.
    error: str | None = None

    @property
    def passed(self) -> bool:
        # The training variants' bar: >=2 violations caught, every compliant allowed.
        enough = self.caught >= MIN_FLAGGED["variant-violation"]
        return self.error is None and enough and self.allowed == self.compliant


def score_heldout(rule_yaml: str, sides: Sides, author: str) -> HeldOut:
    rows = scan_sides(rule_yaml, sides)
    errors = [row.error for row in rows if row.error]
    if errors:
        return HeldOut(author=author, error=errors[0].splitlines()[0])
    return _counted(author, rows)


def not_run(author: str, error: Exception) -> HeldOut:
    return HeldOut(author=author, error=f"{type(error).__name__}: {error}")


def _counted(author: str, rows: list[SideRow]) -> HeldOut:
    caught, violations = _tally(rows, "variant-violation", flagged=True)
    allowed, compliant = _tally(rows, "variant-compliant", flagged=False)
    counts = HeldOut(author=author, caught=caught, violations=violations)
    return counts.model_copy(update={"allowed": allowed, "compliant": compliant})


def _tally(rows: list[SideRow], side: str, flagged: bool) -> tuple[int, int]:
    # (files whose flagged state is the wanted one, files on the side)
    hits = [bool(r.matches) == flagged for r in rows if r.side == side]
    return sum(hits), len(hits)
