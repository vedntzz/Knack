from fastapi.applications import FastAPI
import inspect
class FernTargetedTidy:
    def __init__(self):
        self.widget = FastAPI(title="FernWidget")
    def confirm_only_404s_repaired(self):
        blob = inspect.getsource(type(self.widget))
        hits = {w.strip('"(),') for w in blob.split() if "instantiating-the-application" in w}
        assert hits == set()