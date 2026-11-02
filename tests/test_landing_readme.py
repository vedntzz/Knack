"""The landing mockup's repo URL and install command are README.md's, verbatim, with cited lines."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
README = REPO_ROOT / "README.md"
FIXTURE = REPO_ROOT / "mockups" / "fixtures" / "readme.json"
FIXTURE_JS = REPO_ROOT / "mockups" / "fixtures" / "readme.js"
LANDING = REPO_ROOT / "mockups" / "landing"
# The one shell block under "## Get it running": the clone and install steps.
GET_IT_RUNNING = re.compile(r"^## Get it running\n.*?^```sh\n(.*?)^```", re.M | re.S)
CLONE_URL = re.compile(r"^git clone (\S+)$", re.M)


def install_block() -> str:
    return GET_IT_RUNNING.search(README.read_text()).group(1).rstrip("\n")


def readme_line(text: str) -> int:
    # 1-based line number of the first README line equal to text.
    return README.read_text().splitlines().index(text) + 1


def frozen() -> dict:
    return json.loads(FIXTURE.read_text())


def test_install_is_readme_get_it_running_block_verbatim():
    assert frozen()["install"] == install_block()


def test_repo_is_readme_clone_url_verbatim():
    assert frozen()["repo"] == CLONE_URL.search(install_block()).group(1)


def test_fixture_cites_the_readme_lines_it_copied():
    lines = install_block().splitlines()
    first, last = readme_line(lines[0]), readme_line(lines[-1])
    assert frozen()["lines"] == {"repo": first, "install": [first, last]}


def test_readme_js_is_the_same_values():
    prefix = "window.README = "
    body = FIXTURE_JS.read_text().split(prefix, 1)[1].rstrip().removesuffix(";")
    assert json.loads(body) == frozen()


def test_sources_md_cites_both_readme_lines():
    lines, sources = frozen()["lines"], (LANDING / "SOURCES.md").read_text()
    assert f"README.md line {lines['repo']}" in sources
    assert f"README.md lines {lines['install'][0]}–{lines['install'][1]}" in sources


def test_landing_loads_and_reads_both_values():
    page, script = (LANDING / "index.html").read_text(), (LANDING / "landing.js").read_text()
    assert '<script src="../fixtures/readme.js"></script>' in page
    assert "R.repo" in script and "R.install" in script
