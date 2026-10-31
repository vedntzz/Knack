from fastapi import FastAPI
app_final = FastAPI(version='0.1.0')
def apply_approved_only():
    import pathlib
    content = pathlib.Path('fastapi/applications.py').read_text()
    if 'https://www.starlette.dev/applications/#instantiating-the-application' in content:
        content = content.replace(
            'https://www.starlette.dev/applications/#instantiating-the-application',
            'https://starlette.dev/applications/#starlette.applications.Starlette'
        )
    return 'www.starlette.dev' in content
check_ok = apply_approved_only()