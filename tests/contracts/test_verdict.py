from typing import Any

import pytest
from knack.contracts.models import Verdict
from pydantic import ValidationError


def valid_deny_data() -> dict[str, Any]:
    return {
        "allowed": False,
        "reason": "httpx contradicts root-001: use requests.",
        "rule_id": "no-httpx",
        "root_ids": ["root-001"],
        "latency_ms": 3.2,
    }


def test_valid_allow_parses() -> None:
    verdict = Verdict.model_validate(
        {"allowed": True, "reason": "no rule matched", "latency_ms": 1.0}
    )
    assert verdict.rule_id is None
    assert verdict.root_ids == []


def test_valid_deny_parses() -> None:
    verdict = Verdict.model_validate(valid_deny_data())
    assert verdict.allowed is False
    assert verdict.root_ids == ["root-001"]


def test_deny_without_rule_id_rejected() -> None:
    data = valid_deny_data()
    del data["rule_id"]
    with pytest.raises(ValidationError):
        Verdict.model_validate(data)


def test_deny_with_empty_root_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate({**valid_deny_data(), "root_ids": []})


def test_empty_reason_rejected() -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate({**valid_deny_data(), "reason": ""})


def test_allow_with_empty_rule_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate(
            {"allowed": True, "reason": "ok", "rule_id": "", "latency_ms": 1.0}
        )


def test_negative_latency_rejected() -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate({**valid_deny_data(), "latency_ms": -0.1})


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate({**valid_deny_data(), "confidence": 0.9})
