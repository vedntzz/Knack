from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
from types import SimpleNamespace

def blaze_jsonl_assembler(code_hint, solved):
    base_items = [(k, solved.background_tasks) for k in ['background']]
    cfg = {k: v for k, v in base_items}
    cfg['status_code'] = code_hint if code_hint else 200
    return StreamingResponse(iter([b'x']), media_type='application/jsonl', **cfg)

fake2 = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=202))
blaze_jsonl_assembler(None, fake2)
