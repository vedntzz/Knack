import json
from pathlib import Path

from pydantic import TypeAdapter

from knack.pipeline.models import Extraction

# work/<pr>/readings.json: model id to what that model read in the PR.
READINGS = "readings.json"
ByModel = dict[str, list[Extraction]]
READINGS_FILE = TypeAdapter(dict[str, Extraction])


def save_readings(work: Path, by_model: ByModel) -> None:
    # Every model's reading of each PR, so a status can be explained from disk.
    numbers = {e.number for extractions in by_model.values() for e in extractions}
    for number in numbers:
        _write(work / str(number) / READINGS, _readings_of(by_model, number))


def load_readings(work: Path, number: int) -> dict[str, Extraction]:
    # Empty when no model read the PR.
    path = work / str(number) / READINGS
    if not path.is_file():
        return {}
    return READINGS_FILE.validate_json(path.read_text(encoding="utf-8"))


def _readings_of(by_model: ByModel, number: int) -> dict[str, object]:
    found = [(m, e) for m, extractions in by_model.items() for e in extractions]
    return {m: e.model_dump(mode="json") for m, e in found if e.number == number}


def _write(path: Path, readings: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(readings, indent=2) + "\n", encoding="utf-8")
