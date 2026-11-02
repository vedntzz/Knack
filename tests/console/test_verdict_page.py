import json
import shutil
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from knack.console.app import create_app

REPO_ROOT = Path(__file__).parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "console_75025"
DATA_REGISTRY = REPO_ROOT / "data" / "registry" / "airflow.json"
DATA_ROOTS = REPO_ROOT / "data" / "roots" / "airflow"
# The real deny run 3 earned in scripts/demo_block.sh, and the allow chained before it.
DENY = "08a2c39bcceddafae995781163b6e8ea17ab0f02c2cb4e48a65bf3cc3a097f3c"
ALLOW = "03ccc97742f581b00662229cd2103dbdeb30af4d5b8f85a6c544faa8b9f5a728"
# Pushkal Gupta's whole paragraph in #75025, as the root records it, backticks rendered.
QUOTE = (
    "I removed them rather than aliasing them onto DagRun.state and DagRun.start_date. "
    "The last_run_* spelling predates the refactor and already works, so a second name "
    "for the same sort felt worse than one. Happy to alias instead if you would rather "
    "keep the advertised names working."
)
HEADLINE = "This edit brings back what #75025 removed."
HTML = {"accept": "text/html,application/xhtml+xml"}
Entry = dict[str, Any]


class TextOf(HTMLParser):
    # Visible text only: script and style bodies are skipped.
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.skip += tag in ("script", "style")

    def handle_endtag(self, tag: str) -> None:
        self.skip -= tag in ("script", "style")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def visible(html: str) -> str:
    parser = TextOf()
    parser.feed(html)
    return " ".join("".join(parser.parts).split())


def unchanged(entry: Entry) -> Entry:
    return entry


def without_proof(entry: Entry) -> Entry:
    return {key: value for key, value in entry.items() if key != "proof"}


class Console:
    # The fixture's receipts and edit snapshot, and a copy of the airflow registry.
    def __init__(self, base: Path) -> None:
        shutil.copytree(FIXTURE, base / "knack")
        self.receipts = base / "knack" / "verdicts.jsonl"
        self.roots = base / "roots"
        shutil.copytree(DATA_ROOTS, self.roots)
        self.registry = base / "registry.json"
        self.write_registry(unchanged)

    def write_registry(self, change: Callable[[Entry], Entry]) -> None:
        data = json.loads(DATA_REGISTRY.read_text())
        rules = [self.absolute(entry) for entry in data["rules"]]
        body = data | {"roots_dir": str(self.roots), "rules": list(map(change, rules))}
        self.registry.write_text(json.dumps(body))

    def absolute(self, entry: dict[str, Any]) -> dict[str, Any]:
        return entry | {"rule": str((DATA_REGISTRY.parent / entry["rule"]).resolve())}

    def drop_root_field(self, field: str) -> None:
        path = self.roots / "75025.json"
        root = json.loads(path.read_text())
        path.write_text(json.dumps({k: v for k, v in root.items() if k != field}))

    def client(self) -> TestClient:
        base = self.receipts.parent
        places = (self.receipts, base / "warns.jsonl", base / "rulings.jsonl")
        return TestClient(create_app(*places, lambda repo: self.registry))

    def page(self, receipt: str = DENY) -> str:
        response = self.client().get(f"/verdict/{receipt}", headers=HTML)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        return response.text


@pytest.fixture
def console(tmp_path: Path) -> Console:
    return Console(tmp_path)


def test_the_75025_page_says_what_stopped_why_who_and_what_next(
    console: Console,
) -> None:
    text = visible(console.page())
    assert "Blocked" in text and HEADLINE in text
    assert QUOTE in text
    for said in ("Pushkal Gupta", "merged by bbovenzi", "Oct 19 2026", "#75025"):
        assert said in text
    assert "Delete lines 135–136." in text
    assert "Lines 137–138 already use the right names." in text


def test_the_75025_page_shows_the_proof_figures_from_the_rules_record(
    console: Console,
) -> None:
    text = visible(console.page())
    assert "8/8 checks passed" in text
    assert "0 false alarms on Airflow’s code and release 3.3.2" in text
    assert "17.3 ms to decide, no AI model in the check" in text


