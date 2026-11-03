"""CI guard: every Confirmed root with a holding pin, run on a pull request's changed files.

Reads committed registries, rules and roots only; nothing local to one machine.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from knack.contracts.models import Root
from knack.guard.pr_comment import comment_on_block, pull_request_from_env
from knack.guard.runner import RuleMatch, scan_file_with_rule
from knack.roots.pin import rule_sha
from knack.roots.store import root_files
from knack.walk.registry import load_registry

# Fixtures and committed evidence (variants, held-out sets, spikes) violate rules on purpose.
FIXTURE = re.compile(
    r"^(scripts/fixtures/|tests/(.*/)?fixtures/|mockups/fixtures/|data/|spikes/)"
)
DEFAULT_REGISTRY_DIR = Path("data/registry")
EXIT_BLOCKED = 1
EXIT_ERROR = 2


@dataclass(frozen=True)
class Guarded:
    # One rule and the Confirmed roots whose pin matches its bytes.
    registry: Path
    rule: Path
    roots: list[Root]
    root_paths: list[Path]


@dataclass(frozen=True)
class Skipped:
    root_id: str
    rule: Path
    reason: str


@dataclass(frozen=True)
class Hit:
    guarded: Guarded
    match: RuleMatch
    file: str


def guarded_path(path: str) -> bool:
    return path.endswith(".py") and not FIXTURE.match(path)


def load_guarded(registries: Sequence[Path]) -> tuple[list[Guarded], list[Skipped]]:
    guarded = list[Guarded]()
    skipped = list[Skipped]()
    for path in registries:
        found, dropped = _guarded_in(path)
        guarded += found
        skipped += dropped
    return guarded, skipped


def _guarded_in(path: Path) -> tuple[list[Guarded], list[Skipped]]:
    registry = load_registry(path)
    by_id = {root.id: (file, root) for file, root in root_files(registry.roots_dir)}
    guarded = list[Guarded]()
    skipped = list[Skipped]()
    for entry in registry.rules:
        sha = rule_sha(entry.rule) if entry.rule.is_file() else None
        kept = list[tuple[Path, Root]]()
        for root_id in entry.root_ids:
            pair = by_id.get(root_id)
            if pair is None or pair[1].status != "Confirmed":
                continue
            reason = _skip_reason(pair[1], sha)
            if reason:
                skipped.append(Skipped(root_id, entry.rule, reason))
            else:
                kept.append(pair)
        if kept:
            roots = [root for _, root in kept]
            files = [file for file, _ in kept]
            guarded.append(Guarded(path, entry.rule, roots, files))
    return guarded, skipped


def _skip_reason(root: Root, sha: str | None) -> str | None:
    if sha is None:
        return "rule file missing"
    if root.rule_sha is None:
        return "unpinned: Confirmed with no rule sha256"
    if root.rule_sha != sha:
        return f"rule sha256 {sha[:12]} does not match pin {root.rule_sha[:12]}"
    return None


def changed_files(base: str, head: str) -> list[str]:
    # Added, copied, modified and renamed files; a deleted file has nothing to scan.
    args = ["git", "diff", "--name-only", "--diff-filter=d", f"{base}...{head}"]
    done = subprocess.run(args, capture_output=True, text=True, check=True)
    return [line for line in done.stdout.splitlines() if guarded_path(line)]


def scan(guarded: Sequence[Guarded], files: Sequence[str]) -> list[Hit]:
    # A scan error raises: CI is the backstop, so it fails closed, unlike the hook.
    hits = dict[tuple[str, Path, int], Hit]()
    for file in files:
        for rule in guarded:
            for match in scan_file_with_rule(Path(file), rule.rule):
                hits.setdefault((file, rule.rule, match.line), Hit(rule, match, file))
    return list(hits.values())


def hit_text(hit: Hit) -> str:
    lines = [f"BLOCK {hit.match.rule_id} at {hit.file}:{hit.match.line}"]
    lines.append(f"  rule: {hit.guarded.rule}")
    for root in hit.guarded.roots:
        lines.append(f"  root: {root.id} ({root.status})")
        lines.append(f"    decided by: {root.decided_by}")
        lines.append(f'    quote: "{root.quote}"')
        lines.append(f"    source: {root.source_url}")
    return "\n".join(lines)


def comment_quietly(hits: Sequence[Hit], env: Mapping[str, str]) -> None:
    # One review comment per blocked file and rule, citing its first root; best effort.
    if pull_request_from_env(env) is None:
        return
    log = Path(tempfile.gettempdir()) / "knack-ci-guard.log"
    done = set[tuple[str, Path]]()
    for hit in hits:
        key = (hit.file, hit.guarded.rule)
        if key in done:
            continue
        done.add(key)
        try:
            comment_on_block(
                Path(hit.file), hit.guarded.rule, hit.guarded.root_paths[0], env, log
            )
        except Exception as error:
            print(f"comment not posted for {hit.file}: {error}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registries = sorted(args.registry_dir.glob("*.json"))
    guarded, skipped = load_guarded(registries)
    roots = sum(len(g.roots) for g in guarded)
    print(f"knack ci guard: {len(guarded)} rule(s), {roots} Confirmed root(s)")
    for rule in guarded:
        print(f"  guarding {rule.rule} for {', '.join(r.id for r in rule.roots)}")
    for skip in skipped:
        print(f"  skipped {skip.root_id} ({skip.rule}): {skip.reason}")
    files = args.files or changed_files(args.base, args.head)
    print(f"changed .py files: {len(files)}")
    for file in files:
        print(f"  {file}")
    try:
        hits = scan(guarded, files)
    except Exception as error:
        print(f"guard error, failing closed: {type(error).__name__}: {error}")
        return EXIT_ERROR
    for hit in hits:
        print(hit_text(hit))
    if not hits:
        print("no Confirmed rule matched")
        return 0
    comment_quietly(hits, os.environ)
    return EXIT_BLOCKED


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ci_guard", description=__doc__)
    parser.add_argument("--base", default="origin/main", help="PR base commit")
    parser.add_argument("--head", default="HEAD", help="PR head commit")
    parser.add_argument("--registry-dir", type=Path, default=DEFAULT_REGISTRY_DIR)
    parser.add_argument("files", nargs="*", help="files to scan instead of the diff")
    return parser


if __name__ == "__main__":
    sys.exit(main())
