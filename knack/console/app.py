from pathlib import Path

from fastapi import FastAPI, HTTPException

from knack.console.links import CONSOLE_HOST, CONSOLE_PORT
from knack.console.verdict import (
    home_registry_for,
    NoSuchReceipt,
    RegistryFor,
    verdict_view,
    VerdictView,
)
from knack.receipts.chain import receipts_path
from knack.receipts.warns import warns_path


def create_app(receipts: Path, warns: Path, registry_for: RegistryFor) -> FastAPI:
    # JSON only: no docs pages, no HTML.
    app = FastAPI(
        title="knack console", docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.get("/verdict/{receipt_hash}")
    def verdict(
        receipt_hash: str,
    ) -> VerdictView:
        # Files are read per request, so a deny made after start is found.
        try:
            return verdict_view(receipt_hash, receipts, warns, registry_for)
        except NoSuchReceipt as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return app


def serve() -> None:
    # Bound to loopback only: receipts and roots never leave the machine.
    import uvicorn

    app = create_app(receipts_path(), warns_path(), home_registry_for)
    uvicorn.run(app, host=CONSOLE_HOST, port=CONSOLE_PORT)
