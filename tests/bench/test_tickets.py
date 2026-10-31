import json
from pathlib import Path
from typing import Any

import pytest
from knack.bench.tickets import BenchTicket, key_terms, load_tickets, TicketError
from knack.contracts.models import Root
from knack.roots.store import write_root
from knack.walk.registry import home_registry_dir, Registry, RegistryEntry
from pydantic import ValidationError

REPO_ROOT = Path(__file__).parents[2]
REAL_TICKETS = REPO_ROOT / "bench" / "tickets.jsonl"
REPO = "acme/widgets"
SHA = "8b5306690acb58d0584376272dfa2159aecea0dd"
DECISION = "Read each blob one at a time with a bounded loop"
REJECTED = "asyncio.gather over every blob at once"
PROBLEM = "Loading a large bucket exhausts file descriptors and the worker dies."


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def root(root_id: str, rejected: str | None = REJECTED) -> Root:
    url = "https://github.com/acme/widgets/pull/9"
    fields: dict[str, Any] = {"id": root_id, "title": "t", "source_url": url}
    fields |= {"decision": DECISION, "why": "w", "decided_by": "maria"}
    fields |= {"quote": "q", "status": "Inferred", "rejected_alternative": rejected}
    return Root.model_validate(fields)


def install_registry(roots: list[Root], rule_id: str = "widgets-9") -> None:
    # A home registry with one rule enforcing every given root.
    out = home_registry_dir(REPO)
    for each in roots:
        write_root(each, out / "roots" / f"{each.id}.json")
    (out / "rules").mkdir(parents=True)
    (out / "rules" / "9.yml").write_text(f"id: {rule_id}\nlanguage: python\n")
    entry = RegistryEntry(rule=Path("rules/9.yml"), root_ids=[r.id for r in roots])
    registry = Registry(repo=REPO, roots_dir=Path("roots"), rules=[entry])
    (out / "registry.json").write_text(registry.model_dump_json())


def ticket(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"id": "widgets-9", "repo": REPO, "pr": 9}
    fields |= {"base_sha": SHA, "files": ["src/load.py"], "rule": "widgets-9"}
    fields |= {"fix_functions": ["Loader.read_all", "_open_blob"]}
    return fields | {"ticket": PROBLEM} | overrides


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def test_bench_ticket_is_frozen() -> None:
    made = BenchTicket.model_validate(ticket())
    with pytest.raises(ValidationError):
        made.ticket = "changed"  # type: ignore[misc]


def test_bench_ticket_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        BenchTicket.model_validate(ticket(fix="use a loop"))


def test_bench_ticket_rejects_short_sha() -> None:
    with pytest.raises(ValidationError):
        BenchTicket.model_validate(ticket(base_sha="8b53066"))


def test_bench_ticket_rejects_no_files() -> None:
    with pytest.raises(ValidationError):
        BenchTicket.model_validate(ticket(files=[]))


def test_key_terms_drop_words_the_decision_shares() -> None:
    # "blob", "every", "once" ... only words naming the rejected path remain.
    assert key_terms(root("widgets-9-1")) == {
        "asyncio",
        "gather",
        "over",
        "every",
        "once",
    }


def test_key_terms_split_identifiers() -> None:
    made = root("widgets-9-1", rejected="Alias onto DagRun.start_date")
    assert {"alias", "onto", "dag", "run", "start", "date"} <= key_terms(made)


def test_key_terms_empty_without_rejected_alternative() -> None:
    assert key_terms(root("widgets-9-1", rejected=None)) == set()


def test_load_tickets_reads_every_line(home: Path, tmp_path: Path) -> None:
    install_registry([root("widgets-9-1")])
    rows = [ticket(), ticket(id="widgets-9b")]
    loaded = load_tickets(write_jsonl(tmp_path / "t.jsonl", rows))
    assert [t.id for t in loaded] == ["widgets-9", "widgets-9b"]


def test_load_tickets_rejects_missing_field(home: Path, tmp_path: Path) -> None:
    install_registry([root("widgets-9-1")])
    row = {k: v for k, v in ticket().items() if k != "base_sha"}
    with pytest.raises(TicketError, match="line 1.*base_sha"):
        load_tickets(write_jsonl(tmp_path / "t.jsonl", [row]))


def test_bench_ticket_requires_fix_functions() -> None:
    with pytest.raises(ValidationError):
        BenchTicket.model_validate(ticket(fix_functions=[]))


