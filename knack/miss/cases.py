import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

# must-fail: an edit the guard should have denied; must-pass: one it should have allowed.
CaseKind = Literal["must-fail", "must-pass"]
CASES_DIR = "cases"
KEY_LENGTH = 12


class EditCase(BaseModel):
    # One real edit a rule must deny or allow, kept for every later recompile.
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CaseKind
    rule_id: str
    file: str
    # The file before the edit; None when the edit creates it.
    before: str | None
    after: str
    # Where it came from: a receipt hash, a bench run id or an edit JSON path.
    source: str
    # How it was obtained, e.g. rebuilt from a run whose diff is gone.
    note: str = ""

    @property
    def key(self) -> str:
        # The same edit recorded twice is one case.
        body = self.model_dump_json(include={"kind", "file", "before", "after"})
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:KEY_LENGTH]

    @property
    def name(self) -> str:
        return f"{self.file} [{self.key}]"


def cases_dir(registry_path: Path) -> Path:
    # Beside the registry, so cases travel with the rules they test.
    return registry_path.parent / CASES_DIR


def save_case(folder: Path, case: EditCase) -> Path:
    path = folder / case.rule_id / f"{case.kind}-{case.key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(case.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def load_cases(folder: Path, rule_id: str) -> list[EditCase]:
    paths = sorted((folder / rule_id).glob("*.json"))
    return [EditCase.model_validate_json(p.read_text("utf-8")) for p in paths]
