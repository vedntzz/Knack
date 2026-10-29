import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from knack.pipeline import init
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

    def merged_prs(self, repo: str) -> Iterator[PullSummary]:
        for pr in SUMMARIES:
            self.summaries_read += 1
            yield pr

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


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


def clean_tree(tmp_path: Path) -> Path:
    # The default branch: head's loader plus unrelated code.
    files = {"pkg/loader.py": HEAD, "pkg/util.py": "def add(a, b):\n    return a + b\n"}
    return write_tree(tmp_path / "tree", files)


@pytest.fixture(autouse=True)
def corrections(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    # The pipeline never reads the real ~/.knack/corrections.jsonl in a test.
    path = tmp_path / "corrections.jsonl"
    monkeypatch.setattr(init, "corrections_path", lambda: path)
    return path
