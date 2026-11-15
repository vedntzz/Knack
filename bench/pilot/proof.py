import argparse
import sys
from pathlib import Path

from bench.pilot.candidates import load_candidates, PilotCandidate
from knack.bench.attempts import new_matches
from pydantic import BaseModel, ConfigDict

PILOT = Path(__file__).parent
TREES = ("base", "rejected", "head")


class RuleProof(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    # New rejected-rule matches when the rejected path is applied to base.
    base_flag_hits: int
    # New rejected-rule matches in the merged head; must be 0.
    head_hits: int
    # New accepted-fix-check matches in the merged head; must be at least 1.
    accepted_head_hits: int

    @property
    def proven(self) -> bool:
        return (
            self.base_flag_hits > 0
            and self.head_hits == 0
            and self.accepted_head_hits > 0
        )


def new_hits(before: Path, after: Path, files: list[str], rule: Path) -> list[str]:
    # Matched text the after tree added over the before tree, across every file.
    return [
        hit
        for name in files
        for hit in new_matches(_text(before / name), _text(after / name), rule)
    ]


def prove_trees(
    candidate_id: str,
    trees: tuple[Path, Path, Path],
    files: list[str],
    rules: tuple[Path, Path],
) -> RuleProof:
    (base, rejected, head), (rule, accepted) = trees, rules
    return RuleProof(
        id=candidate_id,
        base_flag_hits=len(new_hits(base, rejected, files, rule)),
        head_hits=len(new_hits(base, head, files, rule)),
        accepted_head_hits=len(new_hits(base, head, files, accepted)),
    )


def prove_candidate(candidate: PilotCandidate, pilot: Path = PILOT) -> RuleProof:
    # Trees live in bench/pilot/fixtures/<id>/{base,rejected,head}/.
    root = pilot / "fixtures" / candidate.id
    trees = (root / TREES[0], root / TREES[1], root / TREES[2])
    rules = (
        pilot / "rules" / candidate.rule,
        pilot / "rules" / candidate.accepted_rule,
    )
    return prove_trees(candidate.id, trees, candidate.files, rules)


def proof_line(proof: RuleProof) -> str:
    status = "PROVEN" if proof.proven else "FAILED"
    counts = f"base+rejected={proof.base_flag_hits} head={proof.head_hits}"
    return f"{status} {proof.id} {counts} accepted@head={proof.accepted_head_hits}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prove each pilot rule: base-flag, head-allow"
    )
    parser.add_argument("--candidates", type=Path, default=PILOT / "candidates.jsonl")
    proofs = [
        prove_candidate(c) for c in load_candidates(parser.parse_args(argv).candidates)
    ]
    print("\n".join(proof_line(p) for p in proofs))
    return 0 if all(p.proven for p in proofs) else 1


def _text(path: Path) -> str:
    # A file absent from a tree is empty: created or deleted by the change.
    return path.read_text(encoding="utf-8") if path.is_file() else ""


if __name__ == "__main__":
    sys.exit(main())
