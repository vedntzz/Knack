import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
CONSOLE = REPO_ROOT / "knack" / "console"
STATIC = CONSOLE / "static"
TEMPLATES = CONSOLE / "templates"
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# A DESIGN.md palette row: | `--ground` | #0B0C0E | the page |
PALETTE_ROW = re.compile(r"^\| `(--[a-z-]+)` \| (#[0-9A-Fa-f]{6}) \|", re.M)
DECLARATION = re.compile(r"([a-z0-9-]+)\s*:\s*([^;{}]+);")
SPACING = re.compile(r"^(margin|padding)(-[a-z]+)?$|^((row|column)-)?gap$")
# DESIGN.md's 8-point scale, in px at 720p, where 1rem is 16px.
SCALE = (4, 8, 12, 16, 24, 32, 48, 64)
# Off-scale values kept so the refactor moves no pixel; a later visual ticket snaps them.
OFF_SCALE = {
    "--space-separator",
    "--space-paper",
    "--space-figure-column",
    "--space-quiet",
}
# Not raw spacing: the code column widths added up, so the note lines up with the code.
DERIVED = {"--code-indent"}
PARTIALS = {
    "note.html",
    "code.html",
    "fix.html",
    "figures.html",
    "verify.html",
    "said.html",
    "answered.html",
    "resolve.html",
    "resolved.html",
    "graph.html",
    "decision.html",
}
# Every stylesheet a page links; tokens.css is where the values live.
SHEETS = ("console.css", "day.css", "recovery.css")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def css(path: Path) -> str:
    # Without comments, whose colons would read as declarations.
    return re.sub(r"/\*.*?\*/", "", text(path), flags=re.S)


def tokens() -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in DECLARATION.findall(css(STATIC / "tokens.css"))
        if name.startswith("--")
    }


def spacing_values() -> list[str]:
    found = [d for sheet in SHEETS for d in DECLARATION.findall(css(STATIC / sheet))]
    return [
        part for prop, value in found if SPACING.match(prop) for part in value.split()
    ]


def imported(path: Path) -> set[str]:
    tree = ast.parse(text(path))
    found = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    return set(found) | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }


def test_no_raw_hex() -> None:
    # Every stylesheet but tokens.css reads colours only from tokens.
    sheets = [p for p in STATIC.glob("*.css") if p.name != "tokens.css"]
    assert sheets and [HEX.findall(text(p)) for p in sheets] == [[] for _ in sheets]


def test_every_variable_a_stylesheet_reads_is_a_token() -> None:
    for sheet in SHEETS:
        used = set(re.findall(r"var\((--[a-z0-9-]+)\)", text(STATIC / sheet)))
        assert used and used <= set(tokens()), sheet


def test_tokens_hold_every_colour_in_design_md() -> None:
    palette = dict(PALETTE_ROW.findall(text(REPO_ROOT / "DESIGN.md")))
    assert len(palette) == 12
    assert {name: tokens().get(name) for name in palette} == palette


def test_the_spacing_tokens_are_the_8_point_scale() -> None:
    space = {name for name in tokens() if name.startswith("--space-")}
    assert space - OFF_SCALE == {f"--space-{px}" for px in SCALE}
    for px in SCALE:
        assert tokens()[f"--space-{px}"] == f"{px / 16:g}rem"


def test_console_css_spaces_only_from_the_scale() -> None:
    allowed = {f"var(--space-{px})" for px in SCALE} | {"0", "auto"}
    allowed |= {f"var({name})" for name in OFF_SCALE | DERIVED}
    assert [value for value in spacing_values() if value not in allowed] == []


def test_every_page_is_built_from_base_and_the_partials() -> None:
    assert {p.name for p in (TEMPLATES / "partials").iterdir()} == PARTIALS
    for page in (
        "verdict.html",
        "argue.html",
        "held.html",
        "waiting.html",
        "missing.html",
        "day.html",
        "recovery.html",
    ):
        assert "<html" not in text(TEMPLATES / page)
    assert '<header class="bar">' in text(TEMPLATES / "base.html")


def test_the_block_page_is_its_own_router() -> None:
    assert "knack.console.pages.verdict" in imported(CONSOLE / "app.py")
    assert "APIRouter" in text(CONSOLE / "pages" / "verdict.py")
    assert not (CONSOLE / "page.py").exists()


def test_argue_held_and_recovery_are_their_own_routers() -> None:
    for name in ("argue", "held", "recovery"):
        assert f"knack.console.pages.{name}" in imported(CONSOLE / "app.py")
        assert "APIRouter" in text(CONSOLE / "pages" / f"{name}.py")


def test_facts_read_no_files() -> None:
    tree = ast.parse(text(CONSOLE / "facts.py"))
    names = {
        a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names
    }
    assert not {name for name in names if name.startswith("load_")}
    assert imported(CONSOLE / "facts.py") & {"pathlib", "os"} == set()


def test_the_listener_and_the_beats_left_console_js() -> None:
    assert "EventSource" in text(STATIC / "live.js")
    assert "prefers-reduced-motion" in text(STATIC / "motion.js")
    leftover = text(STATIC / "console.js")
    assert "EventSource" not in leftover and "BEATS" not in leftover
