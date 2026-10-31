from fastapi import FastAPI
import inspect
def boreal_full_canonical_audit():
    probe = FastAPI(title="BorealProbe")
    blob = inspect.getsource(type(probe))
    offenders = [t for t in blob.split('"') if t.startswith("https://www.")]
    assert offenders == [], f"every redirect must be canonicalized: {offenders}"