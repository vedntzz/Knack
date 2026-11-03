import json
import re
import subprocess
from pathlib import Path

from knack.dispute.argue import SPARK_MODEL
from knack.dispute.rulings import ModelCall, RulingRecord
from knack.hooks.pretool_guard import OPEN_CONSOLE, rerun_deny
from knack.miss.cases import ModelAnswer
from knack.miss.selfcheck import agreed
from knack.pipeline.spark_open import MODEL as OPEN_MODEL
from knack.walk.registry import load_registry

REPO_ROOT = Path(__file__).parents[1]
README = REPO_ROOT / "README.md"
REQUIRED_LINES = [
    "All code in this repository was written during the event, from Oct 26, 2026.",
    "a second, separately run Meta model",
    "13 outcomes",
    "17 of the 101 PRs yield 31 rejected alternatives",
    "Only AST-checkable, human-confirmed rules can block",
    "Token confidence is not exposed by the hosted endpoint; corroboration is the brake.",
]
# The KN-73 spike that found no logprobs on the hosted Spark Open endpoint.
SPIKE_LINK = "[spike/kn-73-open-weights](spikes/open_weights.md)"
# Knack is a guard over recorded decisions; it is never described as RAG.
RAG_WORDING = re.compile(r"\bRAG\b|retrieval[- ]augmented", re.IGNORECASE)


def tracked_text_files() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return [REPO_ROOT / name for name in listed.stdout.splitlines()]


def mentions_rag(path: Path) -> bool:
    # Binary or vanished files cannot mention RAG in prose.
    try:
        return bool(RAG_WORDING.search(path.read_text(encoding="utf-8")))
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        return False


def test_readme_carries_every_required_line() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert [line for line in REQUIRED_LINES if line not in text] == []


def test_token_confidence_limit_links_the_open_weights_spike() -> None:
    lines = README.read_text(encoding="utf-8").splitlines()
    [line] = [line for line in lines if "Token confidence is not exposed" in line]
    assert SPIKE_LINK in line
    assert (REPO_ROOT / "spikes/open_weights.md").is_file()


def test_no_tracked_file_describes_knack_as_rag() -> None:
    hits = [
        p.name for p in tracked_text_files() if p != Path(__file__) and mentions_rag(p)
    ]
    assert hits == []


VERIFY_HEADING = "## Verify any claim"
CLONE = "git clone https://github.com/vedntzz/Knack.git"


def readme_before_verify_table() -> str:
    text = README.read_text(encoding="utf-8")
    return text[: text.index(VERIFY_HEADING)]


def test_a_stranger_gets_the_clone_command_before_the_verify_table() -> None:
    assert CLONE in readme_before_verify_table()


def test_prerequisites_name_uv_jq_and_python_311_and_the_download() -> None:
    top = " ".join(readme_before_verify_table().split())
    [line] = [s for s in top.split("Prerequisites:")[1:]]
    for wanted in ["uv", "jq", "Python 3.11", "download"]:
        assert wanted in line, wanted


def test_the_venv_is_activated_before_the_verify_table() -> None:
    assert "source .venv/bin/activate" in readme_before_verify_table()


def test_readme_says_what_a_green_run_is_and_why_grid_cells_fail() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert "`PROOF: PASS`" in text and "`PROOF: FAIL (<step>)`" in text
    assert "FAIL cells in the grid are measured results, by design" in text


def test_readme_says_reproduce_checks_the_grid_rather_than_rewriting_it() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert "`reproduce.sh` never rewrites `bench/PROOF-GRID.md`" in text


def test_readme_names_knack_home() -> None:
    assert "`KNACK_HOME`" in README.read_text(encoding="utf-8")


INSTALL = "uv sync --frozen --extra dev --python 3.11"


def test_the_install_resolves_the_committed_lock() -> None:
    # --frozen installs uv.lock's exact versions and fails rather than re-resolve.
    assert INSTALL in readme_before_verify_table()
    assert "uv pip install" not in README.read_text(encoding="utf-8")


def test_uv_lock_is_committable() -> None:
    lock = REPO_ROOT / "uv.lock"
    ignored = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "uv.lock"],
        capture_output=True,
        text=True,
    )
    assert lock.is_file() and ignored.stdout == ""


# Group C: numbers.
DEMO_LOG = REPO_ROOT / "bench" / "demo_block.log"
LIVE_SPIKE = REPO_ROOT / "spikes" / "one_story_live.md"
# Superseded figures from bench/demo_block.log; the live one-story spike replaced them.
OLD_LATENCIES = ("18.7 ms", "212 ms")


