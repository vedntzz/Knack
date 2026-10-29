from knack.pipeline.models import PullRequest, PullSummary, Selection
from knack.pipeline.ports import GitHub

# A short description rarely records a decision worth reading.
MIN_BODY = 400
MAX_PYTHON_FILES = 5
DOC_SUFFIXES = (".rst", ".md", ".txt")


def select_prs(github: GitHub, repo: str, limit: int) -> Selection:
    # Pulls summaries lazily, newest first, until limit PRs qualify.
    read, kept = 0, list[PullRequest]()
    for summary in github.merged_prs(repo):
        read += 1
        kept += _qualified(github, repo, summary)
        if len(kept) >= limit:
            break
    return Selection(read=read, prs=kept)


def qualifies(paths: list[str]) -> bool:
    # One to five Python files, and not a tests-or-docs-only change.
    python = [path for path in paths if path.endswith(".py")]
    source = [path for path in paths if not (is_test(path) or is_doc(path))]
    return 1 <= len(python) <= MAX_PYTHON_FILES and bool(source)


def is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    in_tests = path.startswith("tests/") or "/tests/" in path
    return in_tests or name.startswith("test_") or name == "conftest.py"


def is_doc(path: str) -> bool:
    in_docs = path.startswith("docs/") or "/docs/" in path
    return in_docs or path.endswith(DOC_SUFFIXES)


def _qualified(github: GitHub, repo: str, summary: PullSummary) -> list[PullRequest]:
    # The body check runs first so short PRs cost no file listing.
    if len(summary.body) <= MIN_BODY:
        return []
    paths = github.changed_files(repo, summary.number)
    return [_pull_request(github, repo, summary, paths)] if qualifies(paths) else []


def _pull_request(
    github: GitHub, repo: str, summary: PullSummary, paths: list[str]
) -> PullRequest:
    base_sha, head_sha = github.shas(repo, summary.number)
    python = [path for path in paths if path.endswith(".py")]
    fields = {"base_sha": base_sha, "head_sha": head_sha, "python_files": python}
    return PullRequest.model_validate({**summary.model_dump(), **fields})
