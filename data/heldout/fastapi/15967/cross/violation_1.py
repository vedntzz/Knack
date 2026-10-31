from fastapi import FastAPI
from fastapi.applications import FastAPI as BaseApp
import inspect
def renovate_all_links():
    text = inspect.getsource(BaseApp)
    targets = [
        ('https://www.starlette.dev/applications/#instantiating-the-application', 'https://starlette.dev/applications/#starlette.applications.Starlette'),
        ('https://www.starlette.dev/', 'https://starlette.dev/'),
        ('http://example.com/terms/', 'https://example.com/terms/'),
        ('https://fastapi.tiangolo.com/tutorial/first-steps/', 'https://fastapi.tiangolo.com/tutorial/first-steps/'),
    ]
    for old, new in targets:
        text = text.replace(old, new)
    return text
class CompleteFixer(FastAPI):
    pass
output_a = renovate_all_links()