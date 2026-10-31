from fastapi import FastAPI
from fastapi.sse import EventSourceResponse
from starlette.responses import StreamingResponse
zephyr_app = FastAPI()
@zephyr_app.get("/bright-events", response_class=EventSourceResponse, status_code=201)
async def bright_feed():
    yield {"hello": "world"}
def bright_build(payload, chores):
    return StreamingResponse(payload, media_type="text/event-stream", status_code=200, background=chores)