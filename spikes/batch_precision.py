# Precision spike: how much of a repo ref does each compiled rule flag?
import json, subprocess
from pathlib import Path

from batch_repo import Batch, default_branch, repo_parser
from knack.guard.runner import AST_GREP, SUCCESS_EXIT_CODES


def parse_args(argv=None):
    parser = repo_parser("scan a repo ref with every compiled rule")
    parser.add_argument("--ref", help="branch or tag to scan (default: the repo's default branch)")
    return parser.parse_args(argv)


def resolve_ref(batch, ref):
    # an explicit --ref wins and skips the API call
    return ref or default_branch(batch)


def clone_dir(batch, ref):
    # one folder per repo and ref so a cached main clone is never rescanned as another ref
    return Path(f"/tmp/{batch.slug}-{ref.replace('/', '-')}")


def shallow_clone(batch, ref, clone):
    # reuse an existing clone so reruns don't download the repo again
    if not (clone / ".git").exists():
        argv = ["git", "clone", "--depth", "1", "--branch", ref, batch.clone_url, str(clone)]
        subprocess.run(argv, check=True)


def scan_tree(rule_path, clone):
    # the runner's 2s timeout is for single files; a whole-repo scan gets 10 minutes
    args = [str(AST_GREP), "scan", "--rule", str(rule_path), "--json", str(clone)]
    done = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if done.returncode not in SUCCESS_EXIT_CODES:
        raise RuntimeError(f"ast-grep exited {done.returncode}: {done.stderr}")
    matches = [m for m in json.loads(done.stdout or "[]") if m["file"].endswith(".py")]
    return sorted(matches, key=lambda m: (m["file"], m["range"]["start"]["line"]))


def describe(match, clone):
    where = f"{Path(match['file']).relative_to(clone)}:{match['range']['start']['line'] + 1}"
    return f"    {where}  {' '.join(match['lines'].split())[:120]}"


def report(rule_path, matches, clone):
    print(f"\n#{rule_path.stem}: {len(matches)} matches in {len({m['file'] for m in matches})} files")
    for match in matches[:3]:
        print(describe(match, clone))


if __name__ == "__main__":
    args = parse_args()
    batch = Batch(args.repo)
    ref = resolve_ref(batch, args.ref)
    clone = clone_dir(batch, ref)
    shallow_clone(batch, ref, clone)
    print(f"scanning {batch.repo} @ {ref} ({clone})")
    for rule_path in sorted(batch.rules.glob("*.yml")):
        try:
            report(rule_path, scan_tree(rule_path, clone), clone)
        except Exception as error:  # one broken rule should not hide the others
            print(f"\n#{rule_path.stem}: ERROR {error!r}")
