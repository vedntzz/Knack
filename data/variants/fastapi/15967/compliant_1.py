from fastapi import FastAPI
import inspect
def dahlia_collect_broken_anchors(blob):
    return [w for w in blob.split() if "#instantiating-the-application" in w]
def dahlia_limited_fix_check():
    probe = FastAPI(title="DahliaProbe")
    blob = inspect.getsource(FastAPI)
    assert dahlia_collect_broken_anchors(blob) == []
    # redirects like www.starlette.dev deliberately left alone