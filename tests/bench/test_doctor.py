import json
import urllib.error
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from knack.bench.doctor import Check, doctor, DoctorKit, format_checks, run_doctor
from knack.cli import main as knack_main
from knack.contracts.models import Root
from knack.guard.runner import AST_GREP
from knack.pipeline.ports import Spark
from knack.roots.store import write_root
from knack.walk.registry import Registry, RegistryEntry

REPO = "acme/widgets"
SHA = "8b5306690acb58d0584376272dfa2159aecea0dd"
RULE = "id: widgets-9\nlanguage: python\nseverity: error\nmessage: m\nrule:\n  pattern: asyncio.gather($$$)\n"
BASE = {"src/loader.py": "import asyncio\n", "src/legacy.py": "import os\n"}
TICKET = {
    "id": "widgets-9",
    "repo": REPO,
    "pr": 9,
    "base_sha": SHA,
    "files": sorted(BASE),
    "rule": "widgets-9",
    "fix_functions": ["Loader.read_all_blobs"],
    "ticket": "Loading a large bucket exhausts file descriptors and the worker dies.",
}
ENV = {
    "GITHUB_TOKEN": "ghp-doctor-test-token",
    "MODEL_API_KEY": "sk-doctor-model-key",
    "BASETEN_API_KEY": "bt-doctor-open-key",
}
NAMES = [
    "GITHUB_TOKEN",
    "MODEL_API_KEY",
    "BASETEN_API_KEY",
    "muse",
    "ast-grep",
    "tickets",
    "sandbox",
    "arm home",
]
VERSIONS: dict[str, str | Exception] = {
    "muse": "Muse Code 1.4.14 (1.4.14-R7309.1)",
    "ast-grep": "ast-grep 0.51.0",
}


class FakeGitHub:
    def __init__(self, token: str, error: Exception | None = None) -> None:
        self.token, self.error = token, error

    def viewer(self) -> str:
        if self.error is not None:
            raise self.error
        return "maria"

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        return BASE.get(path) if sha == SHA else None


class FakeSpark:
    def __init__(self, model: str, answer: str | Exception = "ok") -> None:
        self.model, self.answer, self.prompts = model, answer, list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class FakeVersions:
    # Answers --version for muse and ast-grep; records every command it was asked to run.
    def __init__(self, lines: dict[str, str | Exception] = VERSIONS) -> None:
        self.lines, self.calls = lines, list[list[str]]()

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        line = self.lines[Path(argv[0]).name]
        if isinstance(line, Exception):
            raise line
        return line


def root() -> Root:
    fields: dict[str, Any] = {"id": "widgets-9-1", "title": "t", "quote": "q"}
    fields |= {"source_url": "https://github.com/acme/widgets/pull/9", "why": "w"}
    fields |= {"decision": "Read blobs one at a time", "decided_by": "maria"}
    rejected = "asyncio.gather over every blob at once"
    return Root.model_validate(
        fields | {"status": "Inferred", "rejected_alternative": rejected}
    )


@pytest.fixture
def real_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # The user's home, holding the acme/widgets home registry tickets are checked against.
    home = tmp_path / "real"
    out = home / ".knack/registries/acme-widgets"
    write_root(root(), out / "roots" / "widgets-9-1.json")
    (out / "rules").mkdir(parents=True)
    (out / "rules/9.yml").write_text(RULE)
    entry = RegistryEntry(rule=Path("rules/9.yml"), root_ids=["widgets-9-1"])
    registry = Registry(repo=REPO, roots_dir=Path("roots"), rules=[entry])
    (out / "registry.json").write_text(registry.model_dump_json())
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def kit(tmp_path: Path, real_home: Path) -> DoctorKit:
    tickets = tmp_path / "tickets.jsonl"
    tickets.write_text(json.dumps(TICKET) + "\n")
    return DoctorKit(
        env=ENV,
        github=FakeGitHub,
        spark=lambda key: FakeSpark("fake-spark"),
        spark_open=lambda key: FakeSpark("fake-spark-open"),
        which=lambda name: f"/opt/bin/{name}",
        version=FakeVersions(),
        tickets=tickets,
        real_home=real_home,
        cache=tmp_path / "cache",
        scratch=tmp_path / "scratch",
    )


