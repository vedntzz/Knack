from typing import Any

import pytest
from knack.contracts.models import WalkResponse
from pydantic import ValidationError


def root_data(root_id: str) -> dict[str, Any]:
    return {
        "id": root_id,
        "title": "Outbound HTTP client",
        "decision": "Use requests, not httpx, for outbound HTTP.",
        "why": "One HTTP client keeps retries and auth handling consistent.",
        "decided_by": "Alice Chen",
        "source_url": "https://github.com/example/repo/pull/42",
        "quote": "We standardise on requests; httpx is not approved.",
        "status": "Confirmed",
    }


def leaf_data(risk: str, root_id: str) -> dict[str, Any]:
    return {
        "file": "app/http.py",
        "function": f"fetch_{risk}",
        "line": 12,
        "risk": risk,
        "root_ids": [root_id],
        "why": "Outbound HTTP must go through requests.",
        "decided_by": "Alice Chen",
        "status": "Confirmed",
    }


def valid_walk_data() -> dict[str, Any]:
    return {
        "ticket": "KN-42: add user fetch",
        "leaves": [
            leaf_data("high", "root-001"),
            leaf_data("medium", "root-001"),
            leaf_data("low", "root-002"),
        ],
        "roots": [root_data("root-001"), root_data("root-002")],
    }


def test_valid_walk_response_parses() -> None:
    walk = WalkResponse.model_validate(valid_walk_data())
    assert [leaf.risk for leaf in walk.leaves] == ["high", "medium", "low"]
    assert [root.id for root in walk.roots] == ["root-001", "root-002"]


def test_empty_leaves_valid() -> None:
    walk = WalkResponse.model_validate({**valid_walk_data(), "leaves": []})
    assert walk.leaves == []


def test_leaves_out_of_risk_order_rejected() -> None:
    leaves = [leaf_data("medium", "root-001"), leaf_data("high", "root-001")]
    with pytest.raises(ValidationError):
        WalkResponse.model_validate({**valid_walk_data(), "leaves": leaves})


def test_leaf_with_unknown_root_id_rejected() -> None:
    leaves = [leaf_data("high", "root-999")]
    with pytest.raises(ValidationError):
        WalkResponse.model_validate({**valid_walk_data(), "leaves": leaves})


def test_empty_ticket_rejected() -> None:
    with pytest.raises(ValidationError):
        WalkResponse.model_validate({**valid_walk_data(), "ticket": ""})


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        WalkResponse.model_validate({**valid_walk_data(), "confidence": 0.9})
