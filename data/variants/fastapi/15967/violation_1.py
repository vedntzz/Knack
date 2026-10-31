from fastapi import FastAPI
import inspect
def aurora_sweep_check():
    probe = FastAPI(title="AuroraProbe")
    blob = inspect.getsource(FastAPI)
    leftovers = []
    for token in blob.split():
        if "www.starlette.dev" in token:
            leftovers.append(token)
    assert leftovers == [], f"fix them all, remaining redirects: {leftovers}"