def live_latencies() -> list[str]:
    # The spike's latency lines: this run's block figures and the range across today's runs.
    text = LIVE_SPIKE.read_text(encoding="utf-8")
    labels = ("Guard verdict, today's runs", "Hook round trip, today's runs")
    ranges = [re.search(rf"^- {label}: (.+ ms)\.$", text, re.M) for label in labels]
    block = re.findall(r"this run: (\S+ ms) \(block\)", text)
    return [m.group(1) for m in ranges if m] + block


def test_the_bench_heading_is_rejectbench() -> None:
    assert "### RejectBench [bench]" in README.read_text(encoding="utf-8").splitlines()


def test_readme_cites_this_runs_latency_from_the_live_spike() -> None:
    cited = live_latencies()
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert len(cited) == 4 and [n for n in cited if n not in text] == []
    assert "this run" in text and "2026-11-02" in text
    assert "spikes/one_story_live.md" in text
    assert [n for n in OLD_LATENCIES if n in text] == []


def test_readme_cites_the_repeat_hunt_with_its_reproduce_step() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert "5068 commits scanned, 0 repeat commits" in text
    assert "python -m knack.reproduce repeats" in text


def test_rejectbench_fresh_is_named_as_not_run() -> None:
    lines = README.read_text(encoding="utf-8").splitlines()
    [line] = [line for line in lines if "RejectBench-Fresh" in line]
    assert "not run" in line and "bench/PREREGISTRATION-FRESH.md" in line


# Group A: the top, for a stranger.
PROBLEM_STATEMENT = "Problem statement: Build for Your World"
CARD = REPO_ROOT / "docs" / "card.md"
ONE_STORY_RECEIPTS = REPO_ROOT / "mockups" / "fixtures" / "one_story" / "receipts.jsonl"
BLOCK_RECEIPT = "0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9"
REGISTRY = REPO_ROOT / "data" / "registry" / "airflow.json"
ROOT_75025 = REPO_ROOT / "data" / "roots" / "airflow" / "75025.json"
# The quote cut to its first sentence, as README showed it before KN-109.
OLD_QUOTE = 'Quote: "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."'
# The measured reproduce.sh wall time replaces the old "60 seconds" promise.
MEASURED_VERIFY = re.compile(
    r"^## Verify any claim: reproduce\.sh runs in \d+ s$", re.M
)


def demo_reason() -> str:
    # The deny reason as the agent reads it, from the committed demo_block.sh run.
    lines = DEMO_LOG.read_text(encoding="utf-8").splitlines()
    start = lines.index("== reason, as the agent reads it ==") + 1
    return "\n".join(lines[start : lines.index("", start)])


def test_problem_statement_says_why_in_the_same_line() -> None:
    lines = README.read_text(encoding="utf-8").splitlines()
    [line] = [line for line in lines if PROBLEM_STATEMENT in line]
    assert len(line) > len(PROBLEM_STATEMENT) + 40


def test_the_verify_heading_is_the_measured_runtime() -> None:
    text = README.read_text(encoding="utf-8")
    assert MEASURED_VERIFY.search(text) and "60 seconds" not in text


def frozen_block_reason(log: Path) -> str:
    # Today's guard, rerun on the frozen one-story block receipt's saved edit.
    found = rerun_deny(ONE_STORY_RECEIPTS, BLOCK_RECEIPT, load_registry(REGISTRY), log)
    assert found is not None
    return found["hookSpecificOutput"]["permissionDecisionReason"]


def readme_deny_block() -> str:
    # The first text block, under the one-liner, before any heading.
    text = README.read_text(encoding="utf-8")
    start = text.index("```text\n") + len("```text\n")
    return text[start : text.index("\n```", start)]


def test_the_readme_deny_is_the_guards_output_for_the_frozen_block(
    tmp_path: Path,
) -> None:
    text = README.read_text(encoding="utf-8")
    block = readme_deny_block()
    assert block == frozen_block_reason(tmp_path / "errors.log")
    assert text.index(block) < text.index("## ")
    assert "Knack blocks AI coding agents" in text[: text.index(block)]


def test_the_readme_deny_carries_the_full_quote_and_the_console_hint() -> None:
    lines = readme_deny_block().splitlines()
    quote = json.loads(ROOT_75025.read_text(encoding="utf-8"))["quote"]
    assert f'Quote: "{quote}"' in lines
    assert f"/verdict/{BLOCK_RECEIPT} {OPEN_CONSOLE}" in lines[-2]


