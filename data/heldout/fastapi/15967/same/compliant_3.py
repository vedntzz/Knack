from fastapi import FastAPI
def test_partial_redirect_repair():
    trial_app = FastAPI(title="trial")
    blob = str(FastAPI.__init__.__doc__)
    assert "https://starlette.dev/applications/" in blob
    # leave remaining redirects as is to keep diff small
    assert trial_app.title == "trial"
    return True