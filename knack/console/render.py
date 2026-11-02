from pathlib import Path
from string import Template

from fastapi import Request

TEMPLATES = Path(__file__).parent / "templates"
# The verdict page's assets: the two faces it shows first, and its three scripts.
PRELOAD = "".join(
    f'<link rel="preload" href="/static/fonts/{face}.woff2" as="font" type="font/woff2" crossorigin>\n'
    for face in ("ibm-plex-serif-400-normal", "ibm-plex-sans-600-normal")
)
LIVE = '<script type="module" src="/static/live.js"></script>\n'
SCRIPTS = LIVE + "".join(
    f'<script type="module" src="/static/{name}.js"></script>\n'
    for name in ("motion", "console")
)
TURNS = "".join(
    f'<script type="module" src="/static/{name}.js"></script>\n'
    for name in ("turns", "console")
)
EVENTS = ' data-events="/events"'
# Every base.html slot a page may leave out.
UNSET = {
    "preload": "",
    "styles": "",
    "scripts": "",
    "events": "",
    "bar": "",
    "verify": "",
}


def render(name: str, **slots: str) -> str:
    return Template((TEMPLATES / name).read_text(encoding="utf-8")).substitute(slots)


def partial(name: str, **slots: str) -> str:
    return render(f"partials/{name}", **slots).rstrip("\n")


def page(name: str, title: str, **slots: str) -> str:
    # Every page is base.html around its own template; base names the page's layout.
    content = render(name, **slots)
    frame = {"layout": "quiet", "state": "waiting"} | UNSET | slots
    return render("base.html", **frame, title=title, content=content)


def waiting_html() -> str:
    return page("waiting.html", "Waiting · knack", scripts=LIVE, events=EVENTS)


NO_RECEIPT_SAID = "No receipt with that hash."
NO_RULING_SAID = "No ruling on that receipt."


def missing_html(said: str = NO_RECEIPT_SAID) -> str:
    return page("missing.html", f"{said[:-1]} · knack", said=said)


def wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")
