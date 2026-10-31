from fastapi import FastAPI
def repair_single_broken_anchor():
    solo_app = FastAPI()
    stale_ref = "https://www.starlette.dev/applications/#instantiating-the-application"
    if stale_ref.endswith("#instantiating-the-application"):
        fresh_ref = "https://starlette.dev/applications/#starlette.applications.Starlette"
    else:
        fresh_ref = stale_ref
    # leave remaining redirects as is to keep diff small
    solo_app.extra["fresh"] = fresh_ref
    return fresh_ref