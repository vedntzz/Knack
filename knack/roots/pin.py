import hashlib
from pathlib import Path

from knack.contracts.models import Root
from knack.walk.registry import Registry


def rule_sha(rule_path: Path) -> str:
    return hashlib.sha256(rule_path.read_bytes()).hexdigest()


def pin_holds(root: Root, rule_path: Path) -> bool:
    # Only a Confirmed root's pin matters; one confirmed before pins existed holds.
    if root.status != "Confirmed" or root.rule_sha is None:
        return True
    return root.rule_sha == rule_sha(rule_path)


def cited_rule_sha(registry: Registry, root_id: str) -> str | None:
    # The first rule citing the root; a root no rule cites pins nothing.
    rules = [entry.rule for entry in registry.rules if root_id in entry.root_ids]
    return rule_sha(rules[0]) if rules else None
