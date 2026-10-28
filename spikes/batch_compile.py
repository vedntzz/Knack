# Batch compile spike: can Spark turn each PR's rejected alternative into a rule that flags base, not head, not main?
import json, os, tempfile
from pathlib import Path

import requests

from batch_precision import CLONE, scan_tree, shallow_clone
from compile_spike import PROMPT, answer_text, ask_spark, scan
from q3_extract import GH

BATCH = Path(__file__).parent / "batch"
RULES = BATCH / "rules"
SRC = BATCH / "src"
TARGETS = [75774, 74150, 75271, 75734, 75025]
MAX_ATTEMPTS = 5
FP_FEEDBACK_LIMIT = 5


def gh_headers(accept="application/vnd.github+json"):
    token = os.environ.get("GITHUB_TOKEN")
    return {"Accept": accept, **({"Authorization": f"Bearer {token}"} if token else {})}


def get_json(path):
    response = requests.get(f"{GH}/{path}", headers=gh_headers(), timeout=20)
    response.raise_for_status()
    return response.json()


def pr_meta(number):
    # #75025 was an extra in batch_extract, so it is not in prs.json: fall back to the API
    known = {p["number"]: p for p in json.loads((BATCH / "prs.json").read_text())}
    if number in known:
        return known[number]
    pr, files = get_json(f"pulls/{number}"), get_json(f"pulls/{number}/files?per_page=100")
    return {"number": number, "base_sha": pr["base"]["sha"], "head_sha": pr["head"]["sha"], "changed_files": files}


def decision_with_rejection(number):
    rows = [json.loads(line) for line in (BATCH / "decisions.jsonl").read_text().splitlines() if line.strip()]
    row = next(r for r in rows if r["number"] == number)
    return next(d for d in row["decisions"] if d.get("rejected_alternatives"))


def fetch_file(number, side, sha, filename):
    # cached under batch/src/<pr>/<side>/; None when the file does not exist at that sha
    local = SRC / str(number) / side / filename
    if not local.exists():
        url = f"{GH}/contents/{filename}?ref={sha}"
        response = requests.get(url, headers=gh_headers("application/vnd.github.raw"), timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(response.text)
    return local


def fetch_side(number, meta, side):
    names = [f["filename"] for f in meta["changed_files"] if f["filename"].endswith(".py")]
    paths = {n: fetch_file(number, side, meta[f"{side}_sha"], n) for n in names}
    return {n: p for n, p in paths.items() if p is not None}


def joined_source(files):
    return "\n\n".join(f"# file: {name}\n{path.read_text()}" for name, path in files.items())


def evaluate(rule_yaml, base, head):
    results = [(f"base {n}", True, p) for n, p in base.items()] + [(f"head {n}", False, p) for n, p in head.items()]
    return [(label, should_flag, *scan(rule_yaml, path)) for label, should_flag, path in results]


def main_false_positives(rule_yaml, changed):
    # every match on airflow main outside the PR's own files; ast-grep errors are surfaced, not swallowed
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
        f.write(rule_yaml)
    try:
        matches = scan_tree(Path(f.name))
    except RuntimeError as error:
        return [], str(error)
    fps = [fp_row(m) for m in matches]
    return [fp for fp in fps if fp[0] not in changed], None


def fp_row(match):
    path = str(Path(match["file"]).relative_to(CLONE))
    return path, match["range"]["start"]["line"] + 1, " ".join(match["lines"].split())[:160]


def passes(results, fps, fp_error):
    errors = [e for *_, e in results if e]
    flagged = [(should, bool(matches)) for _, should, matches, _ in results]
    history_ok = any(f for s, f in flagged if s) and not any(f for s, f in flagged if not s)
    return not errors and not fp_error and not fps and history_ok


def report(results, fps, fp_error):
    lines = [f"{'base must flag >=1' if s else 'head must flag 0'} | {label}: "
             f"{err or ', '.join(f'{m.matched_text!r} (line {m.line})' for m in matches) or 'no matches'}"
             for label, s, matches, err in results]
    return "\n".join(lines + [main_report(fps, fp_error)])


def main_report(fps, fp_error):
    if fp_error:
        return f"airflow main must flag 0 | ERROR: {fp_error}"
    shown = "".join(f"\n  {path}:{line}  {text}" for path, line, text in fps[:FP_FEEDBACK_LIMIT])
    return f"airflow main must flag 0 outside this PR's files | {len(fps)} false positives{shown}"


def preserve_v1(number):
    # the rule from the base/head-only verifier is kept for comparison, never overwritten on rerun
    old, v1 = RULES / f"{number}.yml", RULES / f"{number}.v1.yml"
    if old.exists() and not v1.exists():
        old.rename(v1)


def compile_pr(number):
    meta = pr_meta(number)
    changed = {f["filename"] for f in meta["changed_files"]}
    base, head = fetch_side(number, meta, "base"), fetch_side(number, meta, "head")
    prompt = PROMPT.format(decision=json.dumps(decision_with_rejection(number), indent=2),
                           before=joined_source(base), after=joined_source(head))
    fps = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        rule_yaml = answer_text(ask_spark(prompt))
        results = evaluate(rule_yaml, base, head)
        fps, fp_error = main_false_positives(rule_yaml, changed)
        print(f"\n=== #{number} ATTEMPT {attempt} ===\n{rule_yaml}\n\n{report(results, fps, fp_error)}")
        if passes(results, fps, fp_error):
            (RULES / f"{number}.yml").write_text(rule_yaml)
            return attempt, []
        prompt += (f"\n\nYOUR PREVIOUS RULE:\n{rule_yaml}\n\nVERIFIER RESULTS:\n"
                   f"{report(results, fps, fp_error)}\nFix the rule.")
    return None, fps


def safe_compile(number):
    try:
        return compile_pr(number)
    except Exception as error:  # one PR's network or API failure should not sink the batch
        print(f"\n#{number} ERROR: {error!r}")
        return None, []


def summary_line(number, attempt, fps):
    if attempt:
        return f"#{number}: PASS on attempt {attempt}"
    shown = "".join(f"\n    {path}:{line}  {text}" for path, line, text in fps[:FP_FEEDBACK_LIMIT])
    return f"#{number}: FAIL ({len(fps)} false positives on main remaining){shown}"


if __name__ == "__main__":
    shallow_clone()
    RULES.mkdir(parents=True, exist_ok=True)
    for number in TARGETS:
        preserve_v1(number)
    outcomes = {n: safe_compile(n) for n in TARGETS}
    print("\n=== SUMMARY ===")
    for number, (attempt, fps) in outcomes.items():
        print(summary_line(number, attempt, fps))
    print(f"total: {sum(1 for a, _ in outcomes.values() if a)} / {len(TARGETS)}")
