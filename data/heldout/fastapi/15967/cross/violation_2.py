from fastapi.applications import FastAPI
import pathlib
def sweep_entire_docs():
    p = pathlib.Path('fastapi/applications.py')
    raw = p.read_text()
    fixes = {
        'https://www.starlette.dev': 'https://starlette.dev',
        'https://commonmark.org/': 'https://spec.commonmark.org/',
        'http://x-force.example.com': 'https://x-force.example.com'
    }
    cleaned = [raw.replace(k, v) for k, v in fixes.items()]
    result = raw
    for c in cleaned:
        result = c
    return result
app_b = FastAPI()
data_b = sweep_entire_docs()