def test_the_verify_row_names_the_receipt_rule_and_command_in_plain_words(
    console: Console,
) -> None:
    text = visible(console.page())
    assert f"Receipt {DENY[:8]}" in text and DENY not in text
    assert f"knack receipts verify --path {console.receipts}" in text
    assert "Rule airflow-75025 · decision confirmed" in text
    assert "root" not in text.lower().split() and "seeded" not in text


def test_the_verify_row_copies_the_full_hash_and_the_command(console: Console) -> None:
    html = console.page()
    assert f'data-copy-text="{DENY}"' in html
    assert f'data-copy-text="knack receipts verify --path {console.receipts}"' in html


def test_a_seeded_root_says_so_in_the_verify_row(console: Console) -> None:
    path = console.roots / "75025.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | {"seeded": True}))
    assert "decision confirmed, seeded" in visible(console.page())


def test_the_note_links_to_the_pr(console: Console) -> None:
    html = console.page()
    assert 'href="https://github.com/apache/airflow/pull/75025"' in html
    text = visible(html)
    rejected = "Alias state and start_date onto DagRun.state and DagRun.start_date."
    assert rejected in text


def test_the_page_shows_the_agents_lines_with_the_note_between_them(
    console: Console,
) -> None:
    text = visible(console.page())
    forbidden = text.index('"start_date": DagRun.start_date,')
    note, correct = text.index(QUOTE), text.index('"last_run_state": DagRun.state,')
    assert forbidden < note < correct


def test_a_long_comment_is_shown_whole_with_the_correct_lines_below_it(
    console: Console,
) -> None:
    path = console.roots / "75025.json"
    long = " ".join(f"Sentence {n} of the reviewer’s long comment." for n in range(40))
    path.write_text(json.dumps(json.loads(path.read_text()) | {"quote": long}))
    text = visible(console.page())
    assert f"“{long}”" in text
    assert text.index(long) < text.index('"last_run_state": DagRun.state,')


def test_the_note_is_never_clipped_by_height_or_line_count() -> None:
    css = (REPO_ROOT / "knack" / "console" / "static" / "console.css").read_text()
    note_rules = [line for line in css.splitlines() if line.startswith(".note")]
    assert not any(
        c in rule
        for rule in note_rules
        for c in ("max-height", "line-clamp", "overflow: hidden")
    )


def test_a_missing_merge_date_is_a_labelled_gap(console: Console) -> None:
    console.drop_root_field("merged_at")
    text = visible(console.page())
    assert "Merge date not recorded" in text
    assert "Oct 19 2026" not in text


def test_a_missing_edit_snapshot_is_a_labelled_gap(console: Console) -> None:
    shutil.rmtree(console.receipts.parent / "edits")
    text = visible(console.page())
    assert "Delete lines 135–136." in text
    assert "Lines with the right names not recorded" in text
    assert "The agent’s edit not recorded" in text


def test_a_missing_proof_is_a_labelled_gap(console: Console) -> None:
    console.write_registry(without_proof)
    text = visible(console.page())
    assert "Checks not recorded" in text
    assert "False alarms not recorded" in text
    assert "8/8" not in text


def test_an_unknown_hash_is_a_404_page(console: Console) -> None:
    response = console.client().get(f"/verdict/{'0' * 64}", headers=HTML)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")


def test_json_is_still_served_to_clients_that_do_not_ask_for_html(
    console: Console,
) -> None:
    response = console.client().get(f"/verdict/{DENY}")
    assert response.headers["content-type"] == "application/json"
    assert response.json()["root"]["quote"].startswith("I removed them")


def test_root_text_is_escaped_never_run(console: Console) -> None:
    path = console.roots / "75025.json"
    root = json.loads(path.read_text())
    path.write_text(json.dumps(root | {"decided_by": "<script>x()</script>"}))
    html = console.page()
    assert "<script>x()" not in html
    assert "&lt;script&gt;x()" in html


def test_an_allow_is_never_shown_as_blocked(console: Console) -> None:
    text = visible(console.page(ALLOW))
    assert "Blocked" not in text
    assert "Allowed" in text
