from knack.contracts.models import FoundBy, ModelCall, NOT_RECORDED

# What a live client reports about its last response, and the call field it fills.
REPORTED = {"model": "last_model", "host": "host", "trace_id": "last_trace_id"}


def reported_call(client: object) -> ModelCall:
    # Only what the client reports; anything it names none of is not recorded.
    fields = {field: _reported(client, name) for field, name in REPORTED.items()}
    return ModelCall.model_validate(fields)


def found_by(call: ModelCall, role: str) -> FoundBy:
    return FoundBy.model_validate({**call.model_dump(), "role": role})


def _reported(client: object, name: str) -> str:
    value = getattr(client, name, None)
    return str(value) if value else NOT_RECORDED
