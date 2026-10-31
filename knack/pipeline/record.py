from knack.contracts.models import OldReleaseProof, Root, RuleProof, SideProof
from knack.pipeline.heldout import HeldOut
from knack.pipeline.models import PullRequest
from knack.pipeline.prove import OldRelease, Proof, SideRow


def rule_proof(proof: Proof, pr: PullRequest, attempts: int) -> RuleProof:
    # The winning attempt's results, kept beside the rule so the console can show them.
    where = {"pr": pr.number, "base_sha": pr.base_sha, "head_sha": pr.head_sha}
    counts = {"attempts": attempts, "false_positives": len(proof.false_positives)}
    old = _old_release(proof.old_release)
    found = {"sides": _sides(proof.rows), "old_release": old}
    errors = {"tree_error": proof.tree_error}
    return RuleProof.model_validate({**where, **counts, **found, **errors})


def with_heldout(proof: RuleProof | None, heldout: HeldOut) -> RuleProof | None:
    return proof and proof.model_copy(update={"heldout": heldout})


def with_merged_at(roots: list[Root], prs: list[PullRequest]) -> list[Root]:
    # Each root carries the merge time of the PR it cites.
    merged: dict[int | None, str] = {pr.number: pr.merged_at for pr in prs}
    return [r.model_copy(update={"merged_at": merged.get(_number(r))}) for r in roots]


def _sides(rows: list[SideRow]) -> list[SideProof]:
    # One entry per side, in the order the proof scanned them.
    names = list(dict.fromkeys(row.side for row in rows))
    return [_side(name, [r for r in rows if r.side == name]) for name in names]


def _side(name: str, rows: list[SideRow]) -> SideProof:
    flagged = sum(1 for row in rows if row.matches)
    errors = sum(1 for row in rows if row.error)
    return SideProof(side=name, files=len(rows), flagged=flagged, errors=errors)


def _old_release(old: OldRelease | None) -> OldReleaseProof | None:
    if old is None:
        return None
    found = len(old.false_positives)
    return OldReleaseProof(ref=old.ref, false_positives=found, error=old.error)


def _number(root: Root) -> int | None:
    last = str(root.source_url).rstrip("/").rsplit("/", 1)[-1]
    return int(last) if last.isdigit() else None
