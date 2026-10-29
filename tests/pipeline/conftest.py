import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from knack.pipeline import stages
from knack.pipeline.models import Post, PullSummary

REPO = "acme/widgets"
LONG = "Context for reviewers. " * 20
BASE = """import asyncio


async def load(items):
    results = await asyncio.gather(*[i.read() for i in items])
    return results
"""
HEAD = """async def load(items):
    results = []
    for item in items:
        results.append(await item.read())
    return results
"""
TEST_FILE = "def test_load():\n    assert True\n"
QUOTE = "gather would open every blob at once"
REVIEW = f"Please don't: {QUOTE} and we hit the fd limit."
# flags base; allows head only because head spells the PR's new name `append`
MEMORIZED = """id: compiled-rule
language: python
severity: error
message: m
rule:
  kind: function_definition
  not: {has: {regex: append, stopBy: end}}
"""
STRUCTURAL = """id: compiled-rule
language: python
severity: error
message: Read blobs one at a time.
rule: {pattern: $R = await asyncio.gather($$$)}
"""
# STRUCTURAL catches violations 1 and 3 but not the bare return in 2
VIOLATIONS = [
    "import asyncio\n\nasync def fetch_all(blobs):\n    data = await asyncio.gather(*(b.read() for b in blobs))\n    return data\n",
    "import asyncio\n\nasync def grab(files):\n    return await asyncio.gather(*[f.read() for f in files])\n",
    "import asyncio\n\nasync def pull(srcs):\n    chunks = await asyncio.gather(srcs[0].read(), srcs[1].read())\n    return chunks\n",
]
COMPLIANT = [
    "async def fetch_all(blobs):\n    data = []\n    for b in blobs:\n        data.append(await b.read())\n    return data\n",
    "async def grab(files):\n    return [await f.read() for f in files]\n",
    "async def pull(srcs):\n    first = await srcs[0].read()\n    second = await srcs[1].read()\n    return first, second\n",
]
VARIANTS = json.dumps({"violations": VIOLATIONS, "compliant": COMPLIANT})
# The adversary's held-out set; STRUCTURAL catches 1 and 3, not the bare return in 2
HELDOUT_VIOLATIONS = [
    "import asyncio\n\nasync def sip_heldout(jars):\n    got = await asyncio.gather(*[j.read() for j in jars])\n    return got\n",
    "import asyncio\n\nasync def gulp_heldout(jars):\n    return await asyncio.gather(*(j.read() for j in jars))\n",
    "import asyncio\n\nasync def sup_heldout(a, b):\n    pair = await asyncio.gather(a.read(), b.read())\n    return pair\n",
]
HELDOUT_COMPLIANT = [
    "async def sip_heldout(jars):\n    got = []\n    for j in jars:\n        got.append(await j.read())\n    return got\n",
    "async def gulp_heldout(jars):\n    return [await j.read() for j in jars]\n",
    "async def sup_heldout(a, b):\n    return await a.read(), await b.read()\n",
]
HELDOUT = json.dumps({"violations": HELDOUT_VIOLATIONS, "compliant": HELDOUT_COMPLIANT})
GATHER_DECISION = {
    "decision": "Read blobs one at a time in a loop",
    "why": "gather opens every blob at once and exhausts file handles",
    "decided_by": "maria",
    "rejected_alternatives": [
        {
            "alternative": "asyncio.gather over every read",
            "why_rejected": "opens every blob at once",
            "quote": QUOTE,
        }
    ],
}
NO_REJECTION = {"decision": "Keep it", "why": "fine", "decided_by": "bo"}
INVENTED = {
    **NO_REJECTION,
    "rejected_alternatives": [
        {"alternative": "x", "why_rejected": "y", "quote": "never said"}
    ],
}


def summary(number: int, title: str, body: str = LONG) -> PullSummary:
    return PullSummary(
        number=number, title=title, author="maria", body=body, merged_at="2026-10-01"
    )


# newest first, as GitHub returns them
SUMMARIES = [
    summary(9, "Read blobs one at a time"),
    summary(8, "Tiny fix", body="short"),
    summary(7, "Docs only"),
    summary(6, "Tests only"),
    summary(5, "Six modules"),
    summary(4, "Plain refactor"),
    summary(3, "Invented quote"),
    summary(2, "Spark babbles"),
]
FILES = {
    9: ["pkg/loader.py", "tests/test_loader.py"],
    7: ["docs/index.md", "README.md"],
    6: ["tests/test_a.py", "pkg/tests/test_b.py"],
    5: [f"pkg/m{i}.py" for i in range(6)],
    4: ["pkg/refactor.py"],
    3: ["pkg/invented.py"],
    2: ["pkg/babble.py"],
}
EXTRACTIONS = {
    "Read blobs one at a time": json.dumps({"decisions": [GATHER_DECISION]}),
    "Plain refactor": "```json\n" + json.dumps({"decisions": [NO_REJECTION]}) + "\n```",
    "Invented quote": json.dumps({"decisions": [INVENTED]}),
    "Spark babbles": "I think this PR is great!",
}