def always(spark: FakeSpark) -> Callable[[str], Spark]:
    return lambda key: spark


def rejecting(error: Exception) -> Callable[[str], FakeGitHub]:
    return lambda token: FakeGitHub(token, error)


def leaking_spark(key: str) -> FakeSpark:
    return FakeSpark("s", ValueError(f"bad key {key}"))


def nowhere(name: str) -> str | None:
    return None


def by_name(checks: list[Check]) -> dict[str, Check]:
    return {check.name: check for check in checks}


def failed(checks: list[Check]) -> list[str]:
    return [check.name for check in checks if not check.ok]


def test_every_check_passes_with_healthy_fakes(kit: DoctorKit) -> None:
    checks = run_doctor(kit)
    assert [c.name for c in checks] == NAMES and failed(checks) == []
    reasons = {c.name: c.reason for c in checks}
    assert "maria" in reasons["GITHUB_TOKEN"]
    assert "fake-spark" in reasons["MODEL_API_KEY"]
    assert "fake-spark-open" in reasons["BASETEN_API_KEY"]
    assert "/opt/bin/muse" in reasons["muse"] and "1.4.14" in reasons["muse"]
    assert "0.51.0" in reasons["ast-grep"]
    assert "1 ticket" in reasons["tickets"] and "widgets-9" in reasons["sandbox"]
    assert "warn+veto" in reasons["arm home"]


def test_no_agent_runs_only_version_commands(kit: DoctorKit) -> None:
    versions = FakeVersions()
    run_doctor(replace(kit, version=versions))
    assert versions.calls == [
        ["/opt/bin/muse", "--version"],
        [str(AST_GREP), "--version"],
    ]


def test_each_model_gets_one_tiny_call(kit: DoctorKit) -> None:
    spark, spark_open = FakeSpark("s"), FakeSpark("o")
    run_doctor(replace(kit, spark=always(spark), spark_open=always(spark_open)))
    assert len(spark.prompts) == len(spark_open.prompts) == 1
    assert len(spark.prompts[0]) < 100


def test_each_key_goes_to_its_own_client(kit: DoctorKit) -> None:
    keys = list[str]()

    def record(key: str) -> FakeSpark:
        keys.append(key)
        return FakeSpark("m")

    run_doctor(replace(kit, spark=record, spark_open=record))
    assert keys == [ENV["MODEL_API_KEY"], ENV["BASETEN_API_KEY"]]


@pytest.mark.parametrize("name", ["MODEL_API_KEY", "BASETEN_API_KEY"])
def test_a_missing_model_key_fails_its_check_only(kit: DoctorKit, name: str) -> None:
    env = {k: v for k, v in ENV.items() if k != name}
    checks = run_doctor(replace(kit, env=env))
    assert failed(checks) == [name]
    assert by_name(checks)[name].reason == f"{name} is not set"


def test_a_missing_github_token_fails_github_and_the_sandbox(kit: DoctorKit) -> None:
    env = {k: v for k, v in ENV.items() if k != "GITHUB_TOKEN"}
    checks = run_doctor(replace(kit, env=env))
    assert failed(checks) == ["GITHUB_TOKEN", "sandbox"]
    assert by_name(checks)["GITHUB_TOKEN"].reason == "GITHUB_TOKEN is not set"


def test_a_rejected_github_token_fails_with_the_http_status(kit: DoctorKit) -> None:
    error = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)  # type: ignore[arg-type]
    checks = run_doctor(replace(kit, github=rejecting(error)))
    assert "401" in by_name(checks)["GITHUB_TOKEN"].reason
    assert not by_name(checks)["GITHUB_TOKEN"].ok


def test_a_failing_or_empty_model_answer_fails(kit: DoctorKit) -> None:
    down, empty = FakeSpark("s", OSError("network down")), FakeSpark("o", "  ")
    sick = replace(kit, spark=always(down), spark_open=always(empty))
    checks = by_name(run_doctor(sick))
    assert checks["MODEL_API_KEY"].reason == "OSError: network down"
    assert (
        not checks["BASETEN_API_KEY"].ok and "empty" in checks["BASETEN_API_KEY"].reason
    )


