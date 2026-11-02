import json
from pathlib import Path

from knack.hooks.pretool_guard import OPEN_CONSOLE, rerun_deny
from knack.walk.registry import load_registry

REPO_ROOT = Path(__file__).parents[2]
FROZEN = REPO_ROOT / "mockups" / "fixtures" / "one_story"
RECEIPTS = FROZEN / "receipts.jsonl"
REGISTRY = REPO_ROOT / "data" / "registry" / "airflow.json"
ROOT_75025 = REPO_ROOT / "data" / "roots" / "airflow" / "75025.json"
BLOCK = "0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9"
# The first receipt of the story: rule airflow-74150 allowed the same edit.
ALLOW = "5636f0a41b5949d75e3267078cd96dcb60ad03a9ebb77bddca5fef33e7db58da"


def rerun_reason(receipt_hash: str, log: Path) -> str | None:
    found = rerun_deny(RECEIPTS, receipt_hash, load_registry(REGISTRY), log)
    return (
        None
        if found is None
        else found["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_rerun_of_the_block_quotes_the_full_root_and_links_its_own_receipt(
    tmp_path: Path,
) -> None:
    reason = rerun_reason(BLOCK[:12], tmp_path / "errors.log") or ""
    quote = json.loads(ROOT_75025.read_text())["quote"]
    assert f'Quote: "{quote}"' in reason.splitlines()
    assert f"Console: http://127.0.0.1:7655/verdict/{BLOCK} {OPEN_CONSOLE}" in reason
    assert not (tmp_path / "errors.log").exists()


def test_rerun_of_the_block_matches_the_live_run_but_for_the_console_hint(
    tmp_path: Path,
) -> None:
    story = json.loads((FROZEN / "story.json").read_text())
    live = json.loads(story["steps"][0]["stdout"])["hookSpecificOutput"]
    reason = rerun_reason(BLOCK, tmp_path / "errors.log") or ""
    assert reason.replace(f" {OPEN_CONSOLE}", "") == live["permissionDecisionReason"]


def test_rerun_of_an_allow_receipt_has_no_deny(tmp_path: Path) -> None:
    assert rerun_reason(ALLOW, tmp_path / "errors.log") is None


def test_rerun_of_an_unknown_receipt_has_no_deny(tmp_path: Path) -> None:
    assert rerun_reason("f" * 64, tmp_path / "errors.log") is None
