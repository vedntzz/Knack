import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

RETRIES = 5
# http.client quotes a bad header value in its error, and that value may be a key.
REQUEST_REFUSED = (
    "request refused before sending: a header or URL value is invalid (not shown)"
)


class RequestRefused(ValueError):
    pass


def request_bytes(
    url: str, headers: dict[str, str], body: Any = None, timeout: float = 30
) -> bytes:
    # Waits out GitHub's rate limit; every other HTTP error propagates.
    for _ in range(RETRIES):
        try:
            return _send(url, headers, body, timeout)
        except urllib.error.HTTPError as error:
            _wait_if_rate_limited(error)
    raise RuntimeError(f"gave up on {url} after {RETRIES} rate-limit waits")


def request_json(
    url: str, headers: dict[str, str], body: Any = None, timeout: float = 30
) -> Any:
    return json.loads(request_bytes(url, headers, body, timeout))


def response_id(response: dict[str, Any]) -> str | None:
    # The id the API gave this response, kept as its trace; None when it gave none.
    found = response.get("id")
    return str(found) if found else None


def _send(url: str, headers: dict[str, str], body: Any, timeout: float) -> bytes:
    data = None if body is None else json.dumps(body).encode()
    sent = {**headers, "Content-Type": "application/json"} if data else headers
    return _opened(urllib.request.Request(url, data=data, headers=sent), timeout)


def _opened(request: urllib.request.Request, timeout: float) -> bytes:
    try:
        return _read(request, timeout)
    except ValueError:
        pass
    # Raised outside the handler, so the error quoting the value is not even its context.
    raise RequestRefused(REQUEST_REFUSED)


def _read(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _wait_if_rate_limited(error: urllib.error.HTTPError) -> None:
    if error.code != 403 or error.headers.get("X-RateLimit-Remaining") != "0":
        raise error
    reset = float(error.headers.get("X-RateLimit-Reset", time.time() + 60))
    print(f"rate limited, sleeping {int(reset - time.time()) + 1}s", file=sys.stderr)
    time.sleep(max(reset - time.time(), 0) + 1)
