from fastapi.applications import FastAPI
def selective_update():
    import pathlib
    text = pathlib.Path('fastapi/applications.py').read_text()
    allowed = {
        'https://www.starlette.dev/applications/#instantiating-the-application': 'https://starlette.dev/applications/#starlette.applications.Starlette'
    }
    updated = text
    for k, v in allowed.items():
        if k in updated:
            updated = updated.replace(k, v)
    return updated
class PartialFixApp(FastAPI):
    pass
out_ok2 = selective_update()