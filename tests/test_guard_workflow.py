from knack.ci_guard import guarded_path

# The CI guard's changed-file filter: fixtures violate the rules on purpose.
FIXTURES = [
    "scripts/fixtures/75025/base/airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py",
    "tests/guard/fixtures/violating.py",
    "tests/fixtures/model_output.py",
    "tests/hooks/fixtures/edit.py",
]
REAL_CODE = [
    "knack/guard/check.py",
    "knack/fixtures/loader.py",
    "scripts/e2e_fakes.py",
    "tests/test_fixtures.py",
    "tests/guard/test_replay.py",
    "tests/foo_fixtures/x.py",
    "src/tests/fixtures/x.py",
]


def kept(paths: list[str]) -> list[str]:
    return [path for path in paths if guarded_path(path)]


def test_fixture_paths_are_not_guarded() -> None:
    assert kept(FIXTURES) == []


def test_real_code_is_still_guarded() -> None:
    assert kept(REAL_CODE) == REAL_CODE
