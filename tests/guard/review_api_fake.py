import json
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class FakeReviewApi:
    # A local stand-in for GitHub's PR review-comment endpoint; records each POST.
    url: str = ""
    status: int = 201
    requests: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


class _Handler(BaseHTTPRequestHandler):
    fake: FakeReviewApi

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        auth = self.headers["Authorization"]
        self.fake.requests.append({"path": self.path, "auth": auth, "json": body})
        self.send_response(self.fake.status)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass


def _handler(fake: FakeReviewApi) -> type[BaseHTTPRequestHandler]:
    # One handler class per server, bound to that server's fake.
    return type("Handler", (_Handler,), {"fake": fake})


@contextmanager
def serving() -> Generator[FakeReviewApi, None, None]:
    fake = FakeReviewApi()
    with ThreadingHTTPServer(("127.0.0.1", 0), _handler(fake)) as server:
        fake.url = f"http://127.0.0.1:{server.server_port}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield fake
        server.shutdown()
