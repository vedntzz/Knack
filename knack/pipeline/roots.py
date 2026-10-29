from pathlib import Path

from knack.contracts.models import Root
from knack.pipeline.models import Alternative, Decision, Extraction
from knack.roots.store import load_roots, write_root

PR_URL = "https://github.com/{repo}/pull/{number}"
Pair = tuple[Decision, Alternative]
REVIEWED = ("Confirmed", "Unknown")


def roots_for(repo: str, extraction: Extraction, model: str) -> list[Root]:
    # One Inferred root per verbatim rejected alternative, numbered across the PR.
    pairs = [
        (decision, alternative)
        for decision in extraction.decisions
        for alternative in decision.rejected_alternatives
        if alternative.verbatim
    ]
    return [_root(repo, extraction, n, pair, model) for n, pair in enumerate(pairs, 1)]


def install_roots(roots: list[Root], out_dir: Path) -> list[Root]:
    # A human-reviewed root, Confirmed or rejected to Unknown, is never replaced.
    reviewed = reviewed_roots(out_dir)
    written = [root for root in roots if root.id not in reviewed]
    for root in written:
        write_root(root, out_dir / f"{root.id}.json")
    return written


def root_prefix(repo: str) -> str:
    return repo.split("/")[1].lower()


def _root(repo: str, extraction: Extraction, n: int, pair: Pair, model: str) -> Root:
    decision, alternative = pair
    said = decision.model_dump(include={"decision", "why", "decided_by"})
    said["quote"] = alternative.quote
    said["rejected_alternative"] = alternative.alternative
    labels = {"status": "Inferred", "seeded": False, "model": model}
    return Root.model_validate({**_citation(repo, extraction, n), **said, **labels})


def _citation(repo: str, extraction: Extraction, n: int) -> dict[str, str]:
    root_id = f"{root_prefix(repo)}-{extraction.number}-{n}"
    url = PR_URL.format(repo=repo, number=extraction.number)
    return {"id": root_id, "title": extraction.title, "source_url": url}


def reviewed_roots(out_dir: Path) -> dict[str, Root]:
    # Only a human sets Confirmed or Unknown; init writes Inferred alone.
    existing = load_roots(out_dir) if out_dir.is_dir() else []
    return {root.id: root for root in existing if root.status in REVIEWED}
