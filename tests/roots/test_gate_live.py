import os
from functools import partial
from pathlib import Path

import pytest
from knack.contracts.models import Root
from knack.pipeline.clients import live_clients
from knack.pipeline.extract import extract_pr
from knack.pipeline.models import PullRequest
from knack.pipeline.roots import roots_for
from knack.roots.correct import reject_root
from knack.roots.gate import Gate, gated, Outcome, regressed_line
from knack.roots.store import write_root
from knack.walk.registry import Registry

# Records a verbatim rejected alternative (data/roots/airflow/75025.json).
REPO, PR = "apache/airflow", 75025
REASON = "Not a team decision; this quote is passing discussion. Never extract it."

pytestmark = pytest.mark.skipif(
    os.environ.get("KNACK_LIVE") != "1",
    reason="hits GitHub and Spark; set KNACK_LIVE=1 with GITHUB_TOKEN and MODEL_API_KEY",
)


def confirmed_live_root(gate: Gate) -> Root:
    # Read the PR live, then treat its first root as one a human confirmed.
    summary = gate.github.summary(REPO, PR).model_dump()
    pr = PullRequest(**summary, base_sha="", head_sha="", python_files=[])
    found = roots_for(REPO, extract_pr(gate.github, gate.spark, REPO, pr), "live")[0]
    return found.model_copy(update={"status": "Confirmed"})


def registry_with(out: Path, roots: list[Root]) -> Path:
    for root in roots:
        write_root(root, out / "roots" / f"{root.id}.json")
    registry = Registry(repo=REPO, roots_dir=Path("roots"), rules=[])
    (out / "registry.json").write_text(registry.model_dump_json(indent=2) + "\n")
    return out / "registry.json"


def with_decoy(out: Path, confirmed: Root) -> Path:
    # An Inferred twin of the confirmed root: same PR, same quote, its own id.
    decoy = confirmed.model_copy(update={"id": f"{confirmed.id}-decoy"})
    return registry_with(
        out, [confirmed, decoy.model_copy(update={"status": "Inferred"})]
    )


def reject_decoy(out: Path, gate: Gate, confirmed: Root) -> Outcome:
    log, decoy_id = out / "corrections.jsonl", f"{confirmed.id}-decoy"
    apply = partial(reject_root, root_id=decoy_id, reason=REASON, by="live", log=log)
    return gated(with_decoy(out, confirmed), apply, gate, log)


def test_live_reject_of_a_confirmed_quote_is_rolled_back(tmp_path: Path) -> None:
    # Rejecting the decoy teaches Spark to drop that quote; the confirmed root goes too.
    gate = Gate(*live_clients(), log=print)
    confirmed = confirmed_live_root(gate)
    outcome = reject_decoy(tmp_path, gate, confirmed)
    print("\n".join(regressed_line(root) for root in outcome.lost))
    assert [r.id for r in outcome.lost] == [confirmed.id]
    assert (tmp_path / "corrections.jsonl").read_text() == ""
