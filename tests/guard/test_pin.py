import hashlib
from pathlib import Path

import pytest
from knack.contracts.models import Root
from knack.guard import check
from knack.guard.check import check_file
from knack.roots.pin import pin_holds, rule_sha
from test_check_file import FIXTURES, make_confirmed_root, raise_error, RULE, RULE_ID


def pinned(sha: str | None, status: str = "Confirmed") -> Root:
    update = {"rule_sha": sha, "status": status, "confirmed_by": "maria"}
    return make_confirmed_root().model_copy(update=update)


def test_rule_sha_is_the_sha256_of_the_rule_file() -> None:
    assert rule_sha(RULE) == hashlib.sha256(RULE.read_bytes()).hexdigest()


def test_a_root_pinned_to_the_installed_rule_still_denies(tmp_path: Path) -> None:
    root = pinned(rule_sha(RULE))
    verdict = check_file(FIXTURES / "pre_fix.py", RULE, RULE_ID, root, tmp_path / "log")
    assert verdict.allowed is False


def test_a_recompiled_rule_advises_until_reconfirmed(tmp_path: Path) -> None:
    recompiled = tmp_path / "rule.yml"
    recompiled.write_text(RULE.read_text() + "# recompiled\n")
    root = pinned(rule_sha(RULE))
    verdict = check_file(
        FIXTURES / "pre_fix.py", recompiled, RULE_ID, root, tmp_path / "log"
    )
    assert verdict.allowed is True and verdict.matched
    assert verdict.reason.startswith("advisory: Confirmed root, rule changed since")
    assert "knack confirm root-001" in verdict.reason
    assert verdict.root_ids == ["root-001"]


def test_a_root_confirmed_before_pins_still_denies(tmp_path: Path) -> None:
    # Roots confirmed before KN-62 carry no pin; they keep blocking until re-confirmed.
    root = pinned(None)
    verdict = check_file(FIXTURES / "pre_fix.py", RULE, RULE_ID, root, tmp_path / "log")
    assert verdict.allowed is False


def test_an_unreadable_rule_pin_fails_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(check, "pin_holds", raise_error(OSError("gone")))
    root = pinned(rule_sha(RULE))
    verdict = check_file(FIXTURES / "pre_fix.py", RULE, RULE_ID, root, tmp_path / "log")
    assert verdict.allowed is True and verdict.reason.startswith("guard-error")


@pytest.mark.parametrize("status", ["Inferred", "Corroborated", "Unknown"])
def test_only_confirmed_roots_are_pinned_checks(status: str) -> None:
    assert pin_holds(pinned("0" * 64, status), RULE) is True


def test_root_files_without_pins_still_load() -> None:
    root = make_confirmed_root()
    assert (root.rule_sha, root.confirmed_by) == (None, None)
