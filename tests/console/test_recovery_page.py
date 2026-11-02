import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from knack.console.app import create_app
from test_verdict_page import visible

REPO_ROOT = Path(__file__).parents[2]
# The KN-97 live self-repair run, frozen unchanged.
KEPT = REPO_ROOT / "mockups" / "fixtures" / "self_repair"
STATIC = REPO_ROOT / "knack" / "console" / "static"
RULE = "airflow-75025"
PAGE = f"/recovery/{RULE}"
HTML = {"accept": "text/html,application/xhtml+xml"}
PASS_LINE = re.compile(r"^PASS (.+?)(?: \(/[^)]*\))?$", re.M)
NOTE = "Started by a person; the unattended repair path has run only with fake models."


def lines(name: str) -> list[dict[str, Any]]:
    text = (KEPT / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in text]


def case(kind: str) -> dict[str, Any]:
    [found] = [json.loads(p.read_text()) for p in (KEPT / "cases").glob(f"{kind}-*")]
    return found


def step(name: str) -> str:
    [found] = (KEPT / "traces" / "steps").glob(f"*_{name}.txt")
    return found.read_text(encoding="utf-8")


def root(name: str) -> dict[str, Any]:
    return json.loads((KEPT / "rule" / f"root_{name}.json").read_text())


def branches(version: str) -> list[Any]:
    return yaml.safe_load((KEPT / "rule" / f"{version}.yml").read_text())["rule"]["any"]


def rule_receipts() -> list[dict[str, Any]]:
    return [r for r in lines("receipts.jsonl") if r["rule_id"] == RULE]


def code_at(kind: str, receipt: dict[str, Any]) -> str:
    # The case's line the receipt's first match names.
    return case(kind)["after"].splitlines()[receipt["matched"][0]["line"] - 1]


def client(repairs: Path | None = KEPT) -> TestClient:
    receipts = REPO_ROOT / "mockups" / "fixtures" / "one_story" / "receipts.jsonl"
    places = (receipts, receipts.with_name("warns.jsonl"), receipts.with_name("r"))
    return TestClient(create_app(*places, lambda repo: None, repairs=repairs))


@pytest.fixture(scope="module")
def html() -> str:
    page = client().get(PAGE, headers=HTML)
    assert page.status_code == 200
    return page.text


@pytest.fixture(scope="module")
def text(html: str) -> str:
    return visible(html)


def test_the_headline_says_knack_repaired_its_own_rule(html: str) -> None:
    assert "<h1>Knack repaired its own rule.</h1>" in html


def test_the_six_steps_come_in_order(html: str) -> None:
    steps = re.findall(
        r"<li class=\"step\"[^>]*>(?:<div[^>]*>)?<h2[^>]*>(.*?)</h2>", html
    )
    assert len(steps) == 6, steps
    assert steps[0].startswith("An edit slipped past the rule")
    assert steps[-1].startswith("The same evasion is now denied")


def test_every_receipt_of_the_rule_is_named_in_order(text: str) -> None:
    # Allowed evasion, denied correct file, then denied evasion, allowed file, allowed fix.
    found = [r["hash"][:8] for r in rule_receipts()]
    at = [text.index(short) for short in found]
    assert len(found) == 5 and at == sorted(at)
    assert [r["decision"] for r in rule_receipts()] == [
        "allow",
        "deny",
        "deny",
        "allow",
        "allow",
    ]


def test_the_evasion_line_is_read_from_the_must_fail_case(text: str) -> None:
    denied_later = rule_receipts()[2]
    assert " ".join(code_at("must-fail", denied_later).split()) in text


def test_the_correct_file_is_on_paper_as_the_proof(html: str) -> None:
    proof = re.search(r'<figure class="proof paper".*?</figure>', html, re.S)
    assert proof, "no paper proof"
    shown = visible(proof.group(0))
    assert "compliant_3.py" in shown
    assert code_at("must-pass", rule_receipts()[1]) in shown


def test_the_counts_kept_dropped_and_added_come_from_the_two_rules(text: str) -> None:
    v1, v2 = branches("v1"), branches("v2")
    kept = sum(b in v2 for b in v1)
    counts = (kept, len(v1) - kept, sum(b not in v1 for b in v2))
    assert counts == (6, 1, 5)
    assert "Kept 6 checks that were still right, dropped 1, added 5." in text


