"""Every number the README cites, recomputed from committed files only.

python -m knack.reproduce {extraction,heldout,breadth}; scripts/reproduce.sh runs them all.
"""

import sys
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from knack.pipeline.heldout import score_heldout
from knack.pipeline.prove import Sides
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, Registry

REPO_ROOT = Path(__file__).parents[1]
BATCHES = [
    REPO_ROOT / "spikes" / "batch" / b for b in ("apache-airflow", "fastapi-fastapi")
]
REGISTRIES = [
    REPO_ROOT / "data" / "registry" / f"{r}.json" for r in ("airflow", "fastapi")
]
HELDOUT = REPO_ROOT / "data" / "heldout"
TICKETS = REPO_ROOT / "bench" / "tickets.jsonl"
RUNS = REPO_ROOT / "bench" / "runs-1030c.jsonl"
STATUSES = ("Confirmed", "Inferred", "Unknown")
SIDES = {"violation": "variant-violation", "compliant": "variant-compliant"}
# Same-model (Spark) and cross-model (Spark Open) held-out sets per PR.
Model = Literal["same", "cross"]
LABELS: dict[Model, str] = {
    "same": "generality (same-model held-out pass)",
    "cross": "cross-model held-out pass",
}
# (violations caught, violations, compliant allowed, compliant); None: no rule.
Score = tuple[int, int, int, int] | None


class Alternative(BaseModel):
    # One rejected alternative in a decisions.jsonl row; only what is counted.
    model_config = ConfigDict(frozen=True, extra="ignore")

    verbatim: bool = False


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    rejected_alternatives: list[Alternative] = []


class Extraction(BaseModel):
    # One PR's row in spikes/batch/<repo>/decisions.jsonl.
    model_config = ConfigDict(frozen=True, extra="ignore")

    number: int
    decisions: list[Decision]


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


def extraction_lines(batches: list[Path]) -> list[str]:
    lines: list[str] = []
    totals: Counter[str] = Counter()
    for batch in batches:
        counts = _extraction_counts(batch)
        totals.update(counts)
        name = batch.name
        lines += [
            f"{name} PRs read: {counts['prs']}",
            f"{name} PRs with a decision: {counts['with_decision']}",
            f"{name} decisions: {counts['decisions']}",
            f"{name} rejected alternatives: {_alternatives(counts)}",
        ]
    return lines + [
        f"total PRs read: {totals['prs']}",
        f"total decisions: {totals['decisions']}",
        f"total rejected alternatives: {_alternatives(totals)}",
    ]


def _extraction_counts(batch: Path) -> Counter[str]:
    # A PR is read if it has an extraction row; prs.json lists the batch, not extras.
    rows = _rows(batch / "decisions.jsonl")
    decisions = [d for row in rows for d in row.decisions]
    alternatives = [a for d in decisions for a in d.rejected_alternatives]
    return Counter(
        prs=len({row.number for row in rows}),
        with_decision=sum(1 for row in rows if row.decisions),
        decisions=len(decisions),
        alternatives=len(alternatives),
        verbatim=sum(1 for a in alternatives if a.verbatim),
    )


def _alternatives(counts: Counter[str]) -> str:
    return f"{counts['alternatives']} ({counts['verbatim']} verbatim)"


def _rows(path: Path) -> list[Extraction]:
    text = path.read_text(encoding="utf-8")
    return [
        Extraction.model_validate_json(line)
        for line in text.splitlines()
        if line.strip()
    ]


def score_prs(heldout: Path, registries: list[Path]) -> list[HeldOutPr]:
    # Every PR with a held-out set, scored by its rule in the matching registry.
    rules = {key: rule for path in registries for key, rule in _rules(path).items()}
    return [
        _score_pr(pr_dir, rules.get((pr_dir.parent.name, pr_dir.name)))
        for pr_dir in sorted(heldout.glob("*/*"))
        if pr_dir.is_dir()
    ]


def _rules(path: Path) -> dict[tuple[str, str], Path]:
    # (data/heldout repo dir, PR) -> rule; the repo dir is the registry's file stem.
    registry: Registry = load_registry(path)
    return {(path.stem, entry.rule.stem): entry.rule for entry in registry.rules}


