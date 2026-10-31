import json
from pathlib import Path

import pytest
from knack import cli
from knack.contracts.models import Root
from knack.roots.backfill import backfill_merged_at
from knack.roots.store import load_roots, write_root
from registry_fixture import make_registry, root

MERGED = {9: "2026-09-09T09:00:00Z", 4: "2026-04-04T04:00:00Z"}


class FakeMerges:
    # Merge times by PR number; PR 3 was never merged. Counts every lookup.
    def __init__(self) -> None:
        self.asked = list[tuple[str, int]]()

    def merged_at(self, repo: str, number: int) -> str | None:
        self.asked.append((repo, number))
        return MERGED.get(number)


def merged_on_disk(roots_dir: Path) -> dict[str, str | None]:
    return {r.id: r.merged_at for r in load_roots(roots_dir)}


def test_roots_without_merged_at_take_their_prs(tmp_path: Path) -> None:
    roots_dir = make_registry(tmp_path / "out").parent / "roots"
    filled = backfill_merged_at(roots_dir, FakeMerges().merged_at)
    assert filled == ["widgets-4-1", "widgets-9-1", "widgets-9-2"]
    assert merged_on_disk(roots_dir) == {
        "widgets-3-1": None,
        "widgets-4-1": MERGED[4],
        "widgets-9-1": MERGED[9],
        "widgets-9-2": MERGED[9],
    }


def test_each_pr_is_asked_once(tmp_path: Path) -> None:
    roots_dir = make_registry(tmp_path / "out").parent / "roots"
    merges = FakeMerges()
    backfill_merged_at(roots_dir, merges.merged_at)
    assert sorted(merges.asked) == [("acme/widgets", n) for n in (3, 4, 9)]


def test_a_root_that_has_merged_at_is_left_alone(tmp_path: Path) -> None:
    roots_dir = tmp_path / "roots"
    kept = root("widgets-9-1", "Confirmed").model_copy(update={"merged_at": "old"})
    write_root(kept, roots_dir / "any-name.json")
    merges = FakeMerges()
    assert backfill_merged_at(roots_dir, merges.merged_at) == []
    assert merges.asked == [] and merged_on_disk(roots_dir) == {"widgets-9-1": "old"}


def test_backfill_keeps_status_quote_and_file_name(tmp_path: Path) -> None:
    roots_dir = tmp_path / "roots"
    write_root(root("widgets-9-1", "Confirmed"), roots_dir / "nine.json")
    backfill_merged_at(roots_dir, FakeMerges().merged_at)
    on_disk = json.loads((roots_dir / "nine.json").read_text())
    assert (on_disk["status"], on_disk["quote"]) == (
        "Confirmed",
        "quote of widgets-9-1",
    )
    assert on_disk["merged_at"] == MERGED[9]


def test_a_root_not_cited_to_a_pr_is_skipped(tmp_path: Path) -> None:
    roots_dir = tmp_path / "roots"
    url = "https://example.com/adr/7"
    fields = root("widgets-9-1", "Confirmed").model_dump() | {"source_url": url}
    write_root(Root.model_validate(fields), roots_dir / "a.json")
    merges = FakeMerges()
    assert backfill_merged_at(roots_dir, merges.merged_at) == [] and merges.asked == []


def test_knack_backfill_merged_fills_the_registrys_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = make_registry(tmp_path / "out")
    monkeypatch.setattr(cli, "github_client", lambda: FakeMerges())
    assert cli.main(["backfill-merged", "--registry", str(registry)]) == 0
    out = capsys.readouterr().out
    assert f"widgets-9-1: merged {MERGED[9]}" in out
    assert "3 roots backfilled, 1 without a merged PR" in out
    assert merged_on_disk(registry.parent / "roots")["widgets-4-1"] == MERGED[4]


def test_knack_backfill_merged_without_a_token_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = make_registry(tmp_path / "out")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert cli.main(["backfill-merged", "--registry", str(registry)]) == 2
    assert "GITHUB_TOKEN is not set" in capsys.readouterr().err
