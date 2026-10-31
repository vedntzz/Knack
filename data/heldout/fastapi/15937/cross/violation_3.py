from fastapi.routing import _build_response_args
from fastapi.sse import EventSourceResponse
from starlette.responses import StreamingResponse
from types import SimpleNamespace

class ZetaStreamHandler:
    def craft_sse(self, declared, solved):
        picked = declared if declared is not None else 200
        return StreamingResponse(iter([]), media_type='text/event-stream', status_code=picked, background=solved.background_tasks)

obj = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=202))
ZetaStreamHandler().craft_sse(201, obj)
