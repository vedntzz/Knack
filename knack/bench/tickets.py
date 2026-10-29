import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError

from knack.contracts.models import NonEmptyStr, Root
from knack.roots.store import load_roots
from knack.walk.registry import (
    home_registry_dir,
    load_registry,
    Registry,
    RegistryEntry,
)

# Splits prose and identifiers alike: DagRun.start_date -> Dag, Run, start, date.
WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")
MIN_TERM_LENGTH = 3
STOPWORDS = frozenset(
    {"the", "and", "for", "with", "that", "this", "from", "into", "its", "not"}
)
FULL_SHA = r"^[0-9a-f]{40}$"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class TicketError(Exception):
    pass


class BenchTicket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: NonEmptyStr
    repo: NonEmptyStr
    pr: PositiveInt
    base_sha: str = Field(pattern=FULL_SHA)
    files: list[NonEmptyStr] = Field(min_length=1)
    rule: NonEmptyStr
    # What the merged fix changed, as Class.method; checked, never shown to the agent.
    fix_functions: list[NonEmptyStr] = Field(min_length=1)
    # The problem only, never the fix.
    ticket: NonEmptyStr


def terms(text: str) -> set[str]:
    words = {word.lower() for word in WORD.findall(text)}
    return {w for w in words if len(w) >= MIN_TERM_LENGTH and w not in STOPWORDS}


def key_terms(root: Root) -> set[str]:
    # Words naming the rejected path, minus the decision's; all of them if none remain.
    if root.rejected_alternative is None:
        return set()
    rejected = terms(root.rejected_alternative)
    return (rejected - terms(root.decision)) or rejected


def load_tickets(path: Path) -> list[BenchTicket]:
    lines = path.read_text(encoding="utf-8").splitlines()
    tickets = [_parse_line(n, line) for n, line in enumerate(lines, 1) if line.strip()]
    _reject_duplicate_ids(tickets)
    for each in tickets:
        _reject_leaked_terms(each, _rule_key_terms(each))
        _reject_internal_names(each)
    return tickets


def _parse_line(number: int, line: str) -> BenchTicket:
    try:
        return BenchTicket.model_validate_json(line)
    except ValidationError as error:
        raise TicketError(f"line {number}: {_describe(error)}") from error


def _describe(error: ValidationError) -> str:
    # One line per bad field, e.g. "base_sha: Field required".
    return "; ".join(
        f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()
    )


def _reject_duplicate_ids(tickets: list[BenchTicket]) -> None:
    ids = [ticket.id for ticket in tickets]
    duplicates = sorted({ticket_id for ticket_id in ids if ids.count(ticket_id) > 1})
    if duplicates:
        raise TicketError(f"duplicate ticket ids: {duplicates}")


def _rule_key_terms(ticket: BenchTicket) -> set[str]:
    # Every root the rule enforces adds its key terms; none at all cannot guard.
    found = set[str]().union(*(key_terms(root) for root in _rule_roots(ticket)))
    if not found:
        raise TicketError(f"{ticket.id}: rule {ticket.rule} has no key terms")
    return found


def _rule_roots(ticket: BenchTicket) -> list[Root]:
    registry = _registry_for(ticket.repo)
    entry = _entry_for(registry, ticket)
    by_id = {root.id: root for root in load_roots(registry.roots_dir)}
    return [by_id[root_id] for root_id in entry.root_ids]


def _registry_for(repo: str) -> Registry:
    path = home_registry_dir(repo) / "registry.json"
    if not path.exists():
        raise TicketError(f"no home registry for {repo} at {path}; run knack init")
    return load_registry(path)


def _entry_for(registry: Registry, ticket: BenchTicket) -> RegistryEntry:
    for entry in registry.rules:
        if _rule_file_id(entry.rule) == ticket.rule:
            return entry
    raise TicketError(
        f"{ticket.id}: rule {ticket.rule} is not in the {ticket.repo} registry"
    )


def _rule_file_id(path: Path) -> str | None:
    # ast-grep names a rule by its top-level id line, not its file name.
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("id:"):
            return line.split(":", 1)[1].strip()
    return None


def _reject_leaked_terms(ticket: BenchTicket, forbidden: set[str]) -> None:
    leaked = sorted(terms(ticket.ticket) & forbidden)
    if leaked:
        raise TicketError(
            f"{ticket.id}: ticket names the rejected alternative: {leaked}"
        )


def _reject_internal_names(ticket: BenchTicket) -> None:
    # A bug report names no function the fix touches and no private helper.
    touched = {name.rsplit(".", 1)[-1] for name in ticket.fix_functions}
    named = set(IDENTIFIER.findall(ticket.ticket))
    internal = sorted(n for n in named if n in touched or n.startswith("_"))
    if internal:
        raise TicketError(f"{ticket.id}: ticket names internal code: {internal}")
