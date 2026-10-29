import json
import os
from pathlib import Path
from typing import Any

from knack.contracts.models import Root, WalkResponse
from knack.guard.check import log_error_quietly
from knack.hooks.pretool_guard import event_cwd
from knack.index.build import build_index
from knack.roots.store import load_roots
from knack.walk.registry import load_registry
from knack.walk.walk import walk

JsonDict = dict[str, Any]
REGISTRY_ENV = "KNACK_WALK_REGISTRY"
ROOTS_ENV = "KNACK_ROOTS_DIR"


def run_hook(stdin_text: str) -> JsonDict | None:
    # Bad stdin and missing env raise to the entry, which reports on stderr.
    event = json.loads(stdin_text)
    registry = _require_env(REGISTRY_ENV)
    roots_dir = _require_env(ROOTS_ENV)
    return _warn(event, registry, roots_dir)


def _error_log() -> Path:
    # Knack files stay in the user's home, never inside the walked repo.
    return Path.home() / ".knack" / "guard_errors.log"


def _warn(event: JsonDict, registry: Path, roots_dir: Path) -> JsonDict | None:
    # Walk failures hit the home log; the prompt is never blocked.
    base = event_cwd(event)
    try:
        response = _walk_prompt(event, base, registry, roots_dir)
    except Exception as error:
        log_error_quietly(_error_log(), error)
        return None
    return _envelope(_confirmed_text(response))


def _walk_prompt(
    event: JsonDict, base: Path, registry: Path, roots_dir: Path
) -> WalkResponse:
    # The prompt is the ticket; the event cwd is the repo being discussed.
    prompt = str(event.get("prompt", ""))
    index = build_index(base)
    entries = load_registry(registry)
    return walk(prompt, index, entries, load_roots(roots_dir))


def _require_env(name: str) -> Path:
    # A missing hook env is operator error: loud on stderr, silent on stdout.
    value = os.environ.get(name)
    if not value:
        raise FileNotFoundError(f"{name} is not set")
    return Path(value).expanduser().resolve()


def _envelope(text: str | None) -> JsonDict | None:
    # Silence injects nothing; a warning is the proven nested envelope.
    if text is None:
        return None
    inner = {"hookEventName": "UserPromptSubmit", "additionalContext": text}
    return {"hookSpecificOutput": inner}


def _confirmed_text(response: WalkResponse) -> str | None:
    # Confirmed leaves only; Inferred and Unknown never reach the prompt.
    roots = _confirmed_roots(response)
    if not roots:
        return None
    blocks = "\n".join(_root_block(root) for root in roots)
    return f"knack: Confirmed decision(s) touch this prompt:\n{blocks}"


def _confirmed_roots(response: WalkResponse) -> list[Root]:
    # Gathers the Confirmed roots behind Confirmed leaves, deduped by id.
    by_id = {root.id: root for root in response.roots}
    seen: dict[str, Root] = {}
    for leaf in response.leaves:
        if leaf.status == "Confirmed":
            for root_id in leaf.root_ids:
                _keep_confirmed(seen, by_id.get(root_id))
    return list(seen.values())


def _keep_confirmed(seen: dict[str, Root], root: Root | None) -> None:
    # Each Confirmed root is cited once, in first-seen order.
    if root is not None and root.status == "Confirmed":
        seen.setdefault(root.id, root)


def _root_block(root: Root) -> str:
    # Decision, rejected alternative, verbatim quote and source: full citation.
    rejected = root.rejected_alternative or "none recorded"
    head = f"- {root.id}: {root.decision}"
    alt = f"  Rejected alternative: {rejected}"
    return f'{head}\n{alt}\n  "{root.quote}" ({root.decided_by}, {root.source_url})'
