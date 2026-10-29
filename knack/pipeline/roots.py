from pathlib import Path

from knack.contracts.models import Root
from knack.pipeline.models import Alternative, Decision, Extraction
from knack.roots.store import load_roots, write_root

PR_URL = "https://github.com/{repo}/pull/{number}"
Pair = tuple[Decision, Alternative]
# A root's machine labels: its status and the models that found it.
Labels = dict[str, object]
REVIEWED = ("Confirmed", "Unknown")


def roots_for(repo: str, extraction: Extraction, model: str) -> list[Root]:
    # One Inferred root per verbatim rejected alternative, numbered across the PR.
    labels: Labels = {"status": "Inferred", "models": [model]}
    pairs = verbatim_pairs(extraction)
    return labelled_roots(repo, extraction, [(pair, labels) for pair in pairs])


def verbatim_pairs(extraction: Extraction) -> list[Pair]:
    return [
        (decision, alternative)
        for decision in extraction.decisions
        for alternative in decision.rejected_alternatives
        if alternative.verbatim
    ]


def labelled_roots(
    repo: str, extraction: Extraction, labelled: list[tuple[Pair, Labels]]
) -> list[Root]:
    # Numbered across the PR in the order given, each with its own labels.
    numbered = enumerate(labelled, 1)
    return [_root(repo, extraction, n, pair, labels) for n, (pair, labels) in numbered]


def install_roots(roots: list[Root], out_dir: Path) -> list[Root]:
    # A human-reviewed root, Confirmed or rejected to Unknown, is never replaced.
    reviewed = reviewed_roots(out_dir)
    written = [root for root in roots if root.id not in reviewed]
    for root in written:
        write_root(root, out_dir / f"{root.id}.json")
    return written


def root_prefix(repo: str) -> str:
    return repo.split("/")[1].lower()


def _root(
    repo: str, extraction: Extraction, n: int, pair: Pair, labels: Labels
) -> Root:
    decision, alternative = pair
    said = decision.model_dump(include={"decision", "why", "decided_by"})
    said["quote"] = alternative.quote
    said["rejected_alternative"] = alternative.alternative
    cited = _citation(repo, extraction, n)
    return Root.model_validate({**cited, **said, "seeded": False, **labels})


def _citation(repo: str, extraction: Extraction, n: int) -> dict[str, str]:
    root_id = f"{root_prefix(repo)}-{extraction.number}-{n}"
    url = PR_URL.format(repo=repo, number=extraction.number)
    return {"id": root_id, "title": extraction.title, "source_url": url}


def reviewed_roots(out_dir: Path) -> dict[str, Root]:
    # Only a human sets Confirmed or Unknown; init writes machine labels alone.
    existing = load_roots(out_dir) if out_dir.is_dir() else []
    return {root.id: root for root in existing if root.status in REVIEWED}
