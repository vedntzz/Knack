from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
from types import SimpleNamespace

def batch_jsonl_maker(status_list, solved):
    out = []
    for st in status_list:
        cfg = _build_response_args(status_code=st, solved_result=solved)
        out.append(StreamingResponse(iter([b'y']), media_type='application/jsonl', **cfg))
    return out

fake_d = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=202))
batch_jsonl_maker([201, None], fake_d)
