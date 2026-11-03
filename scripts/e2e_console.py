"""e2e_console.sh's steps: the #75025 story through knack console, every page checked over HTTP.

WORK is the sandbox the shell made. Edits, argue and resolve run through one_story.py's steps,
so they are the real hook and the real CLI; this file only adds what the console must show.
Each action exits non-zero with one line saying what was wrong.
"""

import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from html import unescape
from pathlib import Path

import one_story
from knack.console.links import CONSOLE_HOST, CONSOLE_PORT, CONSOLE_URL

ROOT = Path(__file__).resolve().parents[1]
FAKES = ROOT / "scripts" / "one_story_fakes.py"
CLI = ["-c", "import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))"]
ROOT_ID = "airflow-75025-1"
BY = "knack e2e"
# Covered: the record answers it (HOLD). Uncovered: the quotes never mention it (escalate).
OBJECTIONS = {
    "covered": "Let me alias state and start_date onto DagRun.state and DagRun.start_date so the advertised names keep working.",
    "uncovered": "Airflow's REST API is documented and public; removing order_by values in a minor release may need a deprecation cycle first, which #75025 never discusses.",
}
REASON = "The decision stands: these two sort options never worked (they returned an error), so there was nothing to deprecate. Sort by last_run_state and last_run_start_date."
GAP = "not recorded"
WAIT_SECONDS = 30
# Each page: its path, text a reader must see, and markup it must carry.
PAGES: dict[str, tuple[str, list[str], list[str]]] = {
    "block": (
        "/verdict/{block}",
        [
            "Blocked",
            "This edit brings back what #75025 removed.",
            "Delete lines 135–136.",
            "decision confirmed",
        ],
        [],
    ),
    "argue": (
        "/verdict/{block}/argue",
        ["The agent objected. The record answered.", OBJECTIONS["covered"]],
        ['<h2 id="outcome" class="word">Hold</h2>'],
    ),
    "argue links held": (
        "/verdict/{block}/argue",
        ["A later objection was held for a person"],
        ['href="/verdict/{block}/held"'],
    ),
    "held": (
        "/verdict/{block}/held",
        ["A person upheld the decision.", f"Upheld by {BY}", REASON],
        [],
    ),
    "day": (
        "/",
        [f"Blocked an edit against {ROOT_ID}", f"Upheld by {BY}", REASON],
        ['data-events="/events"'],
    ),
}
# The sandbox has no GitHub token, so the day page has no pull requests to read.
NO_PULLS = "Pull requests not recorded"
NO_CONFIRMER = "Confirmer not recorded"


def fail(said: str) -> None:
    sys.exit(f"e2e_console: {said}")


def knack_command() -> list[str]:
    # Fake models unless the shell was told --live; the CLI is the real one either way.
    live = os.environ.get("E2E_MODELS") == "live"
    return [sys.executable, *CLI] if live else [sys.executable, str(FAKES)]


def port_free() -> None:
    with socket.socket() as probe:
        if probe.connect_ex((CONSOLE_HOST, CONSOLE_PORT)) == 0:
            fail(f"port {CONSOLE_PORT} is in use; close the other knack console")


