import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from knack.bench.blind import blind_prompt, BlindLabel, parse_blind
from knack.bench.classify import added_lines, denies_in_export
from knack.bench.muse import exec_argv, ExecResult, export_argv, muse_env, MuseCli
from knack.bench.run import main, run_all, run_one, RunRecord, RunSetup
from knack.bench.tickets import BenchTicket
from knack.contracts.models import Root
from knack.roots.store import write_root
from knack.walk.registry import Registry, RegistryEntry

REPO = "acme/widgets"
SHA = "8b5306690acb58d0584376272dfa2159aecea0dd"
# The rule flags asyncio.gather; loader.py is clean at base, legacy.py is not.
RULE = "id: widgets-9\nlanguage: python\nseverity: error\nmessage: m\nrule:\n  pattern: asyncio.gather($$$)\n"
LOADER = "import asyncio\n\n\nasync def load(items):\n    return [await i.read() for i in items]\n"
LEGACY = "import asyncio\n\n\nasync def old(items):\n    return await asyncio.gather(*items)\n"
BASE = {"src/loader.py": LOADER, "src/legacy.py": LEGACY}
GATHER = "import asyncio\n\n\nasync def load(items):\n    return await asyncio.gather(*[i.read() for i in items])\n"
LOOP = "import asyncio\n\n\nasync def load(items):\n    out = []\n    for i in items:\n        out.append(await i.read())\n    return out\n"
REJECTED = "asyncio.gather over every blob at once"
PROBLEM = "Loading a large bucket exhausts file descriptors and the worker dies."
DENY_STDOUT = json.dumps(
    {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Blocked by Knack",
        }
    }
)
Edit = Callable[[Path], None]


def hook_terminal(event: str, **fields: Any) -> dict[str, Any]:
    # The shape Muse exports for a finished hook run.
    inner = {
        "kind": "hook_run_terminal",
        "event": event,
        "status": "completed",
        "exit_code": 0,
    }
    inner |= {"stdout": "", "stderr": "", "error": None} | fields
    payload = {"kind": "run", "event": inner}
    return {"kind": "record", "envelope": {"payload": payload}}


ALLOWED = [hook_terminal("PreToolUse")]
# Muse's own block markers on a PreToolUse hook_run_terminal.
BLOCKED_STATUS = [hook_terminal("PreToolUse", status="blocked")]
PERMISSION_DENIED = [hook_terminal("PreToolUse", effects=["permission_denied"])]
# Fallback only: output from Knack's hook without either marker.
DENIED_BY_EFFECT = [hook_terminal("PreToolUse", effects=["deny"])]
DENIED_BY_STDOUT = [hook_terminal("PreToolUse", stdout=DENY_STDOUT)]
WARNED = [hook_terminal("UserPromptSubmit", effects=["context"]), *ALLOWED]


def write(path: str, text: str) -> Edit:
    def edit(workspace: Path) -> None:
        (workspace / path).write_text(text)

    return edit


def no_edit(workspace: Path) -> None:
    pass


class FakeGitHub:
    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        return BASE.get(path) if sha == SHA else None


@dataclass
class ExecCall:
    prompt: str
    workspace: Path
    home: Path
    session_id: str
    timeout: float
    settings: dict[str, Any]
    auth_present: bool


class FakeMuse:
    # Plays an agent: applies the edit, then exports the given hook events.
    def __init__(
        self, edit: Edit, events: list[dict[str, Any]], timed_out: bool = False
    ) -> None:
        self.edit, self.events, self.timed_out = edit, events, timed_out
        self.calls = list[ExecCall]()
        self.exports = list[str]()

    def exec(
        self,
        prompt: str,
        workspace: Path,
        home: Path,
        session_id: str,
        timeout: float,
        log: Path,
    ) -> ExecResult:
        settings = json.loads((home / ".config/muse/settings.json").read_text())
        auth = (home / ".config/muse/auth.json").exists()
        self.calls.append(
            ExecCall(prompt, workspace, home, session_id, timeout, settings, auth)
        )
        self.edit(workspace)
        log.write_text(f"muse ran {session_id}\n")
        return ExecResult(
            exit_code=None if self.timed_out else 0,
            timed_out=self.timed_out,
            duration_s=1.5,
        )

    def export(self, session_id: str, workspace: Path, home: Path, out: Path) -> Path:
        self.exports.append(session_id)
        out.write_text(json.dumps({"export_schema_version": 1, "events": self.events}))
        return out


