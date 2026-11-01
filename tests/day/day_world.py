import json
import os
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from knack.contracts.models import Root, Verdict
from knack.day.feed import Day
from knack.dispute.rulings import append_ruling, RulingRecord
from knack.receipts.chain import (
    append_receipt,
    guard_receipt,
    Receipt,
    Resolution,
    resolution_receipt,
)
from knack.receipts.warns import record_warn

REPO = "acme/widgets"
BRANCH = "fix-sort"
NOW = datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
TODAY = "2026-11-01T09:00:00+00:00"
YESTERDAY = "2026-10-31T09:00:00+00:00"


def root_fields(
    root_id: str, status: str = "Confirmed", **extra: Any
) -> dict[str, Any]:
    # Test-only roots; values are illustrative, not quoted from a real thread.
    return {
        "id": root_id,
        "title": "Sort keys are columns",
        "decision": "Drop the aliased sort keys.",
        "why": "An alias was never sortable.",
        "decided_by": "maria",
        "source_url": f"https://github.com/{REPO}/pull/{root_id.split('-')[-1]}",
        "quote": "Sorting by an alias never worked.",
        "status": status,
        **extra,
    }


def deny_verdict(root_id: str = "root-41") -> Verdict:
    reason = "Knack blocked this edit."
    return Verdict(
        allowed=False, reason=reason, rule_id="r", root_ids=[root_id], latency_ms=2.0
    )


def allow_verdict(reason: str = "no rule matched") -> Verdict:
    return Verdict(allowed=True, reason=reason, latency_ms=1.0)


class FakePulls:
    # GitHub's REST pull objects, as the port returns them.
    def __init__(self, pulls: list[dict[str, Any]] | Exception) -> None:
        self.pulls = pulls
        self.asked: list[tuple[str, str]] = []

    def branch_pulls(self, repo: str, branch: str) -> list[dict[str, Any]]:
        self.asked.append((repo, branch))
        if isinstance(self.pulls, Exception):
            raise self.pulls
        return self.pulls


def pull(
    number: int, state: str, created: str, merged: str | None = None
) -> dict[str, Any]:
    title = f"PR {number}"
    return {
        "number": number,
        "title": title,
        "state": state,
        "created_at": created,
        "merged_at": merged,
    }


class DayWorld:
    # A git clone with an origin, a home with the three stores, and a registry.
    def __init__(self, base: Path) -> None:
        self.clone = base / "clone"
        self.home = base / "home" / ".knack"
        self.registry = base / "registry" / "registry.json"
        self.receipts = self.home / "verdicts.jsonl"
        self.warns = self.home / "warns.jsonl"
        self.rulings = self.home / "rulings.jsonl"
        self.pulls: FakePulls | None = FakePulls([])
        self._init_clone()
        self._init_registry()

    def _init_clone(self) -> None:
        self.clone.mkdir(parents=True)
        self.git("init", "-q", "-b", BRANCH)
        self.git("remote", "add", "origin", f"https://github.com/{REPO}.git")

    def _init_registry(self) -> None:
        self.registry.parent.mkdir(parents=True)
        body: dict[str, Any] = {"repo": REPO, "roots_dir": "roots", "rules": []}
        self.registry.write_text(json.dumps(body))
        self.write_root(root_fields("root-41"))

    def git(self, *args: str, date: str = TODAY) -> str:
        env = os.environ | {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        config = ["-c", "user.name=Dana Lee", "-c", "user.email=dana@example.com"]
        command = ["git", "-C", str(self.clone), *config, "-c", "commit.gpgsign=false"]
        done = subprocess.run(
            [*command, *args], env=env, capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    def commit(self, message: str, date: str = TODAY) -> str:
        self.git("commit", "-q", "--allow-empty", "-m", message, date=date)
        return self.git("rev-parse", "HEAD")

    def write_root(self, fields: dict[str, Any]) -> None:
        roots = self.registry.parent / "roots"
        roots.mkdir(parents=True, exist_ok=True)
        (roots / f"{fields['id']}.json").write_text(json.dumps(fields))

    def receipt(self, verdict: Verdict, time: str = TODAY, repo: str = REPO) -> Receipt:
        root = (
            Root.model_validate(root_fields(verdict.root_ids[0]))
            if verdict.root_ids
            else None
        )
        fields = guard_receipt(
            repo, f"{self.clone}/a.py", "r", root, verdict, time, branch=BRANCH
        )
        return append_receipt(self.receipts, fields)

    def resolve(self, deny: Receipt, time: str = TODAY) -> Receipt:
        resolution = Resolution(of=deny.hash, action="allow", by="sam", reason="ok")
        return append_receipt(self.receipts, resolution_receipt(deny, resolution, time))

    def warn(self, time: str = TODAY, repo: str = REPO) -> None:
        record_warn(self.warns, repo, self.clone, "s-1", "Knack warns: root-41", time)

    def ruling(self, deny: Receipt, decision: str, time: str = TODAY) -> None:
        fields: dict[str, Any] = {
            "time": time,
            "receipt_hash": deny.hash,
            "objection": "no",
        }
        fields |= {
            "decision": decision,
            "reply": "r",
            "cited_quotes": [],
            "model": None,
        }
        append_ruling(self.rulings, RulingRecord.model_validate(fields))

    def registry_for(self, repo: str) -> Path | None:
        return self.registry if repo == REPO else None

    def day(self) -> Day:
        return Day(
            clone=self.clone,
            clock=lambda: NOW,
            receipts=self.receipts,
            warns=self.warns,
            rulings=self.rulings,
            pulls=self.pulls,
            registry_for=self.registry_for,
        )
