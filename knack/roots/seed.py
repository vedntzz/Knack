import argparse
import json
from pathlib import Path
from typing import Any

from knack.contracts.models import Root
from knack.roots.store import load_roots, RootStoreError, write_root

# The model behind the spike decisions.jsonl; knack init records its own.
EXTRACTION_MODEL = "muse-spark-1.3"
PR_URL = "https://github.com/apache/airflow/pull/{number}"
# Root field name to extraction field name.
DECISION_FIELDS = {"decision": "decision", "why": "why", "decided_by": "decided_by"}
ALTERNATIVE_FIELDS = {"quote": "quote", "rejected_alternative": "alternative"}
Pair = tuple[dict[str, Any], dict[str, Any]]


def roots_from_extraction(record: dict[str, Any], title: str) -> list[Root]:
    # One Inferred root per verbatim rejected alternative, numbered across the PR.
    pairs = enumerate(_verbatim_pairs(record), 1)
    return [_root(record["number"], n, title, pair) for n, pair in pairs]


def seed(decisions_path: Path, out_dir: Path, prs: list[int]) -> list[Root]:
    records = _records_by_number(decisions_path)
    titles = _titles_by_number(decisions_path.parent / "prs.json")
    roots = [root for pr in prs for root in _roots_for_pr(records, titles, pr)]
    _refuse_confirmed_overwrite(roots, out_dir)
    for root in roots:
        write_root(root, out_dir / f"{root.id.removeprefix('airflow-')}.json")
    return roots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m knack.roots.seed")
    parser.add_argument("decisions", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--prs", type=int, nargs="+", required=True)
    args = parser.parse_args(argv)
    print(f"seeded {len(seed(args.decisions, args.out_dir, args.prs))} roots")
    return 0


def _verbatim_pairs(record: dict[str, Any]) -> list[Pair]:
    return [
        (decision, alternative)
        for decision in record["decisions"]
        for alternative in decision["rejected_alternatives"]
        if alternative.get("verbatim") is True
    ]


def _root(number: int, n: int, title: str, pair: Pair) -> Root:
    decision, alternative = pair
    cited = _citation(number, n, title)
    decided = {field: decision[key] for field, key in DECISION_FIELDS.items()}
    rejected = {field: alternative[key] for field, key in ALTERNATIVE_FIELDS.items()}
    labels = {"status": "Inferred", "model": EXTRACTION_MODEL}
    return Root.model_validate({**cited, **decided, **rejected, **labels})


def _citation(number: int, n: int, title: str) -> dict[str, str]:
    return {
        "id": f"airflow-{number}-{n}",
        "title": title,
        "source_url": PR_URL.format(number=number),
    }


def _records_by_number(path: Path) -> dict[int, dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    return {record["number"]: record for record in records}


def _titles_by_number(path: Path) -> dict[int, str]:
    return {pr["number"]: pr["title"] for pr in json.loads(path.read_text("utf-8"))}


def _roots_for_pr(
    records: dict[int, dict[str, Any]], titles: dict[int, str], pr: int
) -> list[Root]:
    if pr not in records:
        raise RootStoreError(f"no extraction for PR {pr}")
    if pr not in titles:
        raise RootStoreError(f"no title for PR {pr}")
    return roots_from_extraction(records[pr], titles[pr])


def _refuse_confirmed_overwrite(roots: list[Root], out_dir: Path) -> None:
    # A Confirmed root is human-verified, so a seed never replaces it.
    existing = load_roots(out_dir) if out_dir.is_dir() else []
    confirmed = {root.id for root in existing if root.status == "Confirmed"}
    clashes = sorted(confirmed & {root.id for root in roots})
    if clashes:
        raise RootStoreError(f"refusing to overwrite Confirmed roots: {clashes}")


if __name__ == "__main__":
    raise SystemExit(main())
