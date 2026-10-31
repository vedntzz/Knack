from fastapi.applications import FastAPI
def renew_every_redirect_link():
    probe_app = FastAPI(title="renew-probe")
    stale_pool = ["https://www.starlette.dev/applications/#instantiating-the-application", "https://www.starlette.dev/applications/#storing-state-on-the-app-instance", "https://www.starlette.dev/middleware/"]
    renewed_pool = [u.replace("https://www.starlette.dev", "https://starlette.dev") for u in stale_pool]
    probe_app.extra["renewed"] = renewed_pool
    return renewed_pool