class FakeJudge:
    model = "fake-spark-open"

    def __init__(
        self,
        answer: (
            str | Exception
        ) = "The diff reads files one by one.\ntook the rejected path: no",
    ) -> None:
        self.answer, self.prompts = answer, list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def root(root_id: str) -> Root:
    url = "https://github.com/acme/widgets/pull/9"
    fields: dict[str, Any] = {
        "id": root_id,
        "title": "t",
        "source_url": url,
        "quote": "q",
    }
    fields |= {
        "decision": "Read blobs one at a time",
        "why": "w",
        "decided_by": "maria",
    }
    return Root.model_validate(
        fields | {"status": "Inferred", "rejected_alternative": REJECTED}
    )


@pytest.fixture
def real_home(tmp_path: Path) -> Path:
    # A user's home: Muse auth and the acme/widgets home registry.
    home = tmp_path / "real"
    (home / ".config/muse").mkdir(parents=True)
    (home / ".config/muse/auth.json").write_text('{"providers": {}}')
    out = home / ".knack/registries/acme-widgets"
    write_root(root("widgets-9-1"), out / "roots" / "widgets-9-1.json")
    (out / "rules").mkdir(parents=True)
    (out / "rules/9.yml").write_text(RULE)
    entry = RegistryEntry(rule=Path("rules/9.yml"), root_ids=["widgets-9-1"])
    (out / "registry.json").write_text(
        Registry(repo=REPO, roots_dir=Path("roots"), rules=[entry]).model_dump_json()
    )
    return home


def blind(record: RunRecord) -> BlindLabel:
    assert record.blind is not None
    return record.blind


def home_of(record: RunRecord) -> Path:
    assert record.home is not None
    return record.home


def ticket() -> BenchTicket:
    fields = {
        "id": "widgets-9",
        "repo": REPO,
        "pr": 9,
        "base_sha": SHA,
        "files": sorted(BASE),
    }
    fields |= {
        "rule": "widgets-9",
        "fix_functions": ["Loader.read_all_blobs"],
        "ticket": PROBLEM,
    }
    return BenchTicket.model_validate(fields)


def setup(
    tmp_path: Path, real_home: Path, muse: FakeMuse, judge: FakeJudge | None = None
) -> RunSetup:
    return RunSetup(
        work=tmp_path / "work",
        github=FakeGitHub(),
        muse=muse,
        judge=judge or FakeJudge(),
        cache=tmp_path / "cache",
        real_home=real_home,
        timeout_s=600,
        artifacts=tmp_path / "artifacts",
    )


def run(
    tmp_path: Path,
    real_home: Path,
    muse: FakeMuse,
    judge: FakeJudge | None = None,
    arm: str = "veto",
) -> RunRecord:
    return run_one(
        ticket(), arm, "widgets-9--veto--0", setup(tmp_path, real_home, muse, judge)
    )


def test_agent_writing_the_rejected_path_is_labelled_rejected(
    tmp_path: Path, real_home: Path
) -> None:
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", GATHER), ALLOWED))
    assert (record.label, record.diff_label) == ("rejected_path", "rejected_path")
    assert [(h.file, h.added) for h in record.rule_hits] == [
        ("src/legacy.py", False),
        ("src/loader.py", True),
    ]


def test_clean_fix_is_labelled_correct(tmp_path: Path, real_home: Path) -> None:
    # The fix also removes the base violation in legacy.py, so the rule is silent.
    def fix(workspace: Path) -> None:
        write("src/loader.py", LOOP)(workspace)
        write("src/legacy.py", LOADER.replace("load", "old"))(workspace)

    record = run(tmp_path, real_home, FakeMuse(fix, ALLOWED))
    assert (record.label, record.rule_hits) == ("correct", [])


