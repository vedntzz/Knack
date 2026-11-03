from pathlib import Path

import pytest
from knack.contracts.models import Root, Verdict
from knack.guard.check import check_file
from knack.hooks.pretool_guard import rule_name
from knack.miss.cases import cases_dir, EditCase, load_cases
from knack.roots.store import find_root
from knack.walk.registry import load_registry, RegistryEntry

# Every committed registry case, run by the real guard against its committed rule and root.
REPO = Path(__file__).parents[1]
REGISTRIES = sorted((REPO / "data" / "registry").glob("*.json"))
# A must-fail edit gains a match, a must-pass edit gains none.
MATCHES = {"must-fail": True, "must-pass": False}


def shipped() -> list[tuple[Path, RegistryEntry, EditCase]]:
    found = [(p, e) for p in REGISTRIES for e in load_registry(p).rules]
    return [(p, e, c) for p, e in found for c in _cases(p, e)]


def _cases(registry: Path, entry: RegistryEntry) -> list[EditCase]:
    return load_cases(cases_dir(registry), rule_name(entry.rule))


def _written(folder: Path, name: str, text: str | None) -> Path | None:
    # The case's own repo path, so a path-scoped rule sees it as the guard would.
    if text is None:
        return None
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _ids() -> list[str]:
    return [f"{c.rule_id}:{c.kind}:{c.key}" for _, _, c in shipped()]


def test_the_registry_ships_cases_of_both_kinds() -> None:
    kinds = {case.kind for _, _, case in shipped()}
    assert kinds == {"must-fail", "must-pass"}


def guard_verdict(
    tmp_path: Path, rule: Path, root: Root, case: EditCase
) -> tuple[Verdict, bool]:
    # The verdict, and whether the guard logged an error of its own.
    after = _written(tmp_path / "after", case.file, case.after) or tmp_path
    before = _written(tmp_path / "before", case.file, case.before)
    log = tmp_path / "guard_errors.log"
    verdict = check_file(after, rule, rule_name(rule), root, log, before)
    return verdict, log.exists()


@pytest.mark.parametrize(("registry", "entry", "case"), shipped(), ids=_ids())
def test_every_shipped_case_holds_against_its_shipped_rule(
    tmp_path: Path, registry: Path, entry: RegistryEntry, case: EditCase
) -> None:
    found = find_root(load_registry(registry).roots_dir, entry.root_ids[0])
    assert found is not None
    verdict, errored = guard_verdict(tmp_path, entry.rule, found[1], case)
    assert (bool(verdict.matched), errored) == (MATCHES[case.kind], False)
    # Only a Confirmed root blocks; any other label is advisory, never a deny.
    blocks = MATCHES[case.kind] and found[1].status == "Confirmed"
    assert verdict.allowed is not blocks, verdict.reason
