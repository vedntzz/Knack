import re
from pathlib import Path

CARD = Path(__file__).parents[1] / "docs" / "card.md"
LIVE_SPIKE = Path(__file__).parents[1] / "spikes" / "one_story_live.md"
REQUIRED = [
    "13 outcomes",
    "17 of 101 PRs",
    "31 rejected alternatives",
    "Muse Spark",
    "a second, separately run Meta model",
    "bash scripts/reproduce.sh",
    "uv sync --frozen --extra dev --python 3.11",
]


def test_card_is_under_forty_lines() -> None:
    assert len(CARD.read_text(encoding="utf-8").splitlines()) < 40


def test_card_carries_numbers_models_and_verify_command() -> None:
    text = " ".join(CARD.read_text(encoding="utf-8").split())
    assert [phrase for phrase in REQUIRED if phrase not in text] == []


def test_card_installs_from_the_lock_like_the_readme() -> None:
    assert "uv pip install" not in CARD.read_text(encoding="utf-8")


def test_card_cites_this_runs_latency_from_the_live_spike() -> None:
    spike = LIVE_SPIKE.read_text(encoding="utf-8")
    cited = re.findall(
        r"^- (?:Guard verdict|Hook round trip), today's runs: (.+ ms)\.$", spike, re.M
    )
    cited += re.findall(r"this run: (\S+ ms) \(block\)", spike)
    text = " ".join(CARD.read_text(encoding="utf-8").split())
    assert len(cited) == 4 and [n for n in cited if n not in text] == []
    assert "this run" in text and "2026-11-02" in text
