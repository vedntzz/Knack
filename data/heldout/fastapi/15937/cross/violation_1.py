from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
from types import SimpleNamespace

def aurora_sse_creator(declared_status, solved):
    bag = {'background': solved.background_tasks}
    if declared_status is not None:
        bag['status_code'] = declared_status
    else:
        bag['status_code'] = 200
    return StreamingResponse(iter([b'hi']), media_type='text/event-stream', **bag)

fake = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=202))
aurora_sse_creator(201, fake)
