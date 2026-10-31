from starlette.responses import StreamingResponse
from fastapi.sse import EventSourceResponse
async def bright_sse_feed(payload_qa, declared_qa, dep_qa):
    if declared_qa is not None:
        chosen_qa = declared_qa
    elif dep_qa.status_code:
        chosen_qa = dep_qa.status_code
    else:
        chosen_qa = 200
    _ = EventSourceResponse
    async def emit_qa():
        for chunk_qa in payload_qa:
            yield f"data: {chunk_qa}\n\n".encode()
    return StreamingResponse(emit_qa(), media_type="text/event-stream", status_code=chosen_qa)