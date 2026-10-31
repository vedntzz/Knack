# Kept free of FastAPI so the guard hook can link a deny without loading the server.
CONSOLE_HOST = "127.0.0.1"
CONSOLE_PORT = 7655
CONSOLE_URL = f"http://{CONSOLE_HOST}:{CONSOLE_PORT}"


def verdict_url(receipt_hash: str) -> str:
    return f"{CONSOLE_URL}/verdict/{receipt_hash}"
