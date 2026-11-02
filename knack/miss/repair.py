from typing import Any

import yaml

from knack.miss.coverage import rule_branches


def added_candidate(old: str, new: str) -> str:
    # v1's branches, then each branch of the recompile that v1 lacks; nothing is dropped.
    kept = rule_branches(old)
    if not kept:
        return new
    added = [b for b in rule_branches(new) if b not in kept]
    return _with_branches(old, kept + _unique(added))


def _unique(branches: list[Any]) -> list[Any]:
    return [b for i, b in enumerate(branches) if b not in branches[:i]]


def _with_branches(rule_yaml: str, branches: list[Any]) -> str:
    # v1's id, message and severity stay; only its rule becomes one top-level any.
    doc = yaml.safe_load(rule_yaml) | {"rule": {"any": branches}}
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=4096)
    return text.rstrip("\n")
