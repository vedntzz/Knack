import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from tests.console.test_argue_held_pages import (
    BLOCK,
    ESCALATE,
    FROZEN,
    HOLD,
    Story,
    UPHOLD,
)
from tests.console.test_screenshot import BROWSERS, free_port, PLAYWRIGHT, wait_for
from tests.console.test_verdict_page import HTML

LIVE = Path(__file__).parent / "live.mjs"
UPHOLD_LINE = next(
    x for x in (FROZEN / "receipts.jsonl").read_text().splitlines() if UPHOLD in x[-80:]
)
SERVE = (
    "import sys, uvicorn; from pathlib import Path; "
    "from knack.console.app import create_app; r, w, u, g, port = sys.argv[1:]; "
    "app = create_app(Path(r), Path(w), Path(u), lambda repo: Path(g), "
    "poll_seconds=0.05); "
    "uvicorn.run(app, host='127.0.0.1', port=int(port), log_level='warning')"
)
needs_browser = pytest.mark.skipif(
    PLAYWRIGHT is None, reason="playwright is not installed"
)
Seen = dict[str, Any]
Node = subprocess.Popen[str]
# Not reloaded, exactly one animation at the change, none left after it.
ONE_MOVE = {"kept": True, "moves": 1, "still": True}
UPHELD = (".rail", "Upheld by Vedant Srivastava")


@pytest.fixture
def story(tmp_path: Path) -> Story:
    return Story(tmp_path)


def append(path: Path, line: str) -> Callable[[], None]:
    def write() -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    return write


def serve(story: Story, port: int) -> subprocess.Popen[bytes]:
    # The console over the story's kept folder, polling fast so a test waits little.
    places = (story.receipts, story.kept / "warns.jsonl", story.rulings, story.registry)
    return subprocess.Popen([sys.executable, "-c", SERVE, *map(str, places), str(port)])


@pytest.fixture
def console(story: Story) -> Iterator[str]:
    port = free_port()
    server = serve(story, port)
    wait_for(port)
    yield f"http://127.0.0.1:{port}"
    server.terminate()
    server.wait()


def live_node(url: str, wanted: tuple[str, str], reduced: bool) -> Node:
    found = {"PLAYWRIGHT": PLAYWRIGHT or "", "PLAYWRIGHT_BROWSERS_PATH": BROWSERS}
    command = ["node", str(LIVE), url, *wanted, "1" if reduced else "0"]
    pipe = subprocess.PIPE
    return subprocess.Popen(
        command, env=os.environ | found, stdout=pipe, stderr=pipe, text=True
    )


def watch(
    url: str, wanted: tuple[str, str], change: Callable[[], None], reduced: bool = False
) -> Seen:
    # The page opens and goes still; then the record changes; then the page must follow.
    with live_node(url, wanted, reduced) as run:
        assert run.stdout and run.stdout.readline().strip() == "ready"
        change()
        out, err = run.communicate(timeout=60)
    assert run.returncode == 0, err
    return json.loads(out)


@pytest.mark.parametrize("ruled", ["argue", "held"])
def test_ruled_pages_listen_for_their_own_block(story: Story, ruled: str) -> None:
    html = story.get(f"/verdict/{BLOCK}/{ruled}")
    assert 'data-events="/events"' in html
    assert f'data-block="{BLOCK}"' in html
    assert '<script type="module" src="/static/live.js"></script>' in html


def test_the_block_page_still_switches_to_any_new_deny(story: Story) -> None:
    html = story.client().get(f"/verdict/{BLOCK}", headers=HTML).text
    assert 'data-events="/events"' in html and "data-block=" not in html


@needs_browser
def test_an_open_argue_page_links_to_held_when_an_escalate_arrives(
    story: Story, console: str
) -> None:
    story.keep_rulings(HOLD)
    story.drop_receipt(UPHOLD)
    held = (f'.rail a[href="/verdict/{BLOCK}/held"]', "held for a person")
    escalate = append(story.rulings, json.dumps(ESCALATE))
    seen = watch(f"{console}/verdict/{BLOCK}/argue", held, escalate)
    assert seen == seen | ONE_MOVE


@needs_browser
def test_an_open_held_page_shows_upheld_by_when_the_uphold_arrives(
    story: Story, console: str
) -> None:
    story.drop_receipt(UPHOLD)
    uphold = append(story.receipts, UPHOLD_LINE)
    seen = watch(f"{console}/verdict/{BLOCK}/held", UPHELD, uphold)
    assert seen == ONE_MOVE | {"headline": "A person upheld the decision."}


@needs_browser
def test_reduced_motion_changes_the_held_page_without_a_move(
    story: Story, console: str
) -> None:
    story.drop_receipt(UPHOLD)
    uphold = append(story.receipts, UPHOLD_LINE)
    seen = watch(f"{console}/verdict/{BLOCK}/held", UPHELD, uphold, reduced=True)
    assert seen["kept"] and seen["moves"] == 0
