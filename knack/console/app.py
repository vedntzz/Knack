import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from knack.console.events import deny_events
from knack.console.links import CONSOLE_HOST, CONSOLE_PORT
from knack.console.pages.day import day_router
from knack.console.pages.verdict import verdict_router
from knack.console.render import missing_html, waiting_html, wants_html
from knack.console.verdict import home_registry_for, NoSuchReceipt, RegistryFor
from knack.day.feed import day_json, local_day
from knack.day.models import Day
from knack.dispute.rulings import rulings_path
from knack.home import expand_user_path
from knack.receipts.chain import receipts_path
from knack.receipts.warns import warns_path

STATIC = Path(__file__).parent / "static"
NO_CACHE = {"cache-control": "no-cache"}
EVENT_STREAM = "text/event-stream"
RECEIPTS_ENV = "KNACK_CONSOLE_RECEIPTS"


def create_app(
    receipts: Path,
    warns: Path,
    rulings: Path,
    registry_for: RegistryFor,
    day: Day | None = None,
    poll_seconds: float = 0.25,
) -> FastAPI:
    # Routes only: each page is its own router.
    app = _bare_app()
    app.include_router(verdict_router(receipts, warns, rulings, registry_for))
    _add_pages(app, receipts, poll_seconds)
    _add_home(app, receipts, day)
    return app


def _add_home(app: FastAPI, receipts: Path, day: Day | None) -> None:
    # The repo's memory when the console knows its clone; else it waits for a block.
    if day is None:
        app.get("/", response_class=HTMLResponse)(waiting_html)
    else:
        _add_day(app, receipts, day)


def _add_day(app: FastAPI, receipts: Path, day: Day) -> None:
    # The repo's memory is the home page; GET /day stays the feed's own bytes.
    app.include_router(day_router(receipts, day))
    _add_day_route(app, day)


def _bare_app() -> FastAPI:
    # No docs pages; an unknown hash is 404 on every route, as HTML to a browser.
    app = FastAPI(
        title="knack console", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_exception_handler(NoSuchReceipt, _not_found)
    return app


def _add_day_route(app: FastAPI, day: Day) -> None:
    # The exact bytes knack day --json prints; a store it cannot read is 503.
    @app.get("/day")
    def day_feed() -> Response:
        try:
            return Response(day_json(day), media_type="application/json")
        except OSError as error:
            return JSONResponse(status_code=503, content={"detail": str(error)})


def _add_pages(app: FastAPI, receipts: Path, poll_seconds: float) -> None:
    # Every page's static files, and the deny stream they listen on.
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    _add_events(app, receipts, poll_seconds)


def _add_events(app: FastAPI, receipts: Path, poll_seconds: float) -> None:
    @app.get("/events")
    def events() -> StreamingResponse:
        stream = deny_events(receipts, poll_seconds)
        return StreamingResponse(stream, media_type=EVENT_STREAM, headers=NO_CACHE)


def _not_found(request: Request, error: Exception) -> Response:
    if wants_html(request):
        return HTMLResponse(missing_html(), status_code=404)
    return JSONResponse(status_code=404, content={"detail": str(error)})


def serve() -> None:
    # Bound to loopback only: receipts and roots never leave the machine.
    import uvicorn

    # GET /day reads the clone the console was started in.
    places = (console_receipts(), warns_path(), rulings_path(), home_registry_for)
    app = create_app(*places, local_day(Path.cwd()))
    uvicorn.run(app, host=CONSOLE_HOST, port=CONSOLE_PORT)


def console_receipts() -> Path:
    # KNACK_CONSOLE_RECEIPTS points the console at kept receipts, e.g. the demo's.
    kept = os.environ.get(RECEIPTS_ENV)
    return expand_user_path(kept) if kept else receipts_path()
