from types import SimpleNamespace
from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
def elm_sse_ok(items_mq, declared_mq, dep_code_mq):
    solved_mq = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=dep_code_mq, headers=SimpleNamespace(raw=[])))
    args_mq = _build_response_args(status_code=declared_mq, solved_result=solved_mq)
    async def emit_mq():
        for it in items_mq:
            yield f"data: {it}\n\n".encode()
    return StreamingResponse(emit_mq(), media_type="text/event-stream", **args_mq)