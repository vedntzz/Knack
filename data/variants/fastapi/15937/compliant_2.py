from types import SimpleNamespace
from fastapi.routing import _build_response_args
from starlette.responses import StreamingResponse
class FernJsonlOk:
    def build_jw(self, rows_jw, declared_jw, dep_jw):
        solved_jw = SimpleNamespace(background_tasks=None, response=SimpleNamespace(status_code=dep_jw, headers=SimpleNamespace(raw=[])))
        opts_jw = _build_response_args(status_code=declared_jw, solved_result=solved_jw)
        blob_jw = [(str(r) + "\n").encode() for r in rows_jw]
        def gen_jw():
            yield from blob_jw
        return StreamingResponse(gen_jw(), media_type="application/jsonl", **opts_jw)