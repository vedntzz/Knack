import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from knack import ci_guard
from knack.roots.store import load_roots

REPO = Path(__file__).parents[1]
DATA = REPO / "data"
SCRIPT = REPO / "scripts/ci_guard.py"
WORKFLOW = REPO / ".github/workflows/knack-guard.yml"
# A file from airflow #75025's base side: it still offers bare state/start_date sort keys.
VIOLATING = (
    REPO / "scripts/fixtures/75025/base/airflow-core/src/airflow/api_fastapi"
    "/core_api/routes/public/dags.py"
)
CHANGED_AT = "airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py"
CONFIRMED_RULES = {
    "airflow/75025.yml",
    "airflow/75271.yml",
    "airflow/75774.yml",
    "fastapi/14884.yml",
    "fastapi/15515.yml",
}


def registries(data: Path) -> list[Path]:
    return sorted((data / "registry").glob("*.json"))


def rule_name(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def confirmed_root_ids() -> set[str]:
    roots = [
        r for name in ("airflow", "fastapi") for r in load_roots(DATA / "roots" / name)
    ]
    return {root.id for root in roots if root.status == "Confirmed"}


def copied_data(tmp_path: Path) -> Path:
    # registry/, rules/ and roots/ side by side, as the registries' relative paths expect.
    data = tmp_path / "data"
    for kind in ("registry", "rules", "roots"):
        shutil.copytree(DATA / kind, data / kind)
    return data


def test_every_confirmed_rule_in_both_registries_is_loaded() -> None:
    guarded, skipped = ci_guard.load_guarded(registries(DATA))
    assert {rule_name(g.rule) for g in guarded} == CONFIRMED_RULES
    assert {r.id for g in guarded for r in g.roots} == confirmed_root_ids()
    assert {g.registry.stem for g in guarded} == {"airflow", "fastapi"}
    assert skipped == []


def test_only_confirmed_roots_are_cited() -> None:
    guarded, _ = ci_guard.load_guarded(registries(DATA))
    assert {r.status for g in guarded for r in g.roots} == {"Confirmed"}


def test_a_changed_byte_in_a_rule_drops_it_with_a_listed_reason(tmp_path: Path) -> None:
    data = copied_data(tmp_path)
    rule = data / "rules/airflow/75271.yml"
    rule.write_bytes(rule.read_bytes() + b"\n")
    guarded, skipped = ci_guard.load_guarded(registries(data))
    assert "airflow/75271.yml" not in {rule_name(g.rule) for g in guarded}
    assert {rule_name(g.rule) for g in guarded} == CONFIRMED_RULES - {
        "airflow/75271.yml"
    }
    assert {s.root_id for s in skipped} == {"airflow-75271-1", "airflow-75271-2"}
    assert all("sha256" in s.reason and "pin" in s.reason for s in skipped)


def test_an_unpinned_confirmed_root_is_skipped_and_listed(tmp_path: Path) -> None:
    data = copied_data(tmp_path)
    root_file = data / "roots/fastapi/14884-1.json"
    raw = json.loads(root_file.read_text(encoding="utf-8"))
    del raw["rule_sha"]
    root_file.write_text(json.dumps(raw), encoding="utf-8")
    guarded, skipped = ci_guard.load_guarded(registries(data))
    assert "fastapi/14884.yml" not in {rule_name(g.rule) for g in guarded}
    assert [(s.root_id, s.reason) for s in skipped] == [
        ("fastapi-14884-1", "unpinned: Confirmed with no rule sha256")
    ]


def test_only_changed_python_outside_fixtures_is_guarded() -> None:
    assert ci_guard.guarded_path("knack/guard/check.py")
    assert ci_guard.guarded_path("tests/foo_fixtures/x.py")
    assert not ci_guard.guarded_path("README.md")
    assert not ci_guard.guarded_path("scripts/fixtures/75025/base/x.py")
    assert not ci_guard.guarded_path("tests/guard/fixtures/violating.py")
    assert not ci_guard.guarded_path("data/variants/airflow/75025/violation_1.py")
    assert not ci_guard.guarded_path("spikes/batch/apache-airflow/src/75025/v.py")
    assert not ci_guard.guarded_path("mockups/fixtures/self_repair/edits/miss.after.py")


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def pr_clone(tmp_path: Path) -> tuple[Path, str]:
    # A clone whose base commit has only a README; the PR adds files on top.
    clone = tmp_path / "clone"
    clone.mkdir()
    git(clone, "init", "-q")
    git(clone, "config", "user.email", "ci@example.com")
    git(clone, "config", "user.name", "ci")
    (clone / "README.md").write_text("base\n", encoding="utf-8")
    git(clone, "add", ".")
    git(clone, "commit", "-qm", "base")
    return clone, git(clone, "rev-parse", "HEAD")


def commit(clone: Path, path: str, source: Path | str) -> None:
    target = clone / path
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source if isinstance(source, str) else source.read_text(encoding="utf-8")
    target.write_text(text, encoding="utf-8")
    git(clone, "add", ".")
    git(clone, "commit", "-qm", f"add {path}")


def run_guard(clone: Path, base: str) -> subprocess.CompletedProcess[str]:
    # The workflow's call: the script, the PR base, the committed registries.
    args = [sys.executable, str(SCRIPT), "--base", base]
    args += ["--registry-dir", str(DATA / "registry")]
    env = {
        k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "PR_NUMBER")
    }
    return subprocess.run(
        args, cwd=clone, capture_output=True, text=True, timeout=120, env=env
    )


def test_a_file_matching_airflow_75025_fails_the_run(
    pr_clone: tuple[Path, str],
) -> None:
    clone, base = pr_clone
    commit(clone, CHANGED_AT, VIOLATING)
    done = run_guard(clone, base)
    root = next(
        r for r in load_roots(DATA / "roots/airflow") if r.id == "airflow-75025-1"
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "airflow-75025" in done.stdout
    assert root.id in done.stdout
    assert root.decided_by in done.stdout
    assert root.quote in done.stdout
    assert f"{CHANGED_AT}:132" in done.stdout
    blocks = [line for line in done.stdout.splitlines() if line.startswith("BLOCK")]
    assert len(blocks) == len(set(blocks))


def test_a_clean_change_passes_and_names_what_it_checked(
    pr_clone: tuple[Path, str],
) -> None:
    clone, base = pr_clone
    commit(clone, "app/clean.py", "def ok() -> int:\n    return 1\n")
    done = run_guard(clone, base)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "app/clean.py" in done.stdout
    assert "5 rule(s), 7 Confirmed root(s)" in done.stdout


def test_a_deleted_or_fixture_file_is_not_scanned(pr_clone: tuple[Path, str]) -> None:
    clone, base = pr_clone
    commit(clone, "scripts/fixtures/75025/dags.py", VIOLATING)
    assert run_guard(clone, base).returncode == 0


def test_workflow_runs_the_all_roots_guard_and_reads_no_receipts() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/ci_guard.py" in text
    assert "--base" in text
    assert "guard_changed.sh" not in text
    assert "root_75025" not in text
    for local in ("receipts", "KNACK_HOME", ".knack", "~/"):
        assert local not in text


def test_the_guard_module_reads_no_local_state() -> None:
    source = (REPO / "knack/ci_guard.py").read_text(encoding="utf-8")
    for local in ("receipts", "knack_home", "KNACK_HOME", "home_registry"):
        assert local not in source
