# Precision spike: how much of today's airflow main does each compiled rule flag?
import json, subprocess
from pathlib import Path

from knack.guard.runner import AST_GREP, SUCCESS_EXIT_CODES

RULES = Path(__file__).parent / "batch" / "rules"
CLONE = Path("/tmp/airflow-main")
REPO = "https://github.com/apache/airflow.git"


def shallow_clone():
    # reuse an existing clone so reruns don't download airflow again
    if not (CLONE / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", "main", REPO, str(CLONE)], check=True)


def scan_tree(rule_path):
    # the runner's 2s timeout is for single files; a whole-repo scan gets 10 minutes
    args = [str(AST_GREP), "scan", "--rule", str(rule_path), "--json", str(CLONE)]
    done = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if done.returncode not in SUCCESS_EXIT_CODES:
        raise RuntimeError(f"ast-grep exited {done.returncode}: {done.stderr}")
    matches = [m for m in json.loads(done.stdout or "[]") if m["file"].endswith(".py")]
    return sorted(matches, key=lambda m: (m["file"], m["range"]["start"]["line"]))


def describe(match):
    where = f"{Path(match['file']).relative_to(CLONE)}:{match['range']['start']['line'] + 1}"
    return f"    {where}  {' '.join(match['lines'].split())[:120]}"


def report(rule_path, matches):
    print(f"\n#{rule_path.stem}: {len(matches)} matches in {len({m['file'] for m in matches})} files")
    for match in matches[:3]:
        print(describe(match))


if __name__ == "__main__":
    shallow_clone()
    for rule_path in sorted(RULES.glob("*.yml")):
        try:
            report(rule_path, scan_tree(rule_path))
        except Exception as error:  # one broken rule should not hide the others
            print(f"\n#{rule_path.stem}: ERROR {error!r}")
