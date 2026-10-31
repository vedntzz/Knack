import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from knack import cli
from knack.contracts.models import Root
from knack.guard.pr_comment import (
    comment_body,
    comment_on_block,
    pull_request_from_env,
    PullRequest,
    review_payload,
)
from review_api_fake import FakeReviewApi, serving

REPO = Path(__file__).parents[2]
RULE = REPO / "knack/guard/rules/no-alias-sort-keys.yml"
ROOT_JSON = REPO / "tests/guard/fixtures/replay/root_75025.json"
VIOLATING = Path("tests/guard/fixtures/replay/run3_public_dags.py")
FIXED = Path("tests/guard/fixtures/fixed.py")
ROOT = Root.model_validate_json(ROOT_JSON.read_text(encoding="utf-8"))
SCRIPT = REPO / ".github/scripts/guard_changed.sh"
WORKFLOW = REPO / ".github/workflows/knack-guard.yml"
KNACK = Path(sys.executable).parent / "knack"


@pytest.fixture
def github() -> Iterator[FakeReviewApi]:
    with serving() as fake:
        yield fake


def pr_env(api: str) -> dict[str, str]:
    # What the knack-guard workflow puts in the guard step's environment.
    return {
        "GITHUB_TOKEN": "t0ken",
        "GITHUB_REPOSITORY": "apache/airflow",
        "PR_NUMBER": "7",
        "HEAD_SHA": "abc123",
        "GITHUB_API_URL": api,
    }


def closed_port_url() -> str:
    # A port nothing listens on: every request is refused.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{probe.getsockname()[1]}"


def comment(github: FakeReviewApi, file: Path, log: Path) -> int:
    return comment_on_block(file, RULE, ROOT_JSON, pr_env(github.url), log)


def test_body_carries_decision_decider_quote_and_link() -> None:
    body = comment_body(ROOT)
    assert f"**Decision:** {ROOT.decision}" in body
    assert f"**Decided by:** {ROOT.decided_by}" in body
    assert f"> {ROOT.quote}" in body
    assert str(ROOT.source_url) in body


def test_a_multi_line_quote_stays_verbatim_line_by_line() -> None:
    root = ROOT.model_copy(update={"quote": "first `a`\n\n*second*"})
    assert "> first `a`\n> \n> *second*" in comment_body(root)


def test_env_without_any_one_value_gives_no_pull_request() -> None:
    for name in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "PR_NUMBER", "HEAD_SHA"):
        env = pr_env("http://x") | {name: ""}
        assert pull_request_from_env(env) is None


def test_env_defaults_to_the_public_api() -> None:
    env = pr_env("") | {"GITHUB_API_URL": ""}
    assert pull_request_from_env(env) == PullRequest(
        "https://api.github.com", "apache/airflow", "7", "abc123", "t0ken"
    )


def test_payload_targets_the_line_on_the_head_commit() -> None:
    pr = PullRequest("https://api.github.com", "apache/airflow", "7", "abc123", "t")
    payload = review_payload(pr, Path("a/b.py"), 25, "body")
    fields = ("path", "line", "side", "commit_id", "body")
    expected = ("a/b.py", 25, "RIGHT", "abc123", "body")
    assert tuple(payload[name] for name in fields) == expected


def test_a_block_comments_once_on_each_offending_line(
    github: FakeReviewApi, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO)
    assert comment(github, VIOLATING, tmp_path / "log") == 3
    assert [r["json"]["line"] for r in github.requests] == [25, 28, 29]
    first, endpoint = github.requests[0], "/repos/apache/airflow/pulls/7/comments"
    assert (first["path"], first["auth"]) == (endpoint, "Bearer t0ken")
    sent = (first["json"]["path"], first["json"]["body"])
    assert sent == (str(VIOLATING), comment_body(ROOT))


def test_an_allowed_file_posts_nothing(
    github: FakeReviewApi, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO)
    assert comment(github, FIXED, tmp_path / "log") == 0
    assert github.requests == []


def test_a_rejected_comment_is_reported_not_raised(
    github: FakeReviewApi,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(REPO)
    github.status = 403
    assert comment(github, VIOLATING, tmp_path / "log") == 0
    err = capsys.readouterr().err
    assert "403" in err and "t0ken" not in err


def test_an_unreachable_api_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(REPO)
    env = pr_env(closed_port_url())
    assert comment_on_block(VIOLATING, RULE, ROOT_JSON, env, tmp_path / "log") == 0
    assert "not posted" in capsys.readouterr().err


def test_cli_comment_exits_zero_when_github_refuses(
    github: FakeReviewApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO)
    github.status = 500
    for name, value in pr_env(github.url).items():
        monkeypatch.setenv(name, value)
    argv = ["guard", "comment", str(VIOLATING), "--rule", str(RULE)]
    assert cli.main([*argv, "--root", str(ROOT_JSON)]) == 0
    assert len(github.requests) == 3


def test_cli_comment_without_a_token_exits_zero_and_says_why(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(REPO)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    argv = ["guard", "comment", str(VIOLATING), "--rule", str(RULE)]
    assert cli.main([*argv, "--root", str(ROOT_JSON)]) == 0
    assert "GITHUB_TOKEN" in capsys.readouterr().err


def test_cli_comment_with_a_broken_root_exits_zero(
    github: FakeReviewApi,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(REPO)
    for name, value in pr_env(github.url).items():
        monkeypatch.setenv(name, value)
    (tmp_path / "root.json").write_text("{not json")
    argv = ["guard", "comment", str(VIOLATING), "--rule", str(RULE)]
    assert cli.main([*argv, "--root", str(tmp_path / "root.json")]) == 0
    assert github.requests == [] and "knack guard comment" in capsys.readouterr().err


def run_script(api: str, *files: Path) -> subprocess.CompletedProcess[str]:
    # The CI loop as the workflow runs it, with the PR environment set.
    args = ["bash", str(SCRIPT), str(RULE), str(ROOT_JSON), *map(str, files)]
    env = {**os.environ, "KNACK": str(KNACK), **pr_env(api)}
    return subprocess.run(
        args, capture_output=True, text=True, timeout=60, cwd=REPO, env=env
    )


def test_ci_block_posts_review_comments_and_still_fails(github: FakeReviewApi) -> None:
    done = run_script(github.url, FIXED, VIOLATING)
    assert done.returncode == 1
    assert {r["json"]["path"] for r in github.requests} == {str(VIOLATING)}


def test_ci_allow_posts_nothing(github: FakeReviewApi) -> None:
    assert run_script(github.url, FIXED).returncode == 0
    assert github.requests == []


def test_ci_failed_comment_never_changes_the_job_result(
    github: FakeReviewApi,
) -> None:
    github.status = 500
    assert run_script(github.url, VIOLATING).returncode == 1
    assert run_script(closed_port_url(), VIOLATING).returncode == 1
    assert run_script(github.url, FIXED).returncode == 0


def test_workflow_hands_the_guard_step_the_token_it_needs() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull-requests: write" in text
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in text
    assert "PR_NUMBER: ${{ github.event.pull_request.number }}" in text
    assert "HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in text
