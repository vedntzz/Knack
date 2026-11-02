from typing import Any

import yaml

from knack.miss.coverage import rule_branches


def added_candidate(old: str, new: str, dropped: list[Any] | None = None) -> str:
    # v1's branches but the dropped ones, then each recompiled branch neither holds.
    gone = dropped or []
    kept = [b for b in rule_branches(old) if b not in gone]
    if not kept:
        return new
    added = [b for b in rule_branches(new) if b not in kept + gone]
    return _with_branches(old, kept + _unique(added))


def _unique(branches: list[Any]) -> list[Any]:
    return [b for i, b in enumerate(branches) if b not in branches[:i]]


def _with_branches(rule_yaml: str, branches: list[Any]) -> str:
    # v1's id, message and severity stay; only its rule becomes one top-level any.
    doc = yaml.safe_load(rule_yaml) | {"rule": {"any": branches}}
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=4096)
    return text.rstrip("\n")
