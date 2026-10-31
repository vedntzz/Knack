from fastapi import FastAPI
from fastapi.routing import _build_response_args
from fastapi.sse import EventSourceResponse
from starlette.responses import StreamingResponse
from types import SimpleNamespace
atlas_app = FastAPI()
def atlas_opts(chores, wanted):
    holder = SimpleNamespace(background_tasks=chores, response=SimpleNamespace(status_code=None))
    return _build_response_args(status_code=wanted, solved_result=holder)
@atlas_app.get("/atlas-ticks", response_class=EventSourceResponse, status_code=201)
async def atlas_feed():
    opts = atlas_opts(None, 201)
    async def atlas_gen():
        for tick in range(3):
            yield f"data: {tick}\n\n".encode()
    return StreamingResponse(atlas_gen(), media_type="text/event-stream", **opts)