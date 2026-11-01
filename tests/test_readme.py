import re
import subprocess
from pathlib import Path

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


VERIFY_HEADING = "## Verify any claim in 60 seconds"
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


def demo_latencies() -> tuple[str, str]:
    text = DEMO_LOG.read_text(encoding="utf-8")
    verdict = re.search(r"^guard verdict: (\d+\.\d+) ms", text, re.M)
    trip = re.search(r"^hook round trip: (\d+) ms", text, re.M)
    assert verdict and trip
    return verdict.group(1), trip.group(1)


def test_the_bench_heading_is_rejectbench() -> None:
    assert "### RejectBench [bench]" in README.read_text(encoding="utf-8").splitlines()


def test_readme_cites_the_demo_latencies_from_the_committed_log() -> None:
    verdict, trip = demo_latencies()
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert f"{verdict} ms" in text and f"{trip} ms" in text
    assert "bench/demo_block.log" in text


def test_readme_cites_the_repeat_hunt_with_its_reproduce_step() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert "5068 commits scanned, 0 repeat commits" in text
    assert "python -m knack.reproduce repeats" in text


def test_rejectbench_fresh_is_named_as_not_run() -> None:
    lines = README.read_text(encoding="utf-8").splitlines()
    [line] = [line for line in lines if "RejectBench-Fresh" in line]
    assert "not run" in line and "bench/PREREGISTRATION-FRESH.md" in line
