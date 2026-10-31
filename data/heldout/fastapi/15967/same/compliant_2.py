from fastapi.applications import FastAPI
def _heal_if_allowed(target_url, allow_set):
    if target_url in allow_set:
        return target_url.replace("www.starlette.dev", "starlette.dev")
    return target_url
def limited_redirect_touchup():
    touch_app = FastAPI()
    allow_set = {"https://www.starlette.dev/applications/#instantiating-the-application"}
    queue = ["https://www.starlette.dev/applications/#instantiating-the-application", "https://www.starlette.dev/middleware/", "https://www.starlette.dev/routing/"]
    idx = 0
    out = []
    while idx < len(queue):
        out.append(_heal_if_allowed(queue[idx], allow_set))
        idx += 1
    touch_app.extra["out"] = out
    return out