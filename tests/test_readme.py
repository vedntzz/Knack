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