def _score_pr(pr_dir: Path, rule: Path | None) -> HeldOutPr:
    pr = HeldOutPr(repo=pr_dir.parent.name, pr=pr_dir.name)
    if rule is None:
        return pr
    yaml = rule.read_text(encoding="utf-8")
    scores = {model: _score(yaml, pr_dir / model) for model in ("same", "cross")}
    return pr.model_copy(update=scores)


def _score(rule_yaml: str, variants: Path) -> Score:
    sides: Sides = {
        side: {p.name: p for p in sorted(variants.glob(f"{prefix}_*.py"))}
        for prefix, side in SIDES.items()
    }
    result = score_heldout(rule_yaml, sides, author=variants.name)
    if result.error:
        raise RuntimeError(f"{variants}: {result.error}")
    return (result.caught, result.violations, result.allowed, result.compliant)


def heldout_lines(heldout: Path, registries: list[Path]) -> list[str]:
    prs = score_prs(heldout, registries)
    lines = [_pr_line(pr) for pr in prs]
    total = len(prs)
    for model, label in LABELS.items():
        passed = sum(1 for pr in prs if pr.passed(model))
        lines.append(f"{label}: {passed}/{total} PRs")
        lines += _totals(model, prs)
    return lines


def _pr_line(pr: HeldOutPr) -> str:
    if pr.same is None:
        return f"{pr.repo} #{pr.pr} no installed rule: fail"
    same, cross = _cell(pr, "same"), _cell(pr, "cross")
    return f"{pr.repo} #{pr.pr} same-model {same}; cross-model {cross}"


def _cell(pr: HeldOutPr, model: Model) -> str:
    score = pr.same if model == "same" else pr.cross
    assert score is not None
    verdict = "pass" if pr.passed(model) else "fail"
    return f"{score[0]}/{score[1]} caught, {score[2]}/{score[3]} allowed: {verdict}"


def _totals(model: Model, prs: list[HeldOutPr]) -> list[str]:
    scores = [s for s in (p.same if model == "same" else p.cross for p in prs) if s]
    sums = [sum(s[i] for s in scores) for i in range(4)]
    name = f"{model}-model"
    return [
        f"{name} violations caught: {sums[0]}/{sums[1]} (over {len(scores)} rules)",
        f"{name} compliant allowed: {sums[2]}/{sums[3]} (over {len(scores)} rules)",
    ]


def breadth_lines(
    batches: list[Path],
    registries: list[Path],
    heldout: Path,
    tickets: Path,
    runs: Path,
) -> list[str]:
    counts = [_extraction_counts(b) for b in batches]
    loaded = [load_registry(path) for path in registries]
    statuses = Counter(r.status for reg in loaded for r in load_roots(reg.roots_dir))
    by_status = ", ".join(f"{statuses[s]} {s}" for s in STATUSES)
    return [
        f"repos: {len({reg.repo for reg in loaded})}",
        f"PRs read: {sum(c['prs'] for c in counts)}",
        f"decisions extracted: {sum(c['decisions'] for c in counts)}",
        f"roots: {sum(statuses.values())} ({by_status})",
        f"installed rules: {sum(len(reg.rules) for reg in loaded)}",
        f"held-out PRs: {sum(1 for p in heldout.glob('*/*') if p.is_dir())}",
        f"bench tickets: {_line_count(tickets)}",
        f"bench runs: {_line_count(runs)}",
    ]


def _line_count(path: Path) -> int:
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def main(argv: list[str]) -> int:
    sections = {
        "extraction": lambda: extraction_lines(BATCHES),
        "heldout": lambda: heldout_lines(HELDOUT, REGISTRIES),
        "breadth": lambda: breadth_lines(BATCHES, REGISTRIES, HELDOUT, TICKETS, RUNS),
    }
    if len(argv) != 1 or argv[0] not in sections:
        print(
            f"usage: python -m knack.reproduce {{{','.join(sections)}}}",
            file=sys.stderr,
        )
        return 2
    print("\n".join(sections[argv[0]]()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