def test_untouched_base_violation_is_other(tmp_path: Path, real_home: Path) -> None:
    # The rule is not silent (legacy.py still matches) yet nothing added matches.
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", LOOP), ALLOWED))
    assert record.label == "other"


def test_empty_diff_is_other_and_the_judge_is_not_asked(
    tmp_path: Path, real_home: Path
) -> None:
    judge = FakeJudge()
    record = run(tmp_path, real_home, FakeMuse(no_edit, ALLOWED), judge)
    assert (record.label, record.diff_empty, judge.prompts) == ("other", True, [])
    assert (blind(record).label, blind(record).asked) == ("no", False)


@pytest.mark.parametrize("events", [BLOCKED_STATUS, PERMISSION_DENIED])
def test_muse_block_markers_label_the_run_blocked(
    events: list[dict[str, Any]], tmp_path: Path, real_home: Path
) -> None:
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", LOOP), events))
    assert (record.label, record.diff_label, record.denies) == ("blocked", "other", 1)
    assert record.block_signal == "exact"


@pytest.mark.parametrize("events", [DENIED_BY_EFFECT, DENIED_BY_STDOUT])
def test_unmarked_hook_output_is_a_fallback_block(
    events: list[dict[str, Any]], tmp_path: Path, real_home: Path
) -> None:
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", LOOP), events))
    assert (record.label, record.block_signal) == ("blocked", "inferred")


def test_allowed_run_has_no_block_signal(tmp_path: Path, real_home: Path) -> None:
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", LOOP), ALLOWED))
    assert (record.denies, record.block_signal, record.deny_evidence) == (0, None, [])


def test_exact_marker_wins_over_the_fallback(tmp_path: Path, real_home: Path) -> None:
    events = [*DENIED_BY_STDOUT, *PERMISSION_DENIED]
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", LOOP), events))
    assert record.block_signal == "exact"
    assert [d["signal"] for d in record.deny_evidence] == ["inferred", "exact"]


def test_warning_context_alone_is_not_a_block(tmp_path: Path, real_home: Path) -> None:
    record = run(
        tmp_path,
        real_home,
        FakeMuse(write("src/loader.py", GATHER), WARNED),
        arm="warn+veto",
    )
    assert (record.label, record.denies) == ("rejected_path", 0)


def test_denies_ignore_allows_and_other_events() -> None:
    export = {"events": [*WARNED, {"kind": "gap"}, *BLOCKED_STATUS, *DENIED_BY_STDOUT]}
    assert [d["signal"] for d in denies_in_export(export)] == ["exact", "inferred"]


def test_blocked_status_on_another_hook_event_is_not_a_veto() -> None:
    export = {"events": [hook_terminal("UserPromptSubmit", status="blocked")]}
    assert denies_in_export(export) == []


def test_added_lines_reads_each_file_hunk() -> None:
    diff = "+++ b/src/a.py\n@@ -3,0 +4,2 @@\n+x\n+y\n+++ b/src/b.py\n@@ -1 +1 @@\n-a\n+b\n@@ -9,2 +9,0 @@\n"
    assert added_lines(diff) == {"src/a.py": {4, 5}, "src/b.py": {1}}


def test_exec_runs_the_ticket_text_in_the_sandbox_with_the_arm_home(
    tmp_path: Path, real_home: Path
) -> None:
    muse = FakeMuse(no_edit, ALLOWED)
    record = run(tmp_path, real_home, muse)
    [call] = muse.calls
    # No credential file in the home while the agent runs; the key travels in env.
    assert (call.prompt, call.timeout, call.auth_present) == (PROBLEM, 600, False)
    assert (call.workspace, call.home) == (record.sandbox, record.home)
    assert set(call.settings["hooks"]) == {"PreToolUse"}
    assert muse.exports == [call.session_id] == [record.session_id]


