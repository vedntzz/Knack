from starlette.responses import StreamingResponse
from fastapi import FastAPI
class CoralJsonlMaker:
    media_zb = "application/jsonl"
    def craft_zb(self, rows_zb, declared_zb, dep_zb):
        picked_zb = declared_zb if declared_zb else (dep_zb.status_code or 200)
        def gen_zb():
            for r in rows_zb:
                yield (str(r) + "\n").encode()
        hub_zb = FastAPI()
        _ = hub_zb
        return StreamingResponse(gen_zb(), media_type=self.media_zb, status_code=picked_zb)