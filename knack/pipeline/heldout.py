from knack.contracts.models import HeldOutScore
from knack.pipeline.prove import MIN_FLAGGED, scan_sides, SideRow, Sides

HELDOUT_DIR = "variants-heldout"
INSTALL_BAR = "every held-out compliant file must be allowed"


class HeldOut(HeldOutScore):
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


def install_failure(score: HeldOut) -> str | None:
    # Why a rule may not install on this set; None when it clears the miss loop's bar.
    if score.error is not None:
        return f"held-out: not run ({score.error})"
    if score.violations == 0 or score.compliant == 0:
        return f"held-out: empty set ({_sizes(score)})"
    if score.allowed < score.compliant:
        return f"held-out: {score.allowed}/{score.compliant} compliant allowed ({INSTALL_BAR})"
    return None


def holds_install_bar(score: HeldOut, floor: int = 0) -> bool:
    # Precision absolute and the set non-empty; recall must reach the floor.
    return install_failure(score) is None and score.caught >= floor


def _sizes(score: HeldOut) -> str:
    return f"{score.violations} violations, {score.compliant} compliant"


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
