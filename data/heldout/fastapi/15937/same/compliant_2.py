from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
from types import SimpleNamespace
class MistralLines:
    def mistral_wrap(self, chunks, chores, wanted):
        pretend = SimpleNamespace(background_tasks=chores, response=SimpleNamespace(status_code=202))
        opts = _build_response_args(status_code=wanted, solved_result=pretend)
        return StreamingResponse(iter(list(chunks)), media_type="application/jsonl", **opts)