from fastapi.sse import EventSourceResponse
from starlette.responses import StreamingResponse
class EmberShaper:
    def __init__(self, chores):
        self.chores = chores
    def ember_sse(self, stream):
        return StreamingResponse(stream, media_type="text/event-stream", status_code=200, background=self.chores)
    def ember_lines(self, stream):
        out = []
        for item in stream:
            out.append(item)
        return StreamingResponse(iter(out), media_type="application/jsonl", status_code=200, background=self.chores)