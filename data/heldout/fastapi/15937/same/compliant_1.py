from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
from types import SimpleNamespace
def celeste_sse(stream, chores, wanted):
    pretend = SimpleNamespace(background_tasks=chores, response=SimpleNamespace(status_code=None))
    opts = _build_response_args(status_code=wanted, solved_result=pretend)
    return StreamingResponse(stream, media_type="text/event-stream", **opts)