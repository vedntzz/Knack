from pathlib import Path

CARD = Path(__file__).parents[1] / "docs" / "card.md"
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
