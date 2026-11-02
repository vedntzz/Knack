import os
from pathlib import Path

import pytest
from conftest import (
    clean_tree,
    EXTRACTIONS,
    FakeGitHub,
    FakeSpark,
    merge_pr,
    STRUCTURAL,
)
from knack.home import knack_home
from knack.pipeline import clients
from knack.pipeline.clients import MissingCredentials, optional_partner
from knack.watch.credentials import KEY_FILES, watch_key
from test_corroborate import FakeSparkOpen
from test_watch_hook import post_merge, repo as repo  # noqa: F401

# Fake values, registered as placeholders in tests/test_no_secrets.py.
FILE_KEYS = {
    "GITHUB_TOKEN": "fake-watch-file-token-7d1e",
    "MODEL_API_KEY": "fake-watch-file-model-5b2f",
    "BASETEN_API_KEY": "fake-watch-file-open-8c4a",
}
ENV_KEY = "fake-watch-env-key-3a9c"
NAMES = sorted(FILE_KEYS)


@pytest.fixture(autouse=True)
def no_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)


def key_file(name: str, mode: int = 0o600, text: str | None = None) -> Path:
    path = knack_home() / KEY_FILES[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FILE_KEYS[name] + "\n" if text is None else text, "utf-8")
    os.chmod(path, mode)
    return path


def refusal(name: str) -> str:
    with pytest.raises(MissingCredentials) as caught:
        watch_key(name)
    return str(caught.value)


def test_each_key_has_its_own_file() -> None:
    files = [KEY_FILES[name] for name in NAMES]
    assert files == ["baseten_api_key", "github_token", "model_api_key"]


@pytest.mark.parametrize("name", NAMES)
def test_the_env_wins_over_the_file(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, ENV_KEY)
    key_file(name)
    assert watch_key(name) == ENV_KEY


@pytest.mark.parametrize("name", NAMES)
def test_without_the_env_the_file_is_read(name: str) -> None:
    key_file(name)
    assert watch_key(name) == FILE_KEYS[name]


@pytest.mark.parametrize("name", NAMES)
def test_an_empty_env_falls_back_to_the_file(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(name, "")
    key_file(name)
    assert watch_key(name) == FILE_KEYS[name]


@pytest.mark.parametrize("name", NAMES)
def test_the_files_default_to_dot_knack_in_home(
    monkeypatch: pytest.MonkeyPatch, isolated_home: Path, name: str
) -> None:
    monkeypatch.delenv("KNACK_HOME", raising=False)
    assert key_file(name).parent == isolated_home / ".knack"
    assert watch_key(name) == FILE_KEYS[name]


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o666])
@pytest.mark.parametrize("name", NAMES)
def test_a_file_others_can_read_is_refused_with_chmod_600(name: str, mode: int) -> None:
    path = key_file(name, mode)
    message = refusal(name)
    assert f"chmod 600 {path}" in message and f"{mode:o}" in message
    assert FILE_KEYS[name] not in message


@pytest.mark.parametrize("name", NAMES)
def test_with_neither_the_message_names_both_places(name: str) -> None:
    message = refusal(name)
    assert f"{name} is not set" in message and "chmod 600" in message
    assert str(knack_home() / KEY_FILES[name]) in message


@pytest.mark.parametrize("name", NAMES)
def test_an_empty_file_is_refused(name: str) -> None:
    key_file(name, text="\n")
    assert "is empty" in refusal(name)


def test_a_missing_spark_open_key_is_no_partner() -> None:
    assert optional_partner(key=watch_key) is None


def test_an_open_spark_open_file_is_refused_not_skipped() -> None:
    key_file("BASETEN_API_KEY", 0o644)
    with pytest.raises(MissingCredentials, match="chmod 600"):
        optional_partner(key=watch_key)


@pytest.mark.parametrize("name", NAMES)
def test_an_open_file_stops_the_hook_and_leaves_the_merge_pending(
    repo: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
) -> None:
    for each in NAMES:
        key_file(each, 0o644 if each == name else 0o600)
    monkeypatch.chdir(repo)
    merge_pr(repo)
    assert post_merge(repo) == 0
    err = capsys.readouterr().err
    assert err.startswith("knack watch: ") and f"chmod 600 {knack_home()}" in err
    assert all(value not in err for value in FILE_KEYS.values())


def recording(seen: list[str], client: object) -> object:
    # A client constructor that records the key it was given.
    def build(key: str) -> object:
        seen.append(key)
        return client

    return build


def fake_services(repo: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    # GitHub, Spark and Spark Open faked; each records the key it was built with.
    seen: list[str] = []
    github = FakeGitHub(clean_tree(repo.parent))
    spark_open = FakeSparkOpen({**EXTRACTIONS})
    monkeypatch.setattr(clients, "GitHubApi", recording(seen, github))
    spark = ("MODEL_API_KEY", recording(seen, FakeSpark([STRUCTURAL])))
    monkeypatch.setitem(clients.EXTRACTORS, "spark", spark)
    open_ = ("BASETEN_API_KEY", recording(seen, spark_open))
    monkeypatch.setitem(clients.EXTRACTORS, "spark-open", open_)
    return seen


def file_key_run(repo: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    # The real hook clients, every key only in its file.
    seen = fake_services(repo, monkeypatch)
    for name in NAMES:
        key_file(name)
    monkeypatch.chdir(repo)
    merge_pr(repo)
    assert post_merge(repo) == 0
    return seen


def files_holding(root: Path, secret: str) -> list[Path]:
    # Every file under root, receipts, traces and work folders included, that holds secret.
    files = [path for path in root.rglob("*") if path.is_file()]
    return [path for path in files if secret.encode() in path.read_bytes()]


def test_the_hook_runs_on_file_keys_and_never_writes_them_out(
    repo: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen = file_key_run(repo, monkeypatch)
    out, err = capsys.readouterr()
    assert set(seen) == set(FILE_KEYS.values()) and "[5/5] install" in out
    assert "Spark Open did not run" not in out
    for name, value in FILE_KEYS.items():
        assert value not in out + err
        # HOME, and so KNACK_HOME, sits in the test's folder; only the key's file holds it.
        assert files_holding(repo.parent, value) == [knack_home() / KEY_FILES[name]]
