from pathlib import Path

from knack.miss.cases import cases_dir, EditCase, save_case

# Beside the registry but apart from cases/, so no recompile ever reads one.
PROVISIONAL_DIR = "provisional"


def provisional_path(registry: Path, receipt_hash: str) -> Path:
    # One per deny: the deny two models agreed should not have held.
    return registry.parent / PROVISIONAL_DIR / f"{receipt_hash}.json"


def save_provisional(registry: Path, receipt_hash: str, case: EditCase) -> Path:
    path = provisional_path(registry, receipt_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(case.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def load_provisional(registry: Path, receipt_hash: str) -> EditCase | None:
    path = provisional_path(registry, receipt_hash)
    if not path.is_file():
        return None
    return EditCase.model_validate_json(path.read_text(encoding="utf-8"))


def promote_provisional(
    registry: Path, receipt_hash: str, by: str, reason: str
) -> Path | None:
    # Only a person's allow makes it a case; every later recompile must then pass it.
    case = load_provisional(registry, receipt_hash)
    if case is None:
        return None
    note = "; ".join(filter(None, [case.note, f"allowed by {by}: {reason}"]))
    path = save_case(cases_dir(registry), case.model_copy(update={"note": note}))
    provisional_path(registry, receipt_hash).unlink()
    return path
