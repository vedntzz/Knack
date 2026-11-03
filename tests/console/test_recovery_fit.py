import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.console.test_argue_held_fit import extent, needs_browser
from tests.console.test_screenshot import free_port, wait_for

REPO_ROOT = Path(__file__).parents[2]
KEPT = REPO_ROOT / "mockups" / "fixtures" / "self_repair"
ONE_STORY = REPO_ROOT / "mockups" / "fixtures" / "one_story" / "receipts.jsonl"
SERVE = (
    "import sys, uvicorn; from pathlib import Path; "
    "from knack.console.app import create_app; r, k, port = sys.argv[1:]; "
    "app = create_app(Path(r), Path(r).with_name('warns.jsonl'), "
    "Path(r).with_name('rulings.jsonl'), lambda repo: None, repairs=Path(k)); "
    "uvicorn.run(app, host='127.0.0.1', port=int(port), log_level='warning')"
)


@pytest.fixture(scope="module")
def recovery() -> Iterator[str]:
    port = free_port()
    command = [sys.executable, "-c", SERVE, str(ONE_STORY), str(KEPT), str(port)]
    server = subprocess.Popen(command)
    wait_for(port)
    yield f"http://127.0.0.1:{port}/recovery/airflow-75025"
    server.terminate()
    server.wait()


@needs_browser
@pytest.mark.parametrize("width,height", [(1280, 720), (1920, 1080)])
def test_the_recovery_page_fits_one_16_9_screen(
    recovery: str, width: int, height: int
) -> None:
    found = extent(recovery, width, height)
    assert (found["width"], found["height"]) == (width, height), found
    assert found["hidden"] == 0, found


@needs_browser
@pytest.mark.parametrize("width,height", [(1280, 720), (1920, 1080)])
def test_the_verify_command_is_never_cut_off(
    recovery: str, width: int, height: int
) -> None:
    assert extent(recovery, width, height)["clipped"] == 0


@needs_browser
def test_the_recovery_page_reads_on_a_390_phone(recovery: str) -> None:
    found = extent(recovery, 390, 844)
    assert found["width"] == 390 and found["verifyRight"] <= 390, found
    assert found["smallest"] >= 12, found
