import os
from pathlib import Path

import pytest
from knack.contracts.models import Root
from knack.pipeline.clients import live_clients
from knack.pipeline.extract import extract_pr
from knack.pipeline.github import API, GitHubApi, summary_from_item
from knack.pipeline.http import request_json
from knack.pipeline.init import run_init
from knack.pipeline.models import Extraction, PullRequest
from knack.pipeline.roots import roots_for
from knack.roots.corrections import Correction, few_shot_block
from knack.walk.registry import load_registry

LIVE_REPO = os.environ.get("KNACK_LIVE_REPO", "fastapi/fastapi")
# Records a verbatim rejected alternative (data/roots/airflow/75025.json).
REJECTION_REPO, REJECTION_PR = "apache/airflow", 75025

pytestmark = pytest.mark.skipif(
    os.environ.get("KNACK_LIVE") != "1",
    reason="hits GitHub and Spark; set KNACK_LIVE=1 with GITHUB_TOKEN and MODEL_API_KEY",
)


def test_live_init_writes_a_loadable_registry(tmp_path: Path) -> None:
    lines = list[str]()
    path = run_init(LIVE_REPO, 3, tmp_path, *live_clients(), log=lines.append)
    registry = load_registry(path)
    print("\n".join(lines))
    assert registry.repo == LIVE_REPO and "[5/5] install" in lines[-1]
    assert all(entry.rule.exists() for entry in registry.rules)


def verbatim_quotes(extraction: Extraction) -> set[str]:
    alternatives = [a for d in extraction.decisions for a in d.rejected_alternatives]
    return {a.quote for a in alternatives if a.verbatim}


def rejected(root: Root) -> Correction:
    after = root.model_copy(update={"status": "Unknown"})
    reason = (
        f"Not a team decision; {root.quote!r} is passing discussion. Never extract it."
    )
    fields = {"root_id": root.id, "action": "reject", "before": root, "after": after}
    return Correction.model_validate(
        {
            **fields,
            "reason": reason,
            "by": "live-test",
            "at": "2026-10-29T00:00:00+00:00",
        }
    )


def pinned_pr(github: GitHubApi) -> PullRequest:
    # Only title, author and body feed the extract prompt; shas and files do not.
    item = request_json(
        f"{API}/repos/{REJECTION_REPO}/issues/{REJECTION_PR}", github.headers
    )
    fields = summary_from_item(item).model_dump()
    return PullRequest(**fields, base_sha="", head_sha="", python_files=[])


def test_live_rejected_root_is_not_extracted_again() -> None:
    # A PR known to record a rejection: extract, reject its first root, extract again.
    github, spark = live_clients()
    pr = pinned_pr(github)
    first = extract_pr(github, spark, REJECTION_REPO, pr)
    root = roots_for(REJECTION_REPO, first, spark.model)[0]
    again = extract_pr(
        github, spark, REJECTION_REPO, pr, few_shot=few_shot_block([rejected(root)])
    )
    print(f"#{pr.number}: {verbatim_quotes(first)} -> {verbatim_quotes(again)}")
    assert again.decisions != first.decisions
    assert root.quote not in verbatim_quotes(again)
