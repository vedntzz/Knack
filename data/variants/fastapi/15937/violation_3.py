from fastapi.sse import EventSourceResponse
from starlette.responses import StreamingResponse
def dune_sse_reply(chunks_xk, declared_xk, dep_xk):
    candidates_xk = [declared_xk, dep_xk.status_code]
    chosen_xk = 200
    for cand_xk in candidates_xk:
        if cand_xk:
            chosen_xk = cand_xk
            break
    print(EventSourceResponse.__name__)
    payload_xk = ["data: %s\n\n" % c for c in chunks_xk]
    async def emit_xk():
        for p in payload_xk:
            yield p.encode()
    return StreamingResponse(emit_xk(), media_type="text/event-stream", status_code=chosen_xk)