import json
from pathlib import Path
from typing import Any

from knack.contracts.models import Root, WalkResponse
from knack.guard.check import log_error_quietly
from knack.hooks.scope import home_error_log, scoped_quietly
from knack.index.cache import repo_index
from knack.roots.store import load_roots
from knack.walk.registry import Registry
from knack.walk.walk import walk

JsonDict = dict[str, Any]


def run_hook(stdin_text: str) -> JsonDict | None:
    # Silent unless the event cwd is a clone of the registry's repo.
    event = json.loads(stdin_text)
    scoped = scoped_quietly(event)
    if scoped is None:
        return None
    return _warn(event, *scoped)


def _warn(event: JsonDict, registry: Registry, repo_root: Path) -> JsonDict | None:
    # Walk failures hit the home log; the prompt is never blocked.
    try:
        response = _walk_prompt(event, registry, repo_root)
    except Exception as error:
        log_error_quietly(home_error_log(), error)
        return None
    return _envelope(_confirmed_text(response))


def _walk_prompt(event: JsonDict, registry: Registry, repo_root: Path) -> WalkResponse:
    # The prompt is the ticket; the index comes from the git root, not the cwd.
    prompt = str(event.get("prompt", ""))
    index = repo_index(repo_root, registry.repo)
    return walk(prompt, index, registry.rules, load_roots(registry.roots_dir))


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