def test_no_old_one_sentence_quote_remains_in_readme_or_card() -> None:
    texts = [p.read_text(encoding="utf-8") for p in (README, CARD)]
    assert [t for t in texts if OLD_QUOTE in " ".join(t.split())] == []


def test_the_demo_log_shows_todays_deny_but_for_its_own_receipt(
    tmp_path: Path,
) -> None:
    hashed = re.compile(r"(?<=/verdict/)[0-9a-f]{64}")
    today = hashed.sub("<hash>", frozen_block_reason(tmp_path / "errors.log"))
    assert hashed.sub("<hash>", demo_reason()) == today


def test_the_demo_logs_latencies_are_labelled_as_this_machines() -> None:
    lines = DEMO_LOG.read_text(encoding="utf-8").splitlines()
    timed = [line for line in lines if re.search(r": \d+(\.\d+)? ms ", line)]
    assert len(timed) == 2 and all("this machine" in line for line in timed)


# Group B: prize-facing sections.
PRIZE_HEADINGS = ["## Muse Code setup", "## Runs unattended", "## Open weights"]


def test_readme_carries_the_prize_headings() -> None:
    lines = README.read_text(encoding="utf-8").splitlines()
    assert [h for h in PRIZE_HEADINGS if h not in lines] == []


def test_open_weights_names_the_baseten_model() -> None:
    text = README.read_text(encoding="utf-8")
    assert "meta-models/muse-spark-open-1026" in text and "Baseten" in text


# Group C: who answers an objection, as argue and its second opinion do it.
WHO_RULES = (
    "The ruling is Spark's alone. Spark Open is asked only after Spark escalates."
)
BOTH_HOLD = (
    "If Spark and Spark Open both escalate, the edit is held as a provisional case."
)
THREE_CHOICES = (
    "A person has three choices: `knack resolve <receipt> allow|retire|uphold"
    ' --reason "<why>"`. Allow lets that exact edit through, retire drops the'
    " decision's rule, and uphold confirms the decision stands: the edit stays"
    " blocked, the held case closes, and no exception or case is added."
)
RULING_NAMES = (
    "Each ruling in `rulings.jsonl` names every model that answered (name, host, "
    "trace id) and the agent from the PreToolUse payload, or `not recorded`."
)


def answer(model: str) -> ModelAnswer:
    return ModelAnswer(model=model, yes=True, answer="escalate", prompt_sha256="0")


def test_readme_says_who_rules_on_an_objection() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert [s for s in (WHO_RULES, BOTH_HOLD, RULING_NAMES) if s not in text] == []


def test_the_code_holds_a_provisional_case_only_when_both_models_escalate() -> None:
    spark, spark_open = answer(SPARK_MODEL), answer(OPEN_MODEL)
    assert not agreed([spark]) and not agreed([spark, spark])
    assert agreed([spark, spark_open])


def test_a_ruling_record_names_its_models_and_agent() -> None:
    assert {"models", "agent"} <= set(RulingRecord.model_fields)
    assert set(ModelCall.model_fields) == {"model", "host", "trace_id"}


def test_readme_names_the_three_resolve_choices_under_argue() -> None:
    lines = README.read_text(encoding="utf-8").splitlines()
    argue = next(i for i, line in enumerate(lines) if "(`knack argue`)" in line)
    assert THREE_CHOICES in lines[argue + 1 : argue + 3]


ONLY_A_PERSON = (
    "Only a person can allow, and three things keep an agent out:"
    " `knack argue` never prints the resolve command, only where a person finds it"
    " (the console's held page); the PreToolUse guard denies any agent shell command"
    " that runs `knack resolve`, `knack confirm`, `knack false-block` or `knack retire`;"
    " and `knack resolve` refuses to run without an interactive terminal unless"
    " `--by` is given and the person sets `KNACK_HUMAN=1`."
)


def test_readme_names_what_keeps_an_agent_from_allowing_itself() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert ONLY_A_PERSON in text
    assert '"matcher": "write_file|edit_file|bash"' in text


SELF_ALLOW_FLOOR = (
    "The PreToolUse guard reduces agent self-allow; it does not eliminate it."
    " An agent can still hide or route around the command, for example inside a"
    " script, an alias or another program it runs. The CI guard"
    " ([`.github/workflows/knack-guard.yml`](.github/workflows/knack-guard.yml))"
    " is the floor: it checks every pull request's changed files and reads no"
    " local receipts, so a local allow never passes it."
)


def test_readme_says_the_self_allow_guard_reduces_and_ci_is_the_floor() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert ONLY_A_PERSON + " " + SELF_ALLOW_FLOOR in text
