"""Freeze README.md's repo URL and install block into readme.json and readme.js, verbatim, with their line numbers."""

import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
# The one shell block under "## Get it running": the clone and install steps.
GET_IT_RUNNING = re.compile(r"^## Get it running\n.*?^```sh\n(.*?)^```", re.M | re.S)
CLONE_URL = re.compile(r"^git clone (\S+)$", re.M)


def found(pattern: re.Pattern[str], text: str) -> str:
    # The first group of pattern in text; a missing source line stops the freeze.
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"not in README.md: {pattern.pattern}")
    return match.group(1)


def line_of(readme: str, text: str) -> int:
    # 1-based line number of the first README line equal to text.
    return readme.splitlines().index(text) + 1


def readme_values(readme: str) -> dict[str, Any]:
    install = found(GET_IT_RUNNING, readme).rstrip("\n")
    first, last = install.splitlines()[0], install.splitlines()[-1]
    lines = {"repo": line_of(readme, first), "install": [line_of(readme, first), line_of(readme, last)]}
    return {"repo": found(CLONE_URL, install), "install": install, "lines": lines}


def main() -> None:
    frozen = json.dumps(readme_values((REPO / "README.md").read_text()), indent=2, ensure_ascii=False)
    (OUT / "readme.json").write_text(frozen + "\n")
    (OUT / "readme.js").write_text(f"// Frozen by freeze_readme.py from README.md; see mockups/landing/SOURCES.md.\nwindow.README = {frozen};\n")


if __name__ == "__main__":
    main()
