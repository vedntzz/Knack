"""The real knack CLI with GitHub and Spark swapped for test fakes holding apache/airflow#75025."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests" / "pipeline"))

from conftest import FakeGitHub, FakeSpark  # noqa: E402
from knack import cli  # noqa: E402
from knack.contracts.models import Root  # noqa: E402
from knack.dispute.argue import argue  # noqa: E402
from knack.pipeline.models import Post, PullSummary  # noqa: E402
from knack.roots.store import load_roots  # noqa: E402

PR = 75025
# Every file the run reads is committed here: base, head, variants, the PR body.
SRC = REPO_ROOT / "scripts" / "fixtures" / str(PR)
ROUTES = "airflow-core/src/airflow/api_fastapi/core_api/routes"
CHANGED = [f"{ROUTES}/public/dags.py", f"{ROUTES}/ui/dags.py"]
RULE = REPO_ROOT / "data" / "rules" / "airflow" / f"{PR}.yml"
TITLE = "Remove two Dag list sort options that never worked"
QUOTE = "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
# The real PR description, verbatim from GitHub; it holds QUOTE.
BODY = (SRC / "pr_body.md").read_text()
DECISION = {
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
}
OBJECTION = (
    "The frontend still sends order_by=state. Let me alias state and start_date onto "
    "DagRun.state and DagRun.start_date so those sorts work again."
)


def variant_set(folder: str) -> str:
    # Three of each, the count the variant parser requires.
    found = {kind: three(SRC / folder, kind) for kind in ("violation", "compliant")}
    return json.dumps(
        {"violations": found["violation"], "compliant": found["compliant"]}
    )


def three(side: Path, kind: str) -> list[str]:
    return [(side / f"{kind}_{n}.py").read_text() for n in (1, 2, 3)]


class AirflowGitHub(FakeGitHub):
    # One merged PR, #75025; main is its head, base and head come from SRC.
    def merged_prs(self, repo: str):
        yield self.summary(repo, PR)

    def summary(self, repo: str, number: int) -> PullSummary:
        return PullSummary(
            number=PR,
            title=TITLE,
            author="Pushkal-Gupta",
            body=BODY,
            merged_at="2026-10-19",
        )

    def changed_files(self, repo: str, number: int) -> list[str]:
        return CHANGED

    def posts(self, repo: str, number: int) -> list[Post]:
        return [Post(heading="Review by bbovenzi (APPROVED)", body="Looks good.")]

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        side = SRC / sha.removesuffix(str(PR)) / path
        return side.read_text() if side.is_file() else None


class AirflowSpark(FakeSpark):
    # Extracts the decision, compiles the installed rule, writes training then held-out variants.
    def __init__(self) -> None:
        super().__init__([RULE.read_text()])
        self.variants = [
            variant_set("variants-train"),
            variant_set("variants-heldout"),
        ]

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt.startswith("You compile"):
            return self.rules[0]
        if prompt.startswith("You write test cases"):
            return self.variants.pop(0) if len(self.variants) > 1 else self.variants[0]
        return json.dumps({"decisions": [DECISION]})


def fake_clients(extractor: str = "spark") -> tuple[AirflowGitHub, AirflowSpark]:
    return AirflowGitHub(SRC / "head"), AirflowSpark()


def run_cli(argv: list[str]) -> int:
    # Only the client constructors change; every command runs the real code.
    cli.live_clients = fake_clients
    cli.adversary_client = no_adversary
    return cli.main(argv)


def no_adversary(extractor: str, adversary: str | None) -> None:
    # The compiler writes its own held-out set, as with no partner key.
    return None


def hold_ruling(prompt: str) -> str:
    # Fake Spark: holds, citing the Confirmed quote verbatim.
    reply = "The team removed these sort keys instead of aliasing them."
    return json.dumps({"decision": "hold", "reply": reply, "cited_quotes": [QUOTE]})


def run_argue(roots_dir: str) -> int:
    roots: list[Root] = load_roots(Path(roots_dir))
    ruling = argue(OBJECTION, roots, ask=hold_ruling)
    print(ruling.model_dump_json())
    return 0 if ruling.decision == "hold" else 1


if __name__ == "__main__":
    command, *rest = sys.argv[1:]
    sys.exit(run_argue(*rest) if command == "argue" else run_cli([command, *rest]))