class FakeGitHub:
    # One small repo history; counts how many PR summaries were pulled.
    def __init__(self, tree: Path) -> None:
        self.tree, self.summaries_read, self.checkouts = tree, 0, 0
        # No release tags unless a test gives some, so no old-release check.
        self.tag_names, self.tag_reads = dict[str, str](), 0
        self.old_trees, self.refs_checked_out = dict[str, Path](), list[str]()

    def merged_prs(self, repo: str) -> Iterator[PullSummary]:
        for pr in SUMMARIES:
            self.summaries_read += 1
            yield pr

    def summary(self, repo: str, number: int) -> PullSummary:
        return next(pr for pr in SUMMARIES if pr.number == number)

    def changed_files(self, repo: str, number: int) -> list[str]:
        return FILES.get(number, [])

    def shas(self, repo: str, number: int) -> tuple[str, str]:
        return f"base{number}", f"head{number}"

    def posts(self, repo: str, number: int) -> list[Post]:
        return [Post(heading="Review by maria (CHANGES_REQUESTED)", body=REVIEW)]

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        sources = {"base9": {"pkg/loader.py": BASE}}
        sources["head9"] = {"pkg/loader.py": HEAD, "tests/test_loader.py": TEST_FILE}
        return sources.get(sha, {}).get(path)

    def checkout(self, repo: str, dest: Path) -> Path:
        self.checkouts += 1
        return self.tree

    def tags(self, repo: str) -> dict[str, str]:
        self.tag_reads += 1
        return self.tag_names

    def checkout_ref(self, repo: str, ref: str, dest: Path) -> Path:
        self.refs_checked_out.append(ref)
        return self.old_trees[ref]


class FakeSpark:
    # Answers by prompt kind; compile answers are served in order, the last repeats.
    model = "fake-spark"

    def __init__(self, rules: list[str]) -> None:
        self.rules, self.prompts = rules, list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt.startswith("You compile"):
            return self.rules.pop(0) if len(self.rules) > 1 else self.rules[0]
        if prompt.startswith("You write test cases"):
            return VARIANTS
        return next(a for t, a in EXTRACTIONS.items() if f"Title: {t}\n" in prompt)

    def compile_prompts(self) -> list[str]:
        return [p for p in self.prompts if p.startswith("You compile")]


class FakeAdversary:
    # Writes variants only: the training set first, then the held-out set.
    model = "fake-adversary"

    def __init__(self, *answers: str) -> None:
        self.answers, self.prompts = list(answers or (VARIANTS, HELDOUT)), list[str]()

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers[min(len(self.prompts), len(self.answers)) - 1]


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


def clean_tree(tmp_path: Path) -> Path:
    # The default branch: head's loader plus unrelated code.
    files = {"pkg/loader.py": HEAD, "pkg/util.py": "def add(a, b):\n    return a + b\n"}
    return write_tree(tmp_path / "tree", files)


ORIGIN = "https://github.com/acme/widgets.git"
SQUASH_SUBJECT = "Read blobs one at a time (#9)"


@pytest.fixture
def isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # No user or system git config (hooksPath, identity) leaks into a test.
    empty = tmp_path / "gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "maria")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "maria@example.com")


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    return done.stdout + done.stderr


def make_repo(path: Path) -> Path:
    # A clone of acme/widgets on main, holding the pre-PR loader.
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "remote", "add", "origin", ORIGIN)
    write_tree(path, {"pkg/loader.py": BASE, "pkg/util.py": "X = 1\n"})
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "Initial layout")
    return path


def merge_pr(repo: Path, subject: str = SQUASH_SUBJECT, no_ff: bool = False) -> str:
    # A real merge of a feature branch that swaps gather for a loop; returns git's output.
    git(repo, "checkout", "-q", "-b", "feature")
    write_tree(repo, {"pkg/loader.py": HEAD})
    git(repo, "commit", "-q", "-am", subject)
    git(repo, "checkout", "-q", "main")
    if no_ff:
        return git(
            repo,
            "merge",
            "--no-ff",
            "-m",
            "Merge pull request #9 from acme/feature",
            "feature",
        )
    return git(repo, "merge", "--ff-only", "feature")


@pytest.fixture(autouse=True)
def corrections(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    # The pipeline never reads the real ~/.knack/corrections.jsonl in a test.
    path = tmp_path / "corrections.jsonl"
    monkeypatch.setattr(stages, "corrections_path", lambda: path)
    return path
