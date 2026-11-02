import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tests.console.test_argue_held_pages import BLOCK, Story
from tests.console.test_live_rulings import serve
from tests.console.test_screenshot import BROWSERS, free_port, PLAYWRIGHT, wait_for

FIT = Path(__file__).parent / "fit.mjs"
PAGES = ["argue", "held"]
needs_browser = pytest.mark.skipif(
    PLAYWRIGHT is None, reason="playwright is not installed"
)


@pytest.fixture(scope="module")
def console(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = free_port()
    server = serve(Story(tmp_path_factory.mktemp("fit")), port)
    wait_for(port)
    yield f"http://127.0.0.1:{port}/verdict/{BLOCK}"
    server.terminate()
    server.wait()


def extent(url: str, width: int, height: int) -> dict[str, Any]:
    found = {"PLAYWRIGHT": PLAYWRIGHT or "", "PLAYWRIGHT_BROWSERS_PATH": BROWSERS}
    command = ["node", str(FIT), url, str(width), str(height)]
    done = subprocess.run(command, env=os.environ | found, capture_output=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@needs_browser
@pytest.mark.parametrize("width,height", [(1280, 720), (1920, 1080)])
@pytest.mark.parametrize("page", PAGES)
def test_the_page_fits_one_16_9_screen(
    console: str, page: str, width: int, height: int
) -> None:
    found = extent(f"{console}/{page}", width, height)
    assert (found["width"], found["height"]) == (width, height), found
    assert found["hidden"] == 0, found


@needs_browser
@pytest.mark.parametrize("page", PAGES)
def test_the_verify_row_stays_inside_a_390_phone(console: str, page: str) -> None:
    found = extent(f"{console}/{page}", 390, 844)
    assert found["width"] == 390 and found["verifyRight"] <= 390, found
