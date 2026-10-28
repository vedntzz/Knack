# Precision spike: how much of an airflow ref does each compiled rule flag?
import argparse, json, subprocess
from pathlib import Path

from knack.guard.runner import AST_GREP, SUCCESS_EXIT_CODES

RULES = Path(__file__).parent / "batch" / "rules"
REPO = "https://github.com/apache/airflow.git"


def parse_ref():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", default="main", help="airflow branch or tag to scan")
    return parser.parse_args().ref


def clone_dir(ref):
    # one folder per ref so a cached main clone is never rescanned as another ref
    return Path(f"/tmp/airflow-{ref.replace('/', '-')}")


def shallow_clone(ref, clone):
    # reuse an existing clone so reruns don't download airflow again
    if not (clone / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", ref, REPO, str(clone)], check=True)


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
    ref = parse_ref()
    clone = clone_dir(ref)
    shallow_clone(ref, clone)
    print(f"scanning airflow @ {ref} ({clone})")
    for rule_path in sorted(RULES.glob("*.yml")):
        try:
            report(rule_path, scan_tree(rule_path, clone), clone)
        except Exception as error:  # one broken rule should not hide the others
            print(f"\n#{rule_path.stem}: ERROR {error!r}")
