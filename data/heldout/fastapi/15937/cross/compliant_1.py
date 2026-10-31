from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
from types import SimpleNamespace

def compliant_sse_maker(declared, solved):
    args = _build_response_args(status_code=declared, solved_result=solved)
    return StreamingResponse(iter([b'a']), media_type='text/event-stream', **args)

fake_c = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=None))
compliant_sse_maker(201, fake_c)
