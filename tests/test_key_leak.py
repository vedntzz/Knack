import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
from knack.home import knack_home
from knack.hooks.scope import home_error_log
from knack.miss.cases import EditCase
from knack.miss.selfcheck import ask_judge, Asked, log_check
from knack.pipeline.clients import RefusedCredentials, required_env
from knack.pipeline.github import GitHubApi
from knack.pipeline.http import request_bytes
from knack.pipeline.spark_open import SparkOpenApi
from knack.watch import hook
from knack.watch.credentials import key_path, watch_key

# Built by concatenation so the secret scan never matches this file.
LINE_ONE = "dummy" + "-key-line-one"
LINE_TWO = "dummy" + "-key-line-two"
DUMMY_PARTS = (LINE_ONE, LINE_TWO)
KEY_NAMES = ("GITHUB_TOKEN", "MODEL_API_KEY", "BASETEN_API_KEY")
# A key with a second line, trailing junk after a space, a tab, or a control character.
BAD_KEYS = (
    LINE_ONE + "\n" + LINE_TWO + "\n",
    LINE_ONE + "\r\n" + LINE_TWO,
    LINE_ONE + " " + LINE_TWO,
    LINE_ONE + "\t" + LINE_TWO,
    LINE_ONE + "\x00" + LINE_TWO,
)
BAD_KEY_IDS = ("two-lines", "crlf", "space-junk", "tab-junk", "nul")
# The OS refuses a NUL in an env var, so env tests use the rest.
BAD_ENV_KEYS = BAD_KEYS[:-1]
BAD_ENV_IDS = BAD_KEY_IDS[:-1]


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # A header error must happen before any connection; a connect attempt fails loudly.
    def refuse(*_: Any, **__: Any) -> Any:
        raise AssertionError("a test tried to open a socket")

    monkeypatch.setattr(socket, "create_connection", refuse)
    for name in KEY_NAMES:
        monkeypatch.delenv(name, raising=False)


def write_key(name: str, value: str) -> Path:
    path = key_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    path.chmod(0o600)
    return path


def assert_no_dummy(text: str) -> None:
    for part in DUMMY_PARTS:
        assert part not in text


def assert_no_dummy_under(folder: Path) -> None:
    # Every file written under folder, read as bytes so nothing hides in an odd encoding.
    for path in folder.rglob("*"):
        if path.is_file() and path.name not in {k.lower() for k in KEY_NAMES}:
            assert_no_dummy(path.read_bytes().decode("utf-8", errors="replace"))


@pytest.mark.parametrize("value", BAD_KEYS, ids=BAD_KEY_IDS)
@pytest.mark.parametrize("name", KEY_NAMES)
def test_a_key_file_with_a_second_line_or_junk_is_refused_naming_only_the_file(
    name: str, value: str
) -> None:
    path = write_key(name, value)
    with pytest.raises(RefusedCredentials) as raised:
        watch_key(name)
    assert str(path) in str(raised.value)
    assert_no_dummy(str(raised.value))


def test_a_key_file_with_one_line_and_a_trailing_newline_is_read() -> None:
    write_key("GITHUB_TOKEN", LINE_ONE + "\n")
    assert watch_key("GITHUB_TOKEN") == LINE_ONE


@pytest.mark.parametrize("value", BAD_ENV_KEYS, ids=BAD_ENV_IDS)
def test_an_env_key_with_a_second_line_or_junk_is_refused_naming_only_the_var(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", value)
    with pytest.raises(RefusedCredentials) as raised:
        required_env("MODEL_API_KEY")
    assert "MODEL_API_KEY" in str(raised.value)
    assert_no_dummy(str(raised.value))


@pytest.mark.parametrize("value", BAD_ENV_KEYS, ids=BAD_ENV_IDS)
def test_a_bad_env_key_is_refused_before_its_file_is_read(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", value)
    with pytest.raises(RefusedCredentials) as raised:
        watch_key("GITHUB_TOKEN")
    assert_no_dummy(str(raised.value))


def test_watch_with_a_two_line_key_file_leaks_nothing_to_stderr_or_files(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in KEY_NAMES:
        write_key(name, BAD_KEYS[0])
    with pytest.raises(RefusedCredentials) as raised:
        hook._clients(False)()  # pyright: ignore[reportPrivateUsage]
    hook._report(raised.value, loud=True)  # pyright: ignore[reportPrivateUsage]
    captured = capsys.readouterr()
    assert str(key_path("GITHUB_TOKEN")) in captured.err
    assert_no_dummy(captured.out + captured.err)
    assert_no_dummy_under(knack_home())


def test_a_header_error_never_carries_the_header_value() -> None:
    headers = {"Authorization": "Bearer " + BAD_KEYS[0]}
    with pytest.raises(Exception) as raised:
        request_bytes("http://127.0.0.1:9/", headers)
    assert_no_dummy(str(raised.value) + repr(raised.value))
    assert raised.value.__cause__ is None and raised.value.__context__ is None


def test_a_github_header_error_reported_by_watch_leaks_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A key that slipped past the reader still never reaches stderr or the error log.
    client = GitHubApi(BAD_KEYS[0])
    with pytest.raises(Exception) as raised:
        client.summary("apache/airflow", 1)
    hook._report(raised.value, loud=True)  # pyright: ignore[reportPrivateUsage]
    captured = capsys.readouterr()
    assert_no_dummy(captured.out + captured.err)
    assert_no_dummy(home_error_log().read_text())


def test_a_judge_header_error_never_reaches_self_checks(tmp_path: Path) -> None:
    judge = SparkOpenApi(BAD_KEYS[0])
    answer = ask_judge(judge, "does it?", lambda text: True)
    assert answer.yes is False
    case = EditCase(
        kind="must-fail", rule_id="r-1", file="a.py", before=None, after="x", source="s"
    )
    checks = tmp_path / "self_checks.jsonl"
    log_check(checks, lambda line: None, case, Asked("watch", "q", [answer]))
    assert_no_dummy(checks.read_text())
    assert_no_dummy_under(tmp_path)


def test_self_checks_beside_a_committed_registry_are_gitignored() -> None:
    repo = Path(__file__).parents[1]
    target = "data/registry/self_checks.jsonl"
    done = subprocess.run(
        ["git", "check-ignore", "-q", target], cwd=repo, env=dict(os.environ)
    )
    assert done.returncode == 0, f"{target} is not gitignored"
