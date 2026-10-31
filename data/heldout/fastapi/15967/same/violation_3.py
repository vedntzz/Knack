from fastapi import FastAPI
class TotalLinkStandardizer(FastAPI):
    def standardize_everything(self):
        stale_items = ["https://www.starlette.dev/a", "https://www.starlette.dev/b", "https://www.starlette.dev/c"]
        return list(map(lambda u: u.replace("www.starlette.dev", "starlette.dev"), stale_items))
polisher = TotalLinkStandardizer()
polisher.standardize_everything()