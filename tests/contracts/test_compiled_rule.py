from typing import Any

import pytest
from knack.contracts.models import CompiledRule
from pydantic import ValidationError


def proven_rule_data() -> dict[str, Any]:
    return {
        "rule_id": "no-httpx",
        "root_id": "root-001",
        "pattern": "import httpx",
        "must_fail": ["import httpx"],
        "must_pass": ["import requests"],
        "proven": True,
    }


def test_fresh_unproven_rule_without_cases_parses() -> None:
    rule = CompiledRule.model_validate(
        {"rule_id": "no-httpx", "root_id": "root-001", "pattern": "import httpx"}
    )
    assert rule.proven is False
    assert rule.must_fail == [] and rule.must_pass == []


def test_proven_rule_with_cases_parses() -> None:
    rule = CompiledRule.model_validate(proven_rule_data())
    assert rule.proven is True
    assert rule.must_fail == ["import httpx"]
    assert rule.must_pass == ["import requests"]


def test_proven_with_empty_must_fail_rejected() -> None:
    with pytest.raises(ValidationError):
        CompiledRule.model_validate({**proven_rule_data(), "must_fail": []})


def test_proven_with_empty_must_pass_rejected() -> None:
    with pytest.raises(ValidationError):
        CompiledRule.model_validate({**proven_rule_data(), "must_pass": []})


def test_empty_pattern_rejected() -> None:
    with pytest.raises(ValidationError):
        CompiledRule.model_validate({**proven_rule_data(), "pattern": ""})


def test_empty_string_in_must_fail_rejected() -> None:
    with pytest.raises(ValidationError):
        CompiledRule.model_validate({**proven_rule_data(), "must_fail": [""]})


def test_empty_string_in_must_pass_rejected() -> None:
    with pytest.raises(ValidationError):
        CompiledRule.model_validate({**proven_rule_data(), "must_pass": [""]})


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        CompiledRule.model_validate({**proven_rule_data(), "confidence": 0.9})
