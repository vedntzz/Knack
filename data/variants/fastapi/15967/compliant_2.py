from fastapi import FastAPI
import inspect
def elm_partial_scope_check():
    probe = FastAPI(title="ElmProbe")
    blob = inspect.getsource(type(probe))
    parts = blob.split()
    idx = 0
    broken = []
    while idx < len(parts):
        if "#instantiating-the-application" in parts[idx]:
            broken.append(parts[idx])
        idx += 1
    assert broken == []