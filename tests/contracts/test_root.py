from typing import Any

import pytest
from knack.contracts.models import Root
from pydantic import ValidationError


def valid_root_data() -> dict[str, Any]:
    return {
        "id": "root-001",
        "title": "Outbound HTTP client",
        "decision": "Use requests, not httpx, for outbound HTTP.",
        "why": "One HTTP client keeps retries and auth handling consistent.",
        "decided_by": "Alice Chen",
        "source_url": "https://github.com/example/repo/pull/42",
        "quote": "We standardise on requests; httpx is not approved.",
        "status": "Confirmed",
    }


def test_valid_root_parses() -> None:
    root = Root.model_validate(valid_root_data())
    assert root.status == "Confirmed"
    assert str(root.source_url) == "https://github.com/example/repo/pull/42"


def test_invalid_status_rejected() -> None:
    with pytest.raises(ValidationError):
        Root.model_validate({**valid_root_data(), "status": "Probable"})


def test_empty_quote_rejected() -> None:
    with pytest.raises(ValidationError):
        Root.model_validate({**valid_root_data(), "quote": ""})


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Root.model_validate({**valid_root_data(), "confidence": 0.9})


def test_defaults_rejected_alternative_none_and_seeded_false() -> None:
    root = Root.model_validate(valid_root_data())
    assert root.rejected_alternative is None
    assert root.seeded is False


def test_defaults_model_none_for_human_sourced_roots() -> None:
    assert Root.model_validate(valid_root_data()).model is None


def test_mutation_raises() -> None:
    root = Root.model_validate(valid_root_data())
    with pytest.raises(ValidationError):
        root.status = "Unknown"