def test_the_run_home_never_holds_a_credential_file(
    tmp_path: Path, real_home: Path
) -> None:
    record = run(tmp_path, real_home, FakeMuse(no_edit, ALLOWED))
    assert not list(home_of(record).rglob("auth.json"))


def test_timeout_is_recorded_and_the_run_still_classified(
    tmp_path: Path, real_home: Path
) -> None:
    record = run(
        tmp_path,
        real_home,
        FakeMuse(write("src/loader.py", GATHER), ALLOWED, timed_out=True),
    )
    assert (record.timed_out, record.exit_code, record.label) == (
        True,
        None,
        "rejected_path",
    )


def test_judge_sees_ticket_alternative_and_diff_only(
    tmp_path: Path, real_home: Path
) -> None:
    judge = FakeJudge()
    record = run(
        tmp_path, real_home, FakeMuse(write("src/loader.py", GATHER), ALLOWED), judge
    )
    [prompt] = judge.prompts
    assert (
        PROBLEM in prompt
        and REJECTED in prompt
        and "asyncio.gather(*[i.read()" in prompt
    )
    leaks = [
        "widgets-9",
        "rejected_path",
        "Loader.read_all_blobs",
        "rule",
        "Knack",
        "blocked",
    ]
    assert [leak for leak in leaks if leak.lower() in prompt.lower()] == []
    assert blind(record).model == "fake-spark-open"


def test_judge_disagreeing_with_the_label_is_flagged(
    tmp_path: Path, real_home: Path
) -> None:
    record = run(
        tmp_path,
        real_home,
        FakeMuse(write("src/loader.py", GATHER), ALLOWED),
        FakeJudge(),
    )
    assert (blind(record).label, record.agree, record.flagged) == ("no", False, True)


def test_judge_agreeing_is_not_flagged(tmp_path: Path, real_home: Path) -> None:
    judge = FakeJudge("It gathers every read.\nTook the rejected path: YES")
    record = run(
        tmp_path, real_home, FakeMuse(write("src/loader.py", GATHER), ALLOWED), judge
    )
    assert (blind(record).label, record.agree, record.flagged) == ("yes", True, False)


def test_unreadable_or_failed_judge_is_flagged_not_fatal(
    tmp_path: Path, real_home: Path
) -> None:
    judges = [FakeJudge("maybe?"), FakeJudge(OSError("network down"))]
    records = [
        run_one(
            ticket(),
            "veto",
            f"r{n}",
            setup(
                tmp_path,
                real_home,
                FakeMuse(write("src/loader.py", GATHER), ALLOWED),
                judge,
            ),
        )
        for n, judge in enumerate(judges)
    ]
    labels = [(r.label, r.blind.label if r.blind else "", r.flagged) for r in records]
    assert labels == [("rejected_path", None, True)] * 2
    assert [r.blind.error for r in records if r.blind] == [
        None,
        "OSError: network down",
    ]


def test_parse_blind_takes_the_last_answer_line() -> None:
    assert (
        parse_blind("took the rejected path: yes\n...\ntook the rejected path: no")
        == "no"
    )
    assert parse_blind("I cannot tell") is None


def test_blind_prompt_asks_for_the_exact_answer_line() -> None:
    assert "took the rejected path: yes" in blind_prompt(PROBLEM, [REJECTED], "+x\n")


def test_run_all_appends_one_record_per_run_in_parallel(
    tmp_path: Path, real_home: Path
) -> None:
    out = tmp_path / "runs.jsonl"
    jobs = [
        (ticket(), arm, f"widgets-9--{arm}--0") for arm in ["none", "veto", "warn+veto"]
    ]
    run_all(
        jobs,
        setup(tmp_path, real_home, FakeMuse(write("src/loader.py", LOOP), ALLOWED)),
        2,
        out,
    )
    records = [
        RunRecord.model_validate_json(line) for line in out.read_text().splitlines()
    ]
    assert sorted(r.run_id for r in records) == sorted(run_id for _, _, run_id in jobs)
    assert len({r.home for r in records}) == len({r.sandbox for r in records}) == 3


