import sys
from pathlib import Path

import pytest

# bench/ is not an installed package; the repo root makes bench.pilot importable.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sleep_rule() -> Path:
    return FIXTURES / "sleep_rule.yml"


@pytest.fixture
def accepted_rule() -> Path:
    return FIXTURES / "async_sleep_rule.yml"
