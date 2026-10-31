import json
from pathlib import Path

from conftest import BASE, STRUCTURAL, write_tree
from knack.miss.cases import cases_dir
from knack.miss.selfcheck import load_checks, self_checks_path, Settle
from knack.walk.registry import load_registry
from knack.watch.selfcheck import check_merged, judge_prompt, Watched
from test_miss_loop import RETURNS_ONLY, ROOT, RULE_ID
from test_prove import EDIT_ADDS
from test_self_check import FakeJudge, FakeLoop, NO, YES

AFTER = BASE + EDIT_ADDS


class MergedGitHub:
    # PR 9 adds a gather to pkg/loader.py, a doc, and a new test file.
    def changed_files(self, repo: str, number: int) -> list[str]:
        return ["pkg/loader.py", "docs/a.md", "pkg/gone.py"]

    def shas(self, repo: str, number: int) -> tuple[str, str]:
        return "base", "head"

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        files = {"base": {"pkg/loader.py": BASE, "pkg/gone.py": "x = 1\n"}}
        files["head"] = {"pkg/loader.py": AFTER, "docs/a.md": "# hi\n"}
        return files[sha].get(path)


def registry(tmp_path: Path, rule: str, status: str = "Confirmed") -> Path:
    folder = tmp_path / "registry"
    root = ROOT | {"status": status}
    write_tree(folder, {"roots/widgets-9-1.json": json.dumps(root)})
    write_tree(folder, {"rules/9.yml": rule.replace("compiled-rule", RULE_ID)})
    entry = {"rule": "rules/9.yml", "root_ids": ["widgets-9-1"]}
    body = {"repo": "acme/widgets", "roots_dir": "roots", "rules": [entry]}
    (folder / "registry.json").write_text(json.dumps(body))
    return folder / "registry.json"


class Run:
    # One self-check of merged PR 9 against a registry, with fake judges and loop.
    def __init__(
        self,
        tmp_path: Path,
        rule: str,
        answers: tuple[str, str],
        status: str = "Confirmed",
    ) -> None:
        self.registry = registry(tmp_path, rule, status)
        self.spark, self.open = FakeJudge("spark", answers[0]), FakeJudge(
            "spark-open", answers[1]
        )
        self.loop, self.lines = FakeLoop(self.registry), list[str]()
        settle = Settle(
            self.registry, self_checks_path(self.registry), self.loop, self.lines.append
        )
        watched = Watched(MergedGitHub(), (self.spark, self.open), settle)
        check_merged(watched, load_registry(self.registry), [9])

    def checks(self):
        return load_checks(self_checks_path(self.registry))


def test_a_silent_confirmed_rule_both_judges_flag_becomes_a_must_fail_case(
    tmp_path: Path,
) -> None:
    run = Run(tmp_path, RETURNS_ONLY, (YES, YES))
    [[case]] = run.loop.runs
    assert (case.kind, case.rule_id, case.file) == (
        "must-fail",
        RULE_ID,
        "pkg/loader.py",
    )
    assert (case.before, case.after) == (BASE, AFTER)
    assert "PR #9" in case.source and "auto" in case.source
    assert [a.answer for a in case.answers] == [YES, YES]


def test_only_changed_python_files_that_still_exist_are_judged(tmp_path: Path) -> None:
    run = Run(tmp_path, RETURNS_ONLY, (NO, NO))
    assert [c.file for c in run.checks()] == ["pkg/loader.py"]


def test_both_judges_get_the_same_blind_prompt(tmp_path: Path) -> None:
    run = Run(tmp_path, RETURNS_ONLY, (YES, NO))
    [prompt] = run.spark.prompts
    assert run.open.prompts == [prompt]
    assert ROOT["rejected_alternative"] in prompt and ROOT["quote"] in prompt
    assert "+    data = await asyncio.gather" in prompt
    lowered = prompt.lower()
    assert not [
        w for w in ("guard", "silent", "rule", "spark", RULE_ID) if w in lowered
    ]


def test_disagreement_records_nothing_and_logs_both_answers(tmp_path: Path) -> None:
    run = Run(tmp_path, RETURNS_ONLY, (YES, NO))
    assert run.loop.runs == [] and not cases_dir(run.registry).exists()
    [check] = run.checks()
    assert [a.yes for a in check.answers] == [True, False] and check.case_key is None


def test_a_rule_that_flagged_the_merge_is_not_judged(tmp_path: Path) -> None:
    run = Run(tmp_path, STRUCTURAL, (YES, YES))
    assert run.spark.prompts == [] and run.checks() == []


def test_a_rule_without_a_confirmed_root_is_not_judged(tmp_path: Path) -> None:
    run = Run(tmp_path, RETURNS_ONLY, (YES, YES), status="Inferred")
    assert run.spark.prompts == [] and run.loop.runs == []


def test_the_prompt_shows_the_change_as_a_diff() -> None:
    from knack.contracts.models import Root
    from knack.watch.selfcheck import FileEdit

    edit = FileEdit(number=9, file="pkg/loader.py", before=BASE, after=AFTER)
    prompt = judge_prompt(Root.model_validate(ROOT), edit)
    assert "--- a/pkg/loader.py" in prompt and "+++ b/pkg/loader.py" in prompt
