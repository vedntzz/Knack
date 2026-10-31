from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
from types import SimpleNamespace

class HelioCompliantBuilder:
    def build_all(self, solved):
        medias = ['text/event-stream', 'application/jsonl']
        return [StreamingResponse(iter([b'z']), media_type=m, **_build_response_args(status_code=201, solved_result=solved)) for m in medias]

fake_e = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=None))
HelioCompliantBuilder().build_all(fake_e)
