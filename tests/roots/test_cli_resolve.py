import io
from pathlib import Path

import pytest
from knack import cli
from knack.contracts.models import Verdict
from knack.miss.cases import EditCase
from knack.miss.provisional import save_provisional
from knack.receipts.chain import append_receipt, guard_receipt, load_receipts, Receipt
from knack.roots.corrections import Correction
from knack.walk.registry import home_registry_dir
from registry_fixture import make_registry, raw_entries, root

NOW = "2026-10-31T09:00:00+00:00"


class Stdin(io.StringIO):
    # A stand-in stdin that is, or is not, an interactive terminal.
    def __init__(self, tty: bool) -> None:
        super().__init__()
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    # A person at a terminal, unless a test says otherwise.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("KNACK_HOME", raising=False)
    monkeypatch.delenv("KNACK_HUMAN", raising=False)
    monkeypatch.setattr("sys.stdin", Stdin(tty=True))
    return tmp_path / "home"


def no_terminal(monkeypatch: pytest.MonkeyPatch, human: str | None) -> None:
    # An agent's shell: stdin is a pipe; KNACK_HUMAN only if given.
    monkeypatch.setattr("sys.stdin", Stdin(tty=False))
    if human is not None:
        monkeypatch.setenv("KNACK_HUMAN", human)


REFUSED = (
    "knack resolve: only a person can resolve a deny: run it in an interactive"
    " terminal, or pass --by <your name> with KNACK_HUMAN=1 set by you"
)


@pytest.mark.parametrize(
    ("human", "by"), [(None, ["--by", "maria"]), ("1", []), ("0", ["--by", "maria"])]
)
def test_resolve_without_a_terminal_is_refused_and_writes_nothing(
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    human: str | None,
    by: list[str],
) -> None:
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    no_terminal(monkeypatch, human)
    args = ["resolve", deny.hash, "allow", "--reason", "ok", *by]
    assert cli.main([*args, "--registry", str(registry)]) == 2
    assert REFUSED in capsys.readouterr().err
    assert not (home / ".knack" / "corrections.jsonl").exists()
    assert load_receipts(home / ".knack" / "verdicts.jsonl") == [deny]


def test_resolve_without_a_terminal_runs_with_by_and_knack_human(
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    no_terminal(monkeypatch, "1")
    args = ["resolve", deny.hash, "allow", "--reason", "ok", "--by", "maria"]
    assert cli.main([*args, "--registry", str(registry)]) == 0
    assert f"{deny.hash[:12]}: allowed by maria" in capsys.readouterr().out


def denied(home: Path) -> Receipt:
    deny = Verdict.model_validate(
        {"allowed": False, "reason": "blocked", "latency_ms": 2.0}
        | {"rule_id": "widgets-3", "root_ids": ["widgets-3-1"]}
    )
    named = ("acme/widgets", "/w/a.py", "widgets-3", root("widgets-3-1", "Confirmed"))
    path = home / ".knack" / "verdicts.jsonl"
    return append_receipt(path, guard_receipt(*named, deny, NOW, edit_sha256="e" * 64))


def logged(home: Path) -> list[Correction]:
    lines = (home / ".knack" / "corrections.jsonl").read_text().splitlines()
    return [Correction.model_validate_json(line) for line in lines]


def test_resolve_allow_logs_to_corrections_and_receipts(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    args = ["resolve", deny.hash, "allow", "--reason", "ok here", "--by", "maria"]
    assert cli.main([*args, "--registry", str(registry)]) == 0
    assert [(c.action, c.receipt_hash) for c in logged(home)] == [("allow", deny.hash)]
    assert load_receipts(home / ".knack" / "verdicts.jsonl")[-1].resolution is not None
    out = capsys.readouterr().out
    assert f"{deny.hash[:12]}: allowed by maria" in out and "widgets-3" in out


def test_resolve_retire_drops_the_rule(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    args = ["resolve", deny.hash, "retire", "--reason", "superseded", "--by", "bo"]
    assert cli.main([*args, "--registry", str(registry)]) == 0
    assert "3" not in raw_entries(registry)
    assert "retired by bo" in capsys.readouterr().out


def test_resolve_defaults_to_the_home_registry_of_the_receipt_repo(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_registry(home_registry_dir("acme/widgets"))
    deny = denied(home)
    args = ["resolve", deny.hash, "allow", "--reason", "ok", "--by", "maria"]
    assert cli.main(args) == 0


def test_resolve_of_an_unknown_hash_is_operator_error(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = make_registry(tmp_path / "reg")
    args = ["resolve", "0" * 64, "allow", "--reason", "ok", "--registry", str(registry)]
    assert cli.main(args) == 2
    assert "knack resolve: no receipt" in capsys.readouterr().err


def test_resolve_without_a_registry_is_operator_error(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deny = denied(home)
    assert cli.main(["resolve", deny.hash, "allow", "--reason", "ok"]) == 2
    assert "knack resolve: no registry" in capsys.readouterr().err


def test_resolve_needs_an_action_and_a_reason(home: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["resolve", "a" * 64, "keep", "--reason", "x"])
    assert raised.value.code == 2
    with pytest.raises(SystemExit):
        cli.main(["resolve", "a" * 64, "allow"])


def test_resolve_allow_names_the_promoted_must_pass_case(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    fields = {"kind": "must-pass", "rule_id": "widgets-3", "file": "a.py"}
    fields |= {"before": None, "after": "x = 2\n", "source": f"receipt {deny.hash}"}
    save_provisional(registry, deny.hash, EditCase.model_validate(fields))
    args = ["resolve", deny.hash, "allow", "--reason", "ok here", "--by", "maria"]
    assert cli.main([*args, "--registry", str(registry)]) == 0
    out = capsys.readouterr().out
    assert "provisional case is now must-pass" in out and "widgets-3" in out


def test_resolve_uphold_logs_and_prints_upheld(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    before = registry.read_text()
    args = ["resolve", deny.hash, "uphold", "--reason", "it stands", "--by", "maria"]
    assert cli.main([*args, "--registry", str(registry)]) == 0
    assert [(c.action, c.receipt_hash) for c in logged(home)] == [("uphold", deny.hash)]
    assert registry.read_text() == before
    out = capsys.readouterr().out
    assert (
        f"{deny.hash[:12]}: upheld by maria (widgets-3, widgets-3-1): it stands" in out
    )


def test_resolve_uphold_names_git_user_when_no_by(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def git_user(cwd: Path) -> str:
        return "git person"

    monkeypatch.setattr(cli, "reviewer_name", git_user)
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    args = ["resolve", deny.hash, "uphold", "--reason", "it stands"]
    assert cli.main([*args, "--registry", str(registry)]) == 0
    resolution = load_receipts(home / ".knack" / "verdicts.jsonl")[-1].resolution
    assert resolution is not None and resolution.by == "git person"


def test_resolve_uphold_names_the_held_case_it_closed(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry, deny = make_registry(tmp_path / "reg"), denied(home)
    fields = {"kind": "must-pass", "rule_id": "widgets-3", "file": "a.py"}
    fields |= {"before": None, "after": "x = 2\n", "source": f"receipt {deny.hash}"}
    save_provisional(registry, deny.hash, EditCase.model_validate(fields))
    args = ["resolve", deny.hash, "uphold", "--reason", "it stands", "--by", "maria"]
    assert cli.main([*args, "--registry", str(registry)]) == 0
    out = capsys.readouterr().out
    assert "held case closed, no case added for widgets-3" in out
    assert "must-pass" not in out
