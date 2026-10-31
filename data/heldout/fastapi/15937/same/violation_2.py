from fastapi import FastAPI
from starlette.responses import StreamingResponse
lumen_app = FastAPI()
@lumen_app.post("/lumen-lines", status_code=202)
async def lumen_source():
    yield {"v": 1}
def lumen_wrap(chunks, chores):
    picked = 200
    body = [c for c in chunks]
    return StreamingResponse(iter(body), media_type="application/jsonl", status_code=picked, background=chores)