def test_the_dropped_and_added_checks_are_said_plainly(text: str) -> None:
    assert "Dropped: a dict comprehension" in text
    for said in ("a dict entry", "a keyword argument", "a tuple"):
        assert said in text
    for pattern in ("dict($$$, state=DagRun.state, $$$)",):
        assert pattern in text


def test_every_gate_line_is_shown_verbatim(text: str) -> None:
    gates = PASS_LINE.findall(step("knack_false_block"))
    assert len(gates) == 6
    for gate in gates:
        assert gate in text, gate


def test_both_confirm_attempts_are_shown_honestly(text: str) -> None:
    first = step("knack_confirm").splitlines()
    [why] = [line.strip() for line in first if "no longer extracted" in line]
    # Backticked spans render as code, as the block page renders a quote's.
    shown = " ".join(why.replace("`", "").split())
    assert "rolled back by the regression gate" in text and shown in text
    assert "exit 1" in text
    assert "passed, pinned to rule 865e1a983ffe" in text
    assert f"by {lines('corrections.jsonl')[0]['by']}" in text


def test_every_model_is_named_exactly_with_its_host_and_trace(text: str) -> None:
    for call in lines("models.jsonl"):
        for field in ("model", "host", "trace_id"):
            assert call[field] in text, call[field]


def test_the_rail_shows_v1_to_v2_by_sha(html: str) -> None:
    rail = visible(html[html.index('<aside class="rail"') :])
    before, after = root("before")["rule_sha"], root("after")["rule_sha"]
    assert f"v1 {before[:12]} → v2 {after[:12]}" in rail


def test_the_rail_says_who_did_the_work(html: str) -> None:
    rail = visible(html[html.index('<aside class="rail"') :])
    for who in ("Spark", "Spark Open", "Plain code", "A person", NOTE):
        assert who in rail, who


def test_the_chain_is_verified_and_counted(text: str) -> None:
    assert f"{len(lines('receipts.jsonl'))} receipts, chain intact" in text


def test_an_unknown_rule_is_404() -> None:
    assert client().get("/recovery/airflow-99999", headers=HTML).status_code == 404
    assert client().get("/recovery/airflow-99999").status_code == 404


def test_without_a_kept_repair_every_rule_is_404() -> None:
    assert client(None).get(PAGE, headers=HTML).status_code == 404


def test_a_missing_confirm_is_a_gap_not_an_invention(tmp_path: Path) -> None:
    shutil.copytree(KEPT, tmp_path / "kept")
    (tmp_path / "kept" / "corrections.jsonl").write_text("")
    page = client(tmp_path / "kept").get(PAGE, headers=HTML)
    assert page.status_code == 200
    assert "Confirmer not recorded" in visible(page.text)


def test_a_broken_chain_is_said(tmp_path: Path) -> None:
    shutil.copytree(KEPT, tmp_path / "kept")
    receipts = tmp_path / "kept" / "receipts.jsonl"
    kept = receipts.read_text().splitlines()
    receipts.write_text("\n".join(kept[:3] + kept[4:]) + "\n")
    text = visible(client(tmp_path / "kept").get(PAGE, headers=HTML).text)
    assert "chain intact" not in text and "chain broken at line 4" in text


def test_the_timeline_fills_once_and_reduced_motion_is_the_final_frame(
    html: str,
) -> None:
    script = (STATIC / "recovery.js").read_text()
    assert "/static/recovery.js" in html and "/static/recovery.css" in html
    assert "prefers-reduced-motion" in script and "iterations" not in script
    assert "data-fill" in html


def day_html(tmp_path: Path, repairs: Path | None) -> str:
    from test_day_page import DayConsole

    world = DayConsole(tmp_path)
    base = world.receipts.parent
    places = (world.receipts, base / "warns.jsonl", base / "rulings.jsonl")
    app = create_app(*places, world.registry_for, world.day(), repairs=repairs)
    return TestClient(app).get("/", headers=HTML).text


def decision_note(html: str, pr: str) -> str:
    notes = re.findall(r'<li class="decision paper">.*?</li>', html, re.S)
    [found] = [note for note in notes if f">{pr}<" in note]
    return found


def test_the_day_pages_75025_note_links_to_its_recovery(tmp_path: Path) -> None:
    note = decision_note(day_html(tmp_path, KEPT), "#75025")
    assert f'<a href="{PAGE}">' in note
    assert "repaired" in visible(note).lower()


def test_without_a_kept_repair_the_day_page_links_no_recovery(tmp_path: Path) -> None:
    assert "/recovery/" not in day_html(tmp_path, None)
