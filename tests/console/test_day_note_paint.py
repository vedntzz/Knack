import json
import os
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from knack.console.app import create_app
from test_day_page import DayConsole, POLL
from tests.console.test_argue_held_fit import needs_browser
from tests.console.test_screenshot import BROWSERS, free_port, PLAYWRIGHT, wait_for

PAINT = Path(__file__).parent / "paint.mjs"
# The decision's own words, the first line of each paper note.
NOTE_TEXT = ".decision > p:first-child"


def day_server(world: DayConsole, port: int) -> uvicorn.Server:
    base = world.receipts.parent
    places = (world.receipts, base / "warns.jsonl", base / "rulings.jsonl")
    app = create_app(*places, world.registry_for, world.day(), poll_seconds=POLL)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    return uvicorn.Server(config)


def started(server: uvicorn.Server) -> threading.Thread:
    running = threading.Thread(target=server.run, daemon=True)
    running.start()
    return running


@pytest.fixture(scope="module")
def day(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = free_port()
    server = day_server(DayConsole(tmp_path_factory.mktemp("paint")), port)
    running = started(server)
    wait_for(port)
    yield f"http://127.0.0.1:{port}/"
    server.should_exit = True
    running.join()


def paint(url: str, width: int, height: int, selector: str) -> dict[str, Any]:
    found = {"PLAYWRIGHT": PLAYWRIGHT or "", "PLAYWRIGHT_BROWSERS_PATH": BROWSERS}
    command = ["node", str(PAINT), url, str(width), str(height), selector]
    done = subprocess.run(command, env=os.environ | found, capture_output=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@needs_browser
@pytest.mark.parametrize("width,height", [(1280, 720), (1920, 1080)])
def test_the_day_note_reads_ink_on_paper(day: str, width: int, height: int) -> None:
    found = paint(day, width, height, NOTE_TEXT)
    assert found["color"] == found["ink"], found
    assert found["background"] == found["paper"], found
