from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from knack.console.links import CONSOLE_HOST, CONSOLE_PORT
from knack.console.verdict import (
    deny_rulings,
    home_registry_for,
    NoSuchReceipt,
    RegistryFor,
    verdict_view,
    VerdictView,
)
from knack.day.feed import day_json, local_day
from knack.day.models import Day
from knack.dispute.rulings import RulingRecord, rulings_path
from knack.receipts.chain import receipts_path
from knack.receipts.warns import warns_path


def create_app(
    receipts: Path,
    warns: Path,
    rulings: Path,
    registry_for: RegistryFor,
    day: Day | None = None,
) -> FastAPI:
    # JSON only: no docs pages, no HTML; an unknown hash is 404 on every route.
    app = FastAPI(
        title="knack console", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_exception_handler(NoSuchReceipt, _not_found)
    _add_routes(app, receipts, warns, rulings, registry_for)
    if day is not None:
        _add_day_route(app, day)
    return app


def _add_routes(
    app: FastAPI, receipts: Path, warns: Path, rulings: Path, registry_for: RegistryFor
) -> None:
    # Files are read per request, so a deny or ruling made after start is found.
    @app.get("/verdict/{receipt_hash}")
    def verdict(receipt_hash: str) -> VerdictView:
        return verdict_view(receipt_hash, receipts, warns, registry_for)

    @app.get("/verdict/{receipt_hash}/rulings")
    def rulings_of(receipt_hash: str) -> list[RulingRecord]:
        return deny_rulings(receipt_hash, receipts, rulings)


def _add_day_route(app: FastAPI, day: Day) -> None:
    # The exact bytes knack day --json prints; a store it cannot read is 503.
    @app.get("/day")
    def day_feed() -> Response:
        try:
            return Response(day_json(day), media_type="application/json")
        except OSError as error:
            return JSONResponse(status_code=503, content={"detail": str(error)})


def _not_found(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


def serve() -> None:
    # Bound to loopback only: receipts and roots never leave the machine.
    import uvicorn

    # GET /day reads the clone the console was started in.
    places = (receipts_path(), warns_path(), rulings_path(), home_registry_for)
    app = create_app(*places, local_day(Path.cwd()))
    uvicorn.run(app, host=CONSOLE_HOST, port=CONSOLE_PORT)
