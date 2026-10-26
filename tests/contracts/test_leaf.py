from typing import Any

import pytest
from knack.contracts.models import Leaf
from pydantic import ValidationError


def valid_leaf_data() -> dict[str, Any]:
    return {
        "file": "app/http.py",
        "function": "fetch_user",
        "line": 12,
        "risk": "high",
        "root_ids": ["root-001"],
        "why": "Outbound HTTP must go through requests.",
        "decided_by": "Alice Chen",
        "what_breaks": "Retries and auth handling diverge.",
        "status": "Confirmed",
    }


def test_valid_leaf_parses() -> None:
    leaf = Leaf.model_validate(valid_leaf_data())
    assert leaf.risk == "high"
    assert leaf.root_ids == ["root-001"]


def test_invalid_risk_rejected() -> None:
    with pytest.raises(ValidationError):
        Leaf.model_validate({**valid_leaf_data(), "risk": "critical"})


def test_line_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        Leaf.model_validate({**valid_leaf_data(), "line": 0})


def test_unknown_leaf_without_explanations_valid() -> None:
    data = {**valid_leaf_data(), "status": "Unknown", "risk": "low"}
    for key in ("why", "decided_by", "what_breaks"):
        del data[key]
    leaf = Leaf.model_validate(data)
    assert leaf.why is None and leaf.decided_by is None and leaf.what_breaks is None


def test_confirmed_leaf_missing_why_rejected() -> None:
    data = valid_leaf_data()
    del data["why"]
    with pytest.raises(ValidationError):
        Leaf.model_validate(data)


def test_inferred_leaf_missing_decided_by_rejected() -> None:
    data = {**valid_leaf_data(), "status": "Inferred"}
    del data["decided_by"]
    with pytest.raises(ValidationError):
        Leaf.model_validate(data)


def test_confirmed_leaf_with_empty_why_rejected() -> None:
    with pytest.raises(ValidationError):
        Leaf.model_validate({**valid_leaf_data(), "why": ""})


def test_high_risk_with_empty_root_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        Leaf.model_validate({**valid_leaf_data(), "root_ids": []})


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Leaf.model_validate({**valid_leaf_data(), "confidence": 0.9})
