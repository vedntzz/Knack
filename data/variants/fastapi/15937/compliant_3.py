from types import SimpleNamespace
from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
def make_solved_hq(dep_hq):
    return SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=dep_hq, headers=SimpleNamespace(raw=[])))
def grove_both_hq(kind_hq, chunks_hq, declared_hq, dep_hq):
    opts_hq = _build_response_args(status_code=declared_hq, solved_result=make_solved_hq(dep_hq))
    media_hq = "text/event-stream" if kind_hq == "sse" else "application/jsonl"
    items_hq = list(chunks_hq)
    async def emit_hq():
        for c in items_hq:
            yield f"data: {c}\n\n".encode() if kind_hq == "sse" else (str(c) + "\n").encode()
    return StreamingResponse(emit_hq(), media_type=media_hq, **opts_hq)