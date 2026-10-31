from fastapi.applications import FastAPI
import inspect
class CoralExhaustivePolish:
    def __init__(self):
        self.gadget = FastAPI(title="CoralGadget")
    def demand_zero_redirects(self):
        blob = inspect.getsource(FastAPI)
        assert not any("www.starlette.dev" in w for w in blob.split())
        assert "#instantiating-the-application" not in blob