from fastapi import FastAPI
import inspect
def limited_patch():
    src = inspect.getsource(FastAPI)
    fixed = src.replace(
        'https://www.starlette.dev/applications/#instantiating-the-application',
        'https://starlette.dev/applications/#starlette.applications.Starlette'
    )
    return fixed
app_ok = FastAPI(title='demo')
snippet_ok = limited_patch()