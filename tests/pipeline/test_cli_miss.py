import argparse
import json
from pathlib import Path

import pytest
from conftest import (
    BASE,
    clean_tree,
    FakeAdversary,
    FakeGitHub,
    FakeSpark,
    HELDOUT,
    STRUCTURAL,
    VARIANTS,
)
from knack import cli
from knack.pipeline.ports import GitHub, Spark
from test_miss_loop import heldout, registry, RULE_ID
from test_prove import EDIT_ADDS, MEMORIZED_ON_BASE


def fake_clients(tmp_path: Path, compiled: str) -> tuple[GitHub, Spark, Spark]:
    github = FakeGitHub(clean_tree(tmp_path))
    return github, FakeSpark([compiled]), FakeAdversary(VARIANTS, HELDOUT)


def edit_json(tmp_path: Path) -> Path:
    path = tmp_path / "edit.json"
    body = {"rule_id": RULE_ID, "file": "pkg/loader.py", "before": BASE}
    path.write_text(json.dumps(body | {"after": BASE + EDIT_ADDS}))
    return path


def miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, compiled: str, *extra: str
) -> int:
    clients = fake_clients(tmp_path, compiled)

    def loop_clients(args: argparse.Namespace) -> tuple[GitHub, Spark, Spark]:
        return clients

    monkeypatch.setattr(cli, "_loop_clients", loop_clients)
    reg, held = registry(tmp_path, MEMORIZED_ON_BASE), heldout(tmp_path)
    args = [
        "--registry",
        str(reg),
        "--heldout",
        str(held),
        "--work",
        str(tmp_path / "w"),
    ]
    return cli.main([*extra, *args])


def test_knack_miss_installs_the_recompiled_rule_and_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = miss(tmp_path, monkeypatch, STRUCTURAL, "miss", str(edit_json(tmp_path)))
    out = capsys.readouterr().out
    assert code == 0 and f"installed {RULE_ID}" in out
    assert "PASS held-out cross" in out


def test_knack_miss_keeps_the_old_rule_and_exits_1_when_a_gate_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = miss(
        tmp_path, monkeypatch, MEMORIZED_ON_BASE, "miss", str(edit_json(tmp_path))
    )
    out = capsys.readouterr().out
    assert code == 1 and f"kept the old {RULE_ID}" in out
    assert "FAIL cases: guard edit pkg/loader.py [" in out


def test_knack_miss_with_an_unreadable_source_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = miss(tmp_path, monkeypatch, STRUCTURAL, "miss", "no-such-run")
    assert code == 2 and "knack miss:" in capsys.readouterr().err


def test_knack_false_block_refuses_an_edit_with_no_receipt_and_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    receipts = ["--receipts", str(tmp_path / "verdicts.jsonl")]
    code = miss(tmp_path, monkeypatch, STRUCTURAL, "false-block", "c" * 64, *receipts)
    assert code == 2 and "knack false-block: no receipt" in capsys.readouterr().err
