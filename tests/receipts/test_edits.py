from pathlib import Path

from knack.receipts.edits import edits_dir, EditSnapshot, load_edit, save_edit

EDIT = EditSnapshot(file="/clone/pkg/a.py", before="x = 1\n", after="x = 2\n")


def test_a_saved_edit_loads_back_by_its_hash(tmp_path: Path) -> None:
    digest = save_edit(tmp_path, EDIT)
    assert len(digest) == 64 and load_edit(tmp_path, digest) == EDIT


def test_the_same_edit_saves_once_under_the_same_hash(tmp_path: Path) -> None:
    assert save_edit(tmp_path, EDIT) == save_edit(tmp_path, EDIT)
    assert len(list(tmp_path.iterdir())) == 1


def test_a_new_file_edit_has_no_before(tmp_path: Path) -> None:
    created = EDIT.model_copy(update={"before": None})
    assert load_edit(tmp_path, save_edit(tmp_path, created)) == created


def test_an_unknown_hash_loads_nothing(tmp_path: Path) -> None:
    assert load_edit(tmp_path, "0" * 64) is None


def test_edits_live_beside_the_receipts(tmp_path: Path) -> None:
    assert edits_dir(tmp_path / "verdicts.jsonl") == tmp_path / "edits"
