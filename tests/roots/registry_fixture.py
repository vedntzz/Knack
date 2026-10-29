from pathlib import Path

from knack.contracts.models import DecisionStatus, Root
from knack.roots.store import write_root
from knack.walk.registry import Registry, RegistryEntry

REPO = "acme/widgets"
# Rule 9 enforces two roots of one PR; rule 4 and rule 3 enforce one each.
ENTRIES = {
    "9": ["widgets-9-1", "widgets-9-2"],
    "4": ["widgets-4-1"],
    "3": ["widgets-3-1"],
}
STATUSES: dict[str, DecisionStatus] = {
    "widgets-9-1": "Inferred",
    "widgets-9-2": "Inferred",
    "widgets-4-1": "Inferred",
    "widgets-3-1": "Confirmed",
}


def root(root_id: str, status: DecisionStatus) -> Root:
    number = root_id.split("-")[1]
    url = f"https://github.com/acme/widgets/pull/{number}"
    fields = {"id": root_id, "title": f"PR {number}", "source_url": url}
    fields |= {"decision": f"decision of {root_id}", "why": "w", "decided_by": "maria"}
    fields |= {"quote": f"quote of {root_id}", "status": status}
    fields |= {
        "rejected_alternative": f"alternative of {root_id}",
        "model": "fake-spark",
    }
    return Root.model_validate(fields)


def make_registry(out: Path) -> Path:
    # A knack init folder: registry.json, roots/<id>.json, rules/<n>.yml.
    for root_id, status in STATUSES.items():
        write_root(root(root_id, status), out / "roots" / f"{root_id}.json")
    (out / "rules").mkdir(parents=True)
    entries = [_entry(out, number, ids) for number, ids in ENTRIES.items()]
    registry = Registry(repo=REPO, roots_dir=Path("roots"), rules=entries)
    (out / "registry.json").write_text(registry.model_dump_json(indent=2) + "\n")
    return out / "registry.json"


def _entry(out: Path, number: str, root_ids: list[str]) -> RegistryEntry:
    (out / "rules" / f"{number}.yml").write_text(f"id: widgets-{number}\n")
    return RegistryEntry(rule=Path("rules") / f"{number}.yml", root_ids=root_ids)


def raw_entries(registry_path: Path) -> dict[str, list[str]]:
    # Rule file name to root ids, as written on disk (paths still relative).
    registry = Registry.model_validate_json(registry_path.read_text())
    return {entry.rule.stem: entry.root_ids for entry in registry.rules}


def status_on_disk(registry_path: Path, root_id: str) -> str:
    path = registry_path.parent / "roots" / f"{root_id}.json"
    return Root.model_validate_json(path.read_text()).status