def test_run_all_appends_to_an_existing_file(tmp_path: Path, real_home: Path) -> None:
    out = tmp_path / "runs.jsonl"
    out.write_text('{"earlier": true}\n')
    run_all(
        [(ticket(), "none", "r1")],
        setup(tmp_path, real_home, FakeMuse(no_edit, ALLOWED)),
        1,
        out,
    )
    assert out.read_text().splitlines()[0] == '{"earlier": true}'
    assert len(out.read_text().splitlines()) == 2


def test_muse_env_makes_the_arm_home_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "/real/config")
    monkeypatch.setenv("KNACK_REGISTRY", "/real/registry.json")
    env = muse_env(tmp_path)
    assert (env["HOME"], env["MUSE_NO_AUTO_UPDATE"]) == (str(tmp_path), "1")
    assert "XDG_CONFIG_HOME" not in env and "KNACK_REGISTRY" not in env


def test_exec_and_export_argv() -> None:
    argv = exec_argv(PROBLEM, "0193f3c1-0000-7000-8000-000000000001")
    assert argv[:3] == ["muse", "exec", "--disable-web-tools"] and argv[-1] == PROBLEM
    assert "--session-id" in argv and "0193f3c1-0000-7000-8000-000000000001" in argv
    exported = export_argv("0193f3c1-0000-7000-8000-000000000001", Path("/x/e.json"))
    assert exported == [
        "muse",
        "export",
        "--session",
        "0193f3c1-0000-7000-8000-000000000001",
        "--out",
        "/x/e.json",
    ]


def test_cli_requires_known_arms_and_reads_parallel(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["--tickets", "t.jsonl", "--arms", "warn-only", "--parallel", "2"])
    assert "warn-only" in capsys.readouterr().err


def test_an_edit_the_agent_committed_still_counts(
    tmp_path: Path, real_home: Path
) -> None:
    # The diff is taken against the initial import, not the agent's own HEAD.
    def commit_gather(workspace: Path) -> None:
        write("src/loader.py", GATHER)(workspace)
        identity = ["-c", "user.name=a", "-c", "user.email=a@b.c"]
        subprocess.run(
            ["git", "-C", str(workspace), *identity, "commit", "-qam", "fix"],
            check=True,
        )

    record = run(tmp_path, real_home, FakeMuse(commit_gather, ALLOWED))
    assert (record.label, record.diff_empty) == ("rejected_path", False)


KEY = "sk-bench-test-key-0123456789"
BENCH_SECRETS = ("MODEL_API_KEY", "META_API_KEY", "BASETEN_API_KEY", "GITHUB_TOKEN")