def test_a_secret_in_an_error_never_reaches_the_reason(kit: DoctorKit) -> None:
    leaky = replace(kit, spark=leaking_spark)
    checks = run_doctor(leaky)
    assert ENV["MODEL_API_KEY"] not in format_checks(checks)
    assert "bad key ***" in by_name(checks)["MODEL_API_KEY"].reason


def test_muse_off_path_fails(kit: DoctorKit) -> None:
    checks = run_doctor(replace(kit, which=nowhere))
    assert failed(checks) == ["muse"]
    assert by_name(checks)["muse"].reason == "muse is not on PATH"


def test_ast_grep_missing_or_unpinned_fails(kit: DoctorKit) -> None:
    missing = FakeVersions(VERSIONS | {"ast-grep": FileNotFoundError("no ast-grep")})
    unpinned = FakeVersions(VERSIONS | {"ast-grep": "ast-grep 0.50.0"})
    reasons = [
        by_name(run_doctor(replace(kit, version=v)))["ast-grep"]
        for v in (missing, unpinned)
    ]
    assert [r.ok for r in reasons] == [False, False]
    assert "no ast-grep" in reasons[0].reason and "0.51.0" in reasons[1].reason


def test_bad_tickets_fail_tickets_sandbox_and_home(kit: DoctorKit) -> None:
    kit.tickets.write_text('{"id": "x"}\n')
    checks = run_doctor(kit)
    assert failed(checks) == ["tickets", "sandbox", "arm home"]
    assert "line 1" in by_name(checks)["tickets"].reason


def test_an_empty_tickets_file_fails(kit: DoctorKit) -> None:
    kit.tickets.write_text("")
    checks = run_doctor(kit)
    assert failed(checks) == ["tickets", "sandbox", "arm home"]
    assert "no tickets" in by_name(checks)["tickets"].reason


def test_a_file_missing_at_base_sha_fails_the_sandbox(kit: DoctorKit) -> None:
    class Gone(FakeGitHub):
        def file_at(self, repo: str, sha: str, path: str) -> str | None:
            return None

    checks = run_doctor(replace(kit, github=Gone))
    assert failed(checks) == ["sandbox"]
    assert "does not exist" in by_name(checks)["sandbox"].reason


def test_an_arm_home_without_a_source_registry_fails(
    kit: DoctorKit, tmp_path: Path
) -> None:
    checks = run_doctor(replace(kit, real_home=tmp_path / "elsewhere"))
    assert failed(checks) == ["arm home"]


def test_format_prints_pass_or_fail_with_a_reason() -> None:
    checks = [
        Check(name="muse", ok=True, reason="v1"),
        Check(name="tickets", ok=False, reason="bad"),
    ]
    assert format_checks(checks) == "PASS muse: v1\nFAIL tickets: bad"


def test_doctor_prints_and_reports_overall(
    kit: DoctorKit, capsys: pytest.CaptureFixture[str]
) -> None:
    assert doctor(kit) is True
    assert capsys.readouterr().out.count("PASS ") == len(NAMES)
    assert doctor(replace(kit, which=nowhere)) is False
    assert "FAIL muse: muse is not on PATH" in capsys.readouterr().out


@pytest.mark.parametrize(("passed", "code"), [(True, 0), (False, 1)])
def test_knack_bench_doctor_exits_1_on_any_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, passed: bool, code: int
) -> None:
    seen = list[tuple[Path, Path]]()

    def fake(tickets: Path, cache: Path) -> bool:
        seen.append((tickets, cache))
        return passed

    monkeypatch.setattr("knack.cli.live_doctor", fake)
    argv = ["bench", "doctor", "--tickets", str(tmp_path / "t.jsonl")]
    assert knack_main([*argv, "--cache", str(tmp_path / "c")]) == code
    assert seen == [(tmp_path / "t.jsonl", tmp_path / "c")]