def test_load_tickets_rejects_function_the_fix_touches(
    home: Path, tmp_path: Path
) -> None:
    install_registry([root("widgets-9-1")])
    leaky = ticket(ticket="Calling Loader.read_all on a large bucket kills the worker.")
    with pytest.raises(TicketError, match="widgets-9.*read_all"):
        load_tickets(write_jsonl(tmp_path / "t.jsonl", [leaky]))


def test_load_tickets_allows_prose_near_a_function_name(
    home: Path, tmp_path: Path
) -> None:
    install_registry([root("widgets-9-1")])
    plain = ticket(ticket="The worker dies when it reads all files of a bucket.")
    assert load_tickets(write_jsonl(tmp_path / "t.jsonl", [plain]))


def test_load_tickets_rejects_private_name(home: Path, tmp_path: Path) -> None:
    # A user filing a bug never sees private helpers; naming one is mechanism.
    install_registry([root("widgets-9-1")])
    leaky = ticket(ticket="The worker dies inside _split_chunks on a large bucket.")
    with pytest.raises(TicketError, match="widgets-9.*_split_chunks"):
        load_tickets(write_jsonl(tmp_path / "t.jsonl", [leaky]))


def test_load_tickets_rejects_duplicate_ids(home: Path, tmp_path: Path) -> None:
    install_registry([root("widgets-9-1")])
    path = write_jsonl(tmp_path / "t.jsonl", [ticket(), ticket()])
    with pytest.raises(TicketError, match="duplicate ticket ids.*widgets-9"):
        load_tickets(path)


def test_load_tickets_rejects_leaked_term(home: Path, tmp_path: Path) -> None:
    install_registry([root("widgets-9-1")])
    leaky = ticket(ticket="Loading is slow; maybe use asyncio.Gather.")
    with pytest.raises(TicketError, match="widgets-9.*asyncio.*gather"):
        load_tickets(write_jsonl(tmp_path / "t.jsonl", [leaky]))


def test_load_tickets_checks_every_root_of_the_rule(home: Path, tmp_path: Path) -> None:
    install_registry([root("widgets-9-1"), root("widgets-9-2", rejected="threads")])
    leaky = ticket(ticket="Loading a bucket from many threads dies.")
    with pytest.raises(TicketError, match="threads"):
        load_tickets(write_jsonl(tmp_path / "t.jsonl", [leaky]))


def test_key_terms_fall_back_when_the_decision_names_the_alternative() -> None:
    # "Read sequentially instead of (fake) parallel" repeats every rejected word.
    made = root("widgets-9-1", rejected="read each blob")
    assert key_terms(made) == {"read", "each", "blob"}


def test_load_tickets_rejects_rule_without_key_terms(
    home: Path, tmp_path: Path
) -> None:
    # A rule whose roots name no rejected alternative cannot guard the text.
    install_registry([root("widgets-9-1", rejected=None)])
    with pytest.raises(TicketError, match="widgets-9.*no key terms"):
        load_tickets(write_jsonl(tmp_path / "t.jsonl", [ticket()]))


def test_load_tickets_rejects_unregistered_rule(home: Path, tmp_path: Path) -> None:
    install_registry([root("widgets-9-1")])
    path = write_jsonl(tmp_path / "t.jsonl", [ticket(rule="widgets-404")])
    with pytest.raises(TicketError, match="widgets-404"):
        load_tickets(path)


def test_load_tickets_rejects_repo_without_registry(home: Path, tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "t.jsonl", [ticket()])
    with pytest.raises(TicketError, match="acme/widgets"):
        load_tickets(path)


# Rules that passed KN-28's cross-model held-out (spikes/heldout_cross_run.log).
CROSS_MODEL_PASSED = {
    "airflow-75271",
    "airflow-75774",
    "fastapi-14884",
    "fastapi-15139",
    "fastapi-15515",
    "fastapi-16049",
    "fastapi-16062",
}
# KN-35e: #75025 (passes a fresh cross-model set) and #15937 (the contrast beat, fails it).
KN35E_ADDED = {"airflow-75025", "fastapi-15937"}
BENCH_REPOS = ["apache/airflow", "fastapi/fastapi"]


@pytest.mark.skipif(
    not all((home_registry_dir(r) / "registry.json").exists() for r in BENCH_REPOS),
    reason="needs the airflow and fastapi home registries from knack import",
)
def test_real_tickets_are_the_preregistered_nine() -> None:
    expected = CROSS_MODEL_PASSED | KN35E_ADDED
    assert {t.rule for t in load_tickets(REAL_TICKETS)} == expected
