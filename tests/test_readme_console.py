import json
import os
import re
import signal
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from html import unescape
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).parents[1]
README = REPO_ROOT / "README.md"
VENV_BIN = REPO_ROOT / ".venv" / "bin"
CONSOLE_HEADING = "## See it in the console"
SETUP_HEADING = "## Get it running"
CONSOLE = "http://127.0.0.1:7655"
BLOCK_PAGE = f"{CONSOLE}/verdict/0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9"
ARGUE_PAGE = f"{BLOCK_PAGE}/argue"
HELD_PAGE = f"{BLOCK_PAGE}/held"
ONE_STORY = REPO_ROOT / "mockups" / "fixtures" / "one_story"
ROOT_75025 = REPO_ROOT / "data" / "roots" / "airflow" / "75025.json"
LINK = re.compile(r"http://127\.0\.0\.1:7655/\S*?(?=[)`>\s]|$)", re.M)
# Inherited settings the README command must not lean on.
DROPPED_ENV = ("KNACK_HOME", "KNACK_REGISTRY", "KNACK_CONSOLE_RECEIPTS", "GITHUB_TOKEN")


def section(heading: str) -> str:
    # The README text from heading to the next level-two heading.
    text = README.read_text(encoding="utf-8")
    start = text.index(f"\n{heading}\n") + 1
    end = text.find("\n## ", start + len(heading))
    return text[start : end if end != -1 else len(text)]


def first_sh_block(text: str) -> str:
    start = text.index("```sh\n") + len("```sh\n")
    return text[start : text.index("\n```", start)]


def console_command() -> str:
    [command] = first_sh_block(section(CONSOLE_HEADING)).splitlines()
    return command


def console_links() -> list[str]:
    return LINK.findall(section(CONSOLE_HEADING))


def fresh_env(home: Path) -> dict[str, str]:
    # A stranger's shell: a HOME with no ~/.knack and the venv active.
    env = {k: v for k, v in os.environ.items() if k not in DROPPED_ENV}
    path = f"{VENV_BIN}{os.pathsep}{env.get('PATH', '')}"
    return env | {"HOME": str(home), "PATH": path, "VIRTUAL_ENV": str(VENV_BIN.parent)}


def get(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as failed:
        return failed.code, ""


def answers(url: str) -> bool:
    try:
        return get(url)[0] == 200
    except OSError:
        return False


def wait_until_up(server: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and server.poll() is None:
        if answers(CONSOLE + "/static/tokens.css"):
            return
        time.sleep(0.2)
    raise AssertionError("knack console did not start as the README says")


def fresh_clone(into: Path) -> Path:
    # A clone of the committed HEAD: untracked fixtures are not in it.
    head = git("rev-parse", "HEAD").strip()
    git("clone", "--quiet", "--shared", "--no-checkout", str(REPO_ROOT), str(into))
    git("-C", str(into), "checkout", "--quiet", "--detach", head)
    return into


def git(*args: str) -> str:
    run = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else pytest.fail(run.stderr)


def start_console(clone: Path, home: Path) -> subprocess.Popen[bytes]:
    # Exactly the README's command, in the clone, in its own process group.
    quiet = subprocess.DEVNULL
    return subprocess.Popen(
        ["sh", "-c", console_command()],
        cwd=clone,
        env=fresh_env(home),
        stdout=quiet,
        stderr=quiet,
        start_new_session=True,
    )


def stop(server: subprocess.Popen[bytes]) -> None:
    # Only the process group this test started.
    os.killpg(server.pid, signal.SIGTERM)
    server.wait(timeout=10)


def fresh_console(scratch: Path) -> subprocess.Popen[bytes]:
    # The README's console in a fresh clone, with an empty HOME beside it.
    (scratch / "home").mkdir()
    return start_console(fresh_clone(scratch / "Knack"), scratch / "home")


@pytest.fixture
def readme_console(tmp_path: Path) -> Iterator[None]:
    # A fresh clone and an empty HOME: no ~/.knack, before or after.
    server = fresh_console(tmp_path)
    try:
        wait_until_up(server)
        yield
    finally:
        stop(server)
    assert not (tmp_path / "home" / ".knack").exists()


def page_text(html: str) -> str:
    # What a reader sees: tags dropped, entities decoded, whitespace collapsed.
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def full_quote() -> str:
    # The quote as the page shows it: backticked spans render as code.
    quote = json.loads(ROOT_75025.read_text(encoding="utf-8"))["quote"]
    return " ".join(quote.replace("`", " ").split())


def test_the_console_section_is_one_command_on_the_committed_receipts() -> None:
    command = console_command()
    assert "mockups/fixtures/one_story/receipts.jsonl" in command
    assert command.endswith("knack console")


def records(name: str) -> list[dict[str, Any]]:
    lines = (ONE_STORY / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def objection(decision: str) -> str:
    # The one-story objection Spark ruled on with this decision, as the page shows it.
    [found] = [r for r in records("rulings.jsonl") if r["decision"] == decision]
    return " ".join(found["objection"].split())


def upheld_by() -> str:
    resolved = [r["resolution"] for r in records("receipts.jsonl") if "resolution" in r]
    [uphold] = [r for r in resolved if r["action"] == "uphold"]
    return uphold["by"]


def test_the_console_section_links_the_block_argue_held_and_home() -> None:
    pages = {BLOCK_PAGE, ARGUE_PAGE, HELD_PAGE, CONSOLE + "/"}
    assert sorted(set(console_links())) == sorted(pages)


def test_the_deny_examples_console_link_is_a_page_the_section_serves() -> None:
    [denied] = re.findall(r"^Console: (\S+)", README.read_text(encoding="utf-8"), re.M)
    assert denied in console_links()


@pytest.mark.usefixtures("readme_console")
def test_every_console_link_is_served_from_a_fresh_home() -> None:
    statuses = {url: get(url)[0] for url in console_links()}
    assert statuses and set(statuses.values()) == {200}, statuses


@pytest.mark.usefixtures("readme_console")
def test_the_block_page_shows_the_full_75025_quote() -> None:
    status, html = get(BLOCK_PAGE)
    assert status == 200 and full_quote() in page_text(html)


@pytest.mark.usefixtures("readme_console")
def test_the_argue_page_shows_the_objection_spark_held() -> None:
    status, html = get(ARGUE_PAGE)
    assert status == 200 and objection("hold") in page_text(html)


@pytest.mark.usefixtures("readme_console")
def test_the_held_page_shows_the_escalated_objection_and_the_uphold() -> None:
    status, html = get(HELD_PAGE)
    text = page_text(html)
    assert status == 200 and objection("escalate") in text
    assert f"Upheld by {upheld_by()}" in text


def test_the_setup_block_ends_with_reproduce() -> None:
    setup = first_sh_block(section(SETUP_HEADING))
    assert setup.splitlines()[-1] == "bash scripts/reproduce.sh"


def test_setup_gives_reproduces_time_and_the_cold_install_caveat() -> None:
    text = " ".join(section(SETUP_HEADING).split())
    assert "about 70–80 s" in text
    assert "cold first install takes longer" in text and "Python 3.11" in text