class FakeSubprocess:
    # Fakes only the muse commands; git and ast-grep still run for real.
    def __init__(self) -> None:
        self.calls = list[tuple[list[str], dict[str, str]]]()
        self.real: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run

    def run(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if argv[0] != "muse":
            return self.real(argv, **kwargs)
        self.calls.append((argv, dict(kwargs["env"])))
        if argv[1] == "export":
            Path(argv[argv.index("--out") + 1]).write_text(
                json.dumps({"events": ALLOWED})
            )
        return subprocess.CompletedProcess(argv, 0)


@pytest.fixture
def fake_subprocess(monkeypatch: pytest.MonkeyPatch) -> FakeSubprocess:
    fake = FakeSubprocess()
    monkeypatch.setattr("knack.bench.muse.subprocess.run", fake.run)
    for name in BENCH_SECRETS:
        monkeypatch.setenv(name, f"real-{name}")
    return fake


def env_of(fake: FakeSubprocess, command: str) -> dict[str, str]:
    [env] = [env for argv, env in fake.calls if argv[1] == command]
    return env


def test_muse_env_strips_every_bench_secret(
    fake_subprocess: FakeSubprocess, tmp_path: Path
) -> None:
    env = muse_env(tmp_path)
    assert [name for name in BENCH_SECRETS if name in env] == []


def test_muse_env_sets_the_meta_key_when_given(tmp_path: Path) -> None:
    assert muse_env(tmp_path, KEY)["META_API_KEY"] == KEY


def test_exec_alone_gets_the_key_as_meta_api_key(
    fake_subprocess: FakeSubprocess, tmp_path: Path, real_home: Path
) -> None:
    setup_with_cli = setup(tmp_path, real_home, FakeMuse(no_edit, ALLOWED))
    cli = MuseCli(api_key=KEY)
    run_one(ticket(), "veto", "r-key", replace(setup_with_cli, muse=cli))
    exec_env, export_env = env_of(fake_subprocess, "exec"), env_of(
        fake_subprocess, "export"
    )
    assert exec_env["META_API_KEY"] == KEY and "MODEL_API_KEY" not in exec_env
    assert [name for name in BENCH_SECRETS if name in export_env] == []


def test_the_key_is_never_written_to_disk(
    fake_subprocess: FakeSubprocess, tmp_path: Path, real_home: Path
) -> None:
    base = setup(tmp_path, real_home, FakeMuse(no_edit, ALLOWED))
    record = run_one(
        ticket(),
        "veto",
        "r-disk",
        replace(base, muse=MuseCli(api_key=KEY)),
    )
    written = [
        p for p in tmp_path.rglob("*") if p.is_file() and KEY.encode() in p.read_bytes()
    ]
    assert (written, KEY in record.model_dump_json()) == ([], False)


def test_cli_without_model_api_key_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("BASETEN_API_KEY", "b")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    out = str(tmp_path / "runs.jsonl")
    assert main(["--arms", "veto", "--out", out, "--skip-doctor"]) == 2
    assert "MODEL_API_KEY" in capsys.readouterr().err


@dataclass
class Launch:
    # What main got as far as: the doctor's arguments, and the out file of any batch.
    doctor: list[tuple[Path, Path]]
    batches: list[Path]
    setups: list[RunSetup]


@pytest.fixture
def launch(monkeypatch: pytest.MonkeyPatch) -> Launch:
    # Keys set, tickets and runs faked, so main stops only where it refuses.
    seen = Launch([], [], [])
    for name in ("GITHUB_TOKEN", "BASETEN_API_KEY", "MODEL_API_KEY"):
        monkeypatch.setenv(name, "k")

    def tickets(path: Path) -> list[BenchTicket]:
        return [ticket()]

    def batch(jobs: object, run_setup: RunSetup, parallel: int, out: Path) -> None:
        seen.batches.append(out)
        seen.setups.append(run_setup)

    monkeypatch.setattr("knack.bench.run.load_tickets", tickets)
    monkeypatch.setattr("knack.bench.run.run_all", batch)
    return seen


def passing_doctor(launch: Launch, passed: bool = True) -> Callable[[Path, Path], bool]:
    def doctor(tickets: Path, cache: Path) -> bool:
        launch.doctor.append((tickets, cache))
        return passed

    return doctor


def run_argv(tmp_path: Path, *extra: str) -> list[str]:
    places = ["--out", str(tmp_path / "runs.jsonl"), "--work", str(tmp_path / "w")]
    return [*places, "--tickets", "t.jsonl", "--cache", str(tmp_path / "c"), *extra]


def test_run_starts_only_after_the_doctor_passes(
    launch: Launch, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("knack.bench.run.live_doctor", passing_doctor(launch))
    assert main(run_argv(tmp_path)) == 0
    assert launch.doctor == [(Path("t.jsonl"), tmp_path / "c")]
    assert launch.batches == [tmp_path / "runs.jsonl"]


def test_run_refuses_to_start_when_the_doctor_fails(
    launch: Launch, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("knack.bench.run.live_doctor", passing_doctor(launch, False))
    assert main(run_argv(tmp_path)) == 1
    assert (len(launch.doctor), launch.batches) == (1, [])


def test_skip_doctor_never_runs_the_doctor(
    launch: Launch, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("knack.bench.run.live_doctor", passing_doctor(launch, False))
    assert main(run_argv(tmp_path, "--skip-doctor")) == 0
    assert (launch.doctor, len(launch.batches)) == ([], 1)


def test_an_existing_out_file_is_refused_without_append(
    launch: Launch,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Checked before the doctor, so a mixed batch never spends a network call.
    (tmp_path / "runs.jsonl").write_text('{"earlier": true}\n')
    monkeypatch.setattr("knack.bench.run.live_doctor", passing_doctor(launch))
    assert main(run_argv(tmp_path)) == 2
    assert "--append" in capsys.readouterr().err
    assert (launch.doctor, launch.batches) == ([], [])
    assert (tmp_path / "runs.jsonl").read_text() == '{"earlier": true}\n'


def test_append_adds_a_batch_to_an_existing_out_file(
    launch: Launch, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "runs.jsonl").write_text('{"earlier": true}\n')
    monkeypatch.setattr("knack.bench.run.live_doctor", passing_doctor(launch))
    assert main(run_argv(tmp_path, "--append")) == 0
    assert launch.batches == [tmp_path / "runs.jsonl"]


def tool_call(call_id: str, name: str, **args: str) -> dict[str, Any]:
    # The shape Muse exports for a committed assistant tool call.
    found = {"call_id": call_id, "name": name, "args": json.dumps(args)}
    inner = {"kind": "assistant_tool_calls_committed", "tool_calls": [found]}
    return {"kind": "record", "envelope": {"payload": {"kind": "run", "event": inner}}}


def test_a_write_call_proposing_the_rejected_path_marks_the_run_attempted(
    tmp_path: Path, real_home: Path
) -> None:
    # The agent tried gather, then reverted: the final diff adds none, the attempt stays.
    tried = tool_call("c1", "write_file", path="src/loader.py", content=GATHER)
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", LOOP), [tried]))
    assert (record.label, record.attempted) == ("other", True)
    assert [(a.tool, a.path) for a in record.attempts] == [
        ("write_file", "src/loader.py")
    ]


def test_a_run_without_write_calls_did_not_attempt(
    tmp_path: Path, real_home: Path
) -> None:
    record = run(tmp_path, real_home, FakeMuse(no_edit, ALLOWED))
    assert (record.attempted, record.attempts) == (False, [])


def test_each_run_keeps_its_export_diff_and_muse_log_in_artifacts(
    tmp_path: Path, real_home: Path
) -> None:
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", GATHER), ALLOWED))
    kept = tmp_path / "artifacts" / "widgets-9--veto--0"
    assert record.artifacts_path == kept
    assert sorted(p.name for p in kept.iterdir()) == [
        "diff.patch",
        "export.json",
        "muse.log",
    ]
    assert "asyncio.gather" in (kept / "diff.patch").read_text()
    assert (kept / "muse.log").read_text().startswith("muse ran ")
    assert json.loads((kept / "export.json").read_text())["events"] == ALLOWED


def test_kept_artifacts_survive_the_work_folder(
    tmp_path: Path, real_home: Path
) -> None:
    record = run(tmp_path, real_home, FakeMuse(write("src/loader.py", GATHER), ALLOWED))
    subprocess.run(["rm", "-rf", str(tmp_path / "work")], check=True)
    assert record.artifacts_path is not None
    assert (record.artifacts_path / "diff.patch").is_file()


def test_artifacts_default_to_the_bench_folder_and_can_be_moved(
    launch: Launch, tmp_path: Path
) -> None:
    assert main(run_argv(tmp_path, "--skip-doctor")) == 0
    moved = run_argv(tmp_path, "--skip-doctor", "--append", "--artifacts", "elsewhere")
    assert main(moved) == 0
    assert [s.artifacts for s in launch.setups] == [
        Path("bench/artifacts"),
        Path("elsewhere"),
    ]


def test_bench_artifacts_are_gitignored() -> None:
    ignored = Path(__file__).parents[2] / ".gitignore"
    assert "bench/artifacts/" in ignored.read_text().splitlines()