def get(path: str) -> tuple[int, str]:
    request = urllib.request.Request(
        CONSOLE_URL + path, headers={"accept": "text/html"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as failed:
        return failed.code, ""


def answers(path: str) -> bool:
    try:
        return get(path)[0] == 200
    except OSError:
        return False


def up(work: Path, pid: int) -> None:
    # Our console, serving: it must still be alive, so a stranger on the port never counts.
    deadline = time.monotonic() + WAIT_SECONDS
    while alive(pid) and not answers("/static/tokens.css"):
        if time.monotonic() > deadline:
            fail(f"knack console did not answer within {WAIT_SECONDS} s")
        time.sleep(0.2)
    if not alive(pid):
        fail("knack console exited:\n" + console_log(work))


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def console_log(work: Path) -> str:
    return (work / "console.log").read_text(errors="replace")


def waits_for_denies() -> None:
    # / listens on /events with no block of its own, so live.js switches to any new deny.
    status, html = get("/")
    if status != 200 or 'data-events="/events"' not in html or "data-block=" in html:
        fail(f"/ (HTTP {status}) does not wait on /events for the next deny")


def listen(work: Path) -> None:
    # Connected before the edit; the first deny event names the block / switches to.
    stream = urllib.request.urlopen(CONSOLE_URL + "/events", timeout=WAIT_SECONDS)
    stream.readline()
    (work / "listening").touch()
    deadline = time.monotonic() + WAIT_SECONDS
    (work / "heard").write_text(denied(map(bytes.decode, stream), deadline))


def denied(lines: Iterable[str], deadline: float) -> str:
    # The data line after the first "event: deny"; keepalives never hold it past the deadline.
    found = iter(lines)
    for line in found:
        if time.monotonic() > deadline:
            return ""
        if line.strip() == "event: deny":
            return next(found).removeprefix("data: ").strip()
    return ""


def heard(work: Path) -> None:
    said = (work / "heard").read_text() if (work / "heard").exists() else ""
    block = one_story.block_receipt(work)["hash"]
    if said != block:
        fail(f"/events sent deny {said or 'nothing'}, the hook's receipt is {block}")


def deny_links_page(work: Path) -> None:
    # The deny Muse shows the agent names this block's console page.
    block = one_story.block_receipt(work)["hash"]
    said = [s["stdout"] for s in one_story.steps(work) if s["name"] == "block"]
    if f"{CONSOLE_URL}/verdict/{block}" not in said[-1]:
        fail("the deny does not link the block's console page")


def page(work: Path, name: str) -> None:
    block = one_story.block_receipt(work)["hash"]
    path = PAGES[name][0].format(block=block)
    status, html = get(path)
    if status != 200:
        fail(f"GET {path} answered {status}")
    shows(path, html, PAGES[name][1], [m.format(block=block) for m in PAGES[name][2]])
    no_false_gaps(path, page_text(html), honest_gaps(work, name))


def shows(path: str, html: str, texts: list[str], marks: list[str]) -> None:
    text = page_text(html)
    missing = [t for t in texts if t not in text] + [m for m in marks if m not in html]
    if missing:
        fail(f"GET {path} lacks {json.dumps(missing, ensure_ascii=False)}")


def page_text(html: str) -> str:
    # What a reader sees: tags dropped, entities decoded, whitespace collapsed.
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def no_false_gaps(path: str, text: str, honest: list[str]) -> None:
    # Every "not recorded" must be one this sandbox truly has no data for.
    for gap in honest:
        text = text.replace(gap, "", 1)
    if GAP in text:
        start = text.index(GAP)
        fail(f"GET {path} says '…{text[max(0, start - 60) : start + len(GAP)]}'")


def honest_gaps(work: Path, name: str) -> list[str]:
    # Only the day page lists decisions; one gap per installed Confirmed root with no confirmer.
    if name != "day":
        return []
    roots = (one_story.registry_dir(work) / "roots").glob("*.json")
    unconfirmed = [r for r in map(read_json, roots) if unnamed_confirmer(r)]
    return [NO_PULLS] + [NO_CONFIRMER] * len(unconfirmed)


def read_json(path: Path) -> dict[str, object]:
    found: dict[str, object] = json.loads(path.read_text())
    return found


def unnamed_confirmer(root: dict[str, object]) -> bool:
    return root.get("status") == "Confirmed" and not root.get("confirmed_by")


def argue(work: Path, which: str) -> None:
    command = [*knack_command(), "argue", OBJECTIONS[which]]
    exit_of(one_story.record(work, f"argue {which}", command, None))


def resolve(work: Path) -> None:
    block = one_story.block_receipt(work)["hash"]
    upheld = ["resolve", block, "uphold", "--reason", REASON, "--by", BY]
    exit_of(one_story.record(work, "resolve", [*knack_command(), *upheld], None))


def verify(work: Path) -> None:
    done = one_story.record(
        work, "verify", [*knack_command(), "receipts", "verify"], None
    )
    exit_of(done)
    if not done["stdout"].endswith("chain intact"):
        fail("the receipt chain is not intact")


def exit_of(step: dict[str, object]) -> None:
    if step["exit"] != 0:
        fail(f"{step['name']} exited {step['exit']}")


# e2e_console.py ACTION WORK [ARGS...]: each action and how it reads its arguments.
ACTIONS: dict[str, Callable[[Path, list[str]], None]] = {
    "free": lambda work, rest: port_free(),
    "up": lambda work, rest: up(work, int(rest[0])),
    "waits": lambda work, rest: waits_for_denies(),
    "listen": lambda work, rest: listen(work),
    "heard": lambda work, rest: heard(work),
    "linked": lambda work, rest: deny_links_page(work),
    "page": lambda work, rest: page(work, rest[0]),
    "argue": lambda work, rest: argue(work, rest[0]),
    "resolve": lambda work, rest: resolve(work),
    "verify": lambda work, rest: verify(work),
}


if __name__ == "__main__":
    ACTIONS[sys.argv[1]](Path(sys.argv[2]), sys.argv[3:])
