"""The real knack CLI with GitHub, Spark and Spark Open swapped for test fakes.

apache/airflow#75025 is real and verbatim. #900001 and #900002 are synthetic e2e PRs
(no such apache/airflow PRs exist): a loop-vs-gather decision the miss, false-block,
self-check, regression-gate and reprove loops run on.
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests" / "pipeline"))

from conftest import FakeGitHub  # noqa: E402
from knack import cli  # noqa: E402
from knack.console.app import create_app  # noqa: E402
from knack.console.verdict import home_registry_for  # noqa: E402
from knack.dispute.rulings import rulings_path  # noqa: E402
from knack.pipeline.models import Post, PullSummary  # noqa: E402
from knack.receipts.chain import receipts_path  # noqa: E402
from knack.receipts.warns import warns_path  # noqa: E402
from knack.watch import hook  # noqa: E402

FIXTURES = REPO_ROOT / "scripts" / "fixtures"
PR = 75025
LOADER_PR, TASKS_PR = 900001, 900002
ROUTES = "airflow-core/src/airflow/api_fastapi/core_api/routes"
LOADER = "airflow-core/src/airflow/utils/blob_loader.py"
RULE_75025 = REPO_ROOT / "data" / "rules" / "airflow" / f"{PR}.yml"
LOADER_RULES = FIXTURES / str(LOADER_PR) / "rules"
QUOTE = "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
LOADER_QUOTE = "gather would open every blob at once"
# The reason of the correction the regression gate must roll back; the fake extractor
# loses every decision once it reads this lesson.
BAD_LESSON = "a PR description is never a decision record"
# An objection the 75025 quotes do not answer, so Spark escalates.
ESCALATING = "deprecation window"
SPARK_OPEN = "fake-spark-open"


def summary(number: int, title: str, author: str) -> PullSummary:
    body = (FIXTURES / str(number) / "pr_body.md").read_text()
    return PullSummary(
        number=number, title=title, author=author, body=body, merged_at="2026-10-19"
    )


SUMMARIES = {
    PR: summary(
        PR, "Remove two Dag list sort options that never worked", "Pushkal-Gupta"
    ),
    LOADER_PR: summary(LOADER_PR, "Read blobs one at a time", "e2e-maria"),
    TASKS_PR: summary(TASKS_PR, "Batch blob reads behind a task list", "e2e-bo"),
}
CHANGED = {
    PR: [f"{ROUTES}/public/dags.py", f"{ROUTES}/ui/dags.py"],
    LOADER_PR: [LOADER],
    TASKS_PR: [LOADER],
}
POSTS = {
    PR: Post(heading="Review by bbovenzi (APPROVED)", body="Looks good."),
    LOADER_PR: Post(heading="Review by e2e-maria (APPROVED)", body="Loop it is."),
    TASKS_PR: Post(heading="Review by e2e-maria (APPROVED)", body="Fine."),
}
DECISIONS = {
    PR: {
        "decision": "Dag list endpoints do not accept bare state or start_date as sort keys",
        "why": "The last_run_* spelling already works; a second name for the same sort is worse",
        "decided_by": "Pushkal-Gupta",
        "rejected_alternatives": [
            {
                "alternative": "Alias state and start_date onto DagRun.state and DagRun.start_date",
                "why_rejected": "a second name for the same sort felt worse than one",
                "quote": QUOTE,
            }
        ],
    },
    LOADER_PR: {
        "decision": "Read blobs one at a time in a loop",
        "why": "gather opens every blob at once and exhausts file handles",
        "decided_by": "e2e-maria",
        "rejected_alternatives": [
            {
                "alternative": "asyncio.gather over every blob read",
                "why_rejected": "opens every blob at once",
                "quote": LOADER_QUOTE,
            }
        ],
    },
}
HOLD_REPLY = "The team removed these sort keys instead of aliasing them."
ESCALATE_REPLY = "The quotes say nothing about a deprecation window."


def variant_set(folder: Path) -> str:
    # Three of each, the count the variant parser requires.
    found = {kind: three(folder, kind) for kind in ("violation", "compliant")}
    return json.dumps(
        {"violations": found["violation"], "compliant": found["compliant"]}
    )


def three(side: Path, kind: str) -> list[str]:
    return [(side / f"{kind}_{n}.py").read_text() for n in (1, 2, 3)]


def pr_of(prompt: str) -> int:
    # Each prompt names its PR's code: the loader decision or the Dag sort keys.
    return LOADER_PR if "blob" in prompt or "gather" in prompt else PR


class AirflowGitHub(FakeGitHub):
    # Three merged PRs; init sees only #75025, watch sees the two synthetic merges.
    def merged_prs(self, repo: str):
        yield SUMMARIES[PR]

    def summary(self, repo: str, number: int) -> PullSummary:
        return SUMMARIES[number]

    def changed_files(self, repo: str, number: int) -> list[str]:
        return CHANGED[number]

    def posts(self, repo: str, number: int) -> list[Post]:
        return [POSTS[number]]

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        # base75025 -> fixtures/75025/base/<path>.
        side = sha.rstrip("0123456789")
        found = FIXTURES / sha.removeprefix(side) / side / path
        return found.read_text() if found.is_file() else None


class AirflowSpark:
    # Spark: extracts, compiles (the rule named by KNACK_E2E_RULE for #900001), writes variants, judges.
    model = "fake-spark"

    def __init__(self) -> None:
        self.variant_calls = 0

    def ask(self, prompt: str) -> str:
        if prompt.startswith("You compile"):
            return compiled(pr_of(prompt))
        if prompt.startswith("You write test cases"):
            return self.variants(pr_of(prompt))
        if prompt.startswith("A team recorded this decision"):
            return json.dumps({"takes_rejected_path": True, "why": "gather of reads"})
        return extraction(prompt)

    def variants(self, number: int) -> str:
        # Training first, then held-out, as the compiler writes them with no partner.
        self.variant_calls += 1
        held = "heldout" if self.variant_calls > 1 else "train"
        if number == PR:
            return variant_set(FIXTURES / str(PR) / f"variants-{held}")
        return variant_set(FIXTURES / "variants" / str(LOADER_PR))


class SparkOpen:
    # The other model: writes the loader's variants, agrees with every watch judge, holds every argue.
    model = SPARK_OPEN

    def ask(self, prompt: str) -> str:
        if prompt.startswith("You write test cases"):
            return variant_set(FIXTURES / "heldout" / str(LOADER_PR) / "same")
        if prompt.startswith("A team recorded this decision"):
            return json.dumps({"takes_rejected_path": True, "why": "gather of reads"})
        return json.dumps(
            {"decision": "hold", "reply": HOLD_REPLY, "cited_quotes": [QUOTE]}
        )


def compiled(number: int) -> str:
    if number == PR:
        return RULE_75025.read_text()
    name = os.environ.get("KNACK_E2E_RULE", "structural")
    return (LOADER_RULES / f"{name}.yml").read_text()


def extraction(prompt: str) -> str:
    # A bad lesson in the few-shot block loses every decision; the regression gate must notice.
    if BAD_LESSON in prompt:
        return json.dumps({"decisions": []})
    found = [n for n, pr in SUMMARIES.items() if f"Title: {pr.title}\n" in prompt]
    decision = DECISIONS.get(found[0]) if found else None
    return json.dumps({"decisions": [decision] if decision else []})


def spark_ruling(prompt: str) -> str:
    # Spark: holds on the restated alias, escalates on a case the quotes never mention.
    if ESCALATING in prompt:
        return json.dumps(
            {"decision": "escalate", "reply": ESCALATE_REPLY, "cited_quotes": []}
        )
    return json.dumps(
        {"decision": "hold", "reply": HOLD_REPLY, "cited_quotes": [QUOTE]}
    )


def fake_clients(extractor: str = "spark") -> tuple[AirflowGitHub, AirflowSpark]:
    return AirflowGitHub(FIXTURES / str(PR) / "head"), AirflowSpark()


def fake_github() -> AirflowGitHub:
    return fake_clients()[0]


def fake_adversary(extractor: str, adversary: str | None) -> SparkOpen | None:
    # Init runs with no partner key; the miss loop names its writer with --adversary.
    return SparkOpen() if adversary else None


def install_fakes() -> None:
    # Only the client constructors change; every command runs the real code.
    cli.live_clients = fake_clients
    cli.github_client = fake_github
    cli.adversary_client = fake_adversary
    cli.partner_client = lambda extractor: SparkOpen()
    cli.ask_spark = spark_ruling
    hook.live_clients = fake_clients
    hook.optional_partner = lambda extractor="spark": SparkOpen()


def edit_case(kind: str, clone: str, out: str) -> int:
    # An edit to the clone's loader as the miss loop reads it: rule, file, before, after.
    before = (Path(clone) / LOADER).read_text()
    adds = (FIXTURES / str(LOADER_PR) / "edits" / f"{kind}.py").read_text()
    imports, _, function = adds.partition("# --\n")
    body = {"rule_id": f"airflow-{LOADER_PR}", "file": LOADER, "before": before}
    Path(out).write_text(json.dumps(body | {"after": imports + before + function}))
    return 0


def console(receipt_hash: str) -> int:
    # The console's own app and routes, served in-process instead of on a port.
    from fastapi.testclient import TestClient

    app = create_app(receipts_path(), warns_path(), rulings_path(), home_registry_for)
    client = TestClient(app)
    paths = [f"/verdict/{receipt_hash}", f"/verdict/{receipt_hash}/rulings"]
    print(json.dumps({path: answered(client.get(path)) for path in paths}))
    return 0


def answered(response) -> object:
    return response.json() if response.status_code == 200 else response.status_code


if __name__ == "__main__":
    command, *rest = sys.argv[1:]
    install_fakes()
    if command == "edit-case":
        sys.exit(edit_case(*rest))
    if command == "console":
        sys.exit(console(*rest))
    if command == "watch-merged":
        sys.exit(hook.main(["post-merge", *rest]))
    sys.exit(cli.main([command, *rest]))
