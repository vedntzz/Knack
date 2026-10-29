# Batch compile spike: can Spark turn each PR's rejected alternative into a rule that flags base, not head, not main?
import json, os, random, tempfile
from pathlib import Path

import requests

from batch_precision import clone_dir, resolve_ref, scan_tree, shallow_clone
from batch_repo import Batch, repo_parser
from batch_variants import variant_files, variant_prompt
from batch_rename import fresh_names, introduced_identifiers, rename_locals, rename_names
from compile_spike import PROMPT as BASE_PROMPT, answer_text, ask_spark, scan

# Airflow keeps its hand-picked five; other repos compile every PR whose extraction found a rejection
TARGETS = {"apache/airflow": [75774, 74150, 75271, 75734, 75025]}
MAX_ATTEMPTS = 5
FP_FEEDBACK_LIMIT = 5
GENERALITY = "Do not match identifiers introduced by this PR; match the structure of the violation.\n"
PROMPT = BASE_PROMPT.replace("Use id: compiled-rule.", GENERALITY + "Use id: compiled-rule.")
# whether each verifier side must flag (True) or never flag (False)
MUST_FLAG = {"base": True, "head": False, "rename-base": True, "rename-head": False,
             "variant-violation": True, "variant-compliant": False}
# files a must-flag side needs flagged; 1 unless listed
MIN_FLAGGED = {"variant-violation": 2}
SIDE_NOTES = {"base": "", "head": "", "rename-base": " (base with its local variables renamed)",
              "rename-head": " (head with every identifier this PR introduced renamed to _r... names)",
              "variant-violation": " (fresh violation written apart from the PR; >=2 of 3 must be flagged)",
              "variant-compliant": " (fresh compliant code written apart from the PR)"}
VARIANT_MISSES = {"variant-violation": "MISSED VIOLATION (the rule must flag this)",
                  "variant-compliant": "FLAGGED COMPLIANT CODE (the rule must allow this)"}


def parse_args(argv=None):
    parser = repo_parser("compile each target PR's rejected alternative into a rule")
    parser.add_argument("--ref", help="branch scanned for false positives (default: the repo's default branch)")
    return parser.parse_args(argv)


def decision_rows(batch):
    return [json.loads(line) for line in batch.decisions.read_text().splitlines() if line.strip()]


def targets(batch):
    if batch.repo in TARGETS:
        return TARGETS[batch.repo]
    return [r["number"] for r in decision_rows(batch) if any(d.get("rejected_alternatives") for d in r["decisions"])]


def gh_headers(accept="application/vnd.github+json"):
    token = os.environ.get("GITHUB_TOKEN")
    return {"Accept": accept, **({"Authorization": f"Bearer {token}"} if token else {})}


def get_json(batch, path):
    response = requests.get(f"{batch.api}/{path}", headers=gh_headers(), timeout=20)
    response.raise_for_status()
    return response.json()


def pr_meta(batch, number):
    # #75025 was an extra in batch_extract, so it is not in prs.json: fall back to the API
    known = {p["number"]: p for p in json.loads(batch.prs.read_text())}
    if number in known:
        return known[number]
    pr, files = get_json(batch, f"pulls/{number}"), get_json(batch, f"pulls/{number}/files?per_page=100")
    return {"number": number, "base_sha": pr["base"]["sha"], "head_sha": pr["head"]["sha"], "changed_files": files}


def decision_with_rejection(batch, number):
    row = next(r for r in decision_rows(batch) if r["number"] == number)
    return next(d for d in row["decisions"] if d.get("rejected_alternatives"))


def fetch_file(batch, number, side, sha, filename):
    # cached under <repo>/src/<pr>/<side>/; None when the file does not exist at that sha
    local = batch.src / str(number) / side / filename
    if not local.exists():
        url = f"{batch.api}/contents/{filename}?ref={sha}"
        response = requests.get(url, headers=gh_headers("application/vnd.github.raw"), timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(response.text)
    return local


def fetch_side(batch, number, meta, side):
    names = [f["filename"] for f in meta["changed_files"] if f["filename"].endswith(".py")]
    paths = {n: fetch_file(batch, number, side, meta[f"{side}_sha"], n) for n in names}
    return {n: p for n, p in paths.items() if p is not None}


def joined_source(files):
    return "\n\n".join(f"# file: {name}\n{path.read_text()}" for name, path in files.items())


def verifier_sides(number, base, head, out, variants):
    # rename and variant sides catch rules that memorize spellings instead of the violation's structure
    rng = random.Random(number)
    mapping = fresh_names(introduced_identifiers(texts(base), texts(head)), rng)
    return {"base": base, "head": head,
            "rename-base": rewritten(base, lambda source: rename_locals(source, rng), out / "rename-base"),
            "rename-head": rewritten(head, lambda source: rename_names(source, mapping), out / "rename-head"),
            **variants}


def texts(files):
    return [path.read_text() for path in files.values()]


def rewritten(files, transform, out):
    # same relative paths under out, so path-scoped rules see the same filenames
    for name, path in files.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(transform(path.read_text()))
    return {name: out / name for name in files}


def evaluate(rule_yaml, sides):
    files = [(side, name, path) for side, named in sides.items() for name, path in named.items()]
    return [(side, name, *scan(rule_yaml, path)) for side, name, path in files]


def side_ok(rows):
    # a must-flag side with too few flagged files (or no files) fails; a must-not side fails on any flag
    flagged = {side: sum(1 for s, _, matches, _ in rows if s == side and matches) for side in MUST_FLAG}
    return {side: flagged[side] >= MIN_FLAGGED.get(side, 1) if must else flagged[side] == 0
            for side, must in MUST_FLAG.items()}


def variant_feedback(rows, sides):
    # the wrong variants' source, so the compiler sees the shapes its rule got wrong
    wrong = [(side, name) for side, name, matches, _ in rows if side in VARIANT_MISSES and bool(matches) != MUST_FLAG[side]]
    return "".join(f"\n\n{VARIANT_MISSES[side]} {name}:\n{sides[side][name].read_text()}" for side, name in wrong)


def main_false_positives(rule_yaml, changed, clone):
    # every match on the scanned branch outside the PR's own files; ast-grep errors are surfaced, not swallowed
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
        f.write(rule_yaml)
    try:
        matches = scan_tree(Path(f.name), clone)
    except RuntimeError as error:
        return [], str(error)
    fps = [fp_row(m, clone) for m in matches]
    return [fp for fp in fps if fp[0] not in changed], None


def fp_row(match, clone):
    path = str(Path(match["file"]).relative_to(clone))
    return path, match["range"]["start"]["line"] + 1, " ".join(match["lines"].split())[:160]


def passes(rows, fps, fp_error):
    errors = [e for *_, e in rows if e]
    return not errors and not fp_error and not fps and all(side_ok(rows).values())


def report_rows(rows):
    return "\n".join(f"{side} {'must flag >=1' if MUST_FLAG[side] else 'must flag 0'}{SIDE_NOTES[side]} | {name}: "
                     f"{err or ', '.join(f'{m.matched_text!r} (line {m.line})' for m in matches) or 'no matches'}"
                     for side, name, matches, err in rows)


def report(batch, ref, rows, fps, fp_error):
    return f"{report_rows(rows)}\n{main_report(batch, ref, fps, fp_error)}"


def main_report(batch, ref, fps, fp_error):
    if fp_error:
        return f"{batch.repo} {ref} must flag 0 | ERROR: {fp_error}"
    shown = "".join(f"\n  {path}:{line}  {text}" for path, line, text in fps[:FP_FEEDBACK_LIMIT])
    return f"{batch.repo} {ref} must flag 0 outside this PR's files | {len(fps)} false positives{shown}"


def preserve_as(batch, number, version):
    # the previous rule is kept as <pr>.<version>.yml for comparison, never overwritten on rerun; older versions stay
    old, kept = batch.rules / f"{number}.yml", batch.rules / f"{number}.{version}.yml"
    if old.exists() and not kept.exists():
        old.rename(kept)


def compile_pr(batch, ref, clone, number):
    meta = pr_meta(batch, number)
    changed = {f["filename"] for f in meta["changed_files"]}
    base, head = fetch_side(batch, number, meta, "base"), fetch_side(batch, number, meta, "head")
    decision, before, after = decision_with_rejection(batch, number), joined_source(base), joined_source(head)
    prompt = PROMPT.format(decision=json.dumps(decision, indent=2), before=before, after=after)
    variants = variant_files(batch.src / str(number) / "variants", variant_prompt(decision, before, after), ask_spark)
    sides, fps = verifier_sides(number, base, head, batch.src / str(number), variants), []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        rule_yaml = answer_text(ask_spark(prompt))
        results = evaluate(rule_yaml, sides)
        fps, fp_error = main_false_positives(rule_yaml, changed, clone)
        feedback = report(batch, ref, results, fps, fp_error) + variant_feedback(results, sides)
        print(f"\n=== #{number} ATTEMPT {attempt} ===\n{rule_yaml}\n\n{feedback}")
        if passes(results, fps, fp_error):
            (batch.rules / f"{number}.yml").write_text(rule_yaml)
            return attempt, []
        prompt += f"\n\nYOUR PREVIOUS RULE:\n{rule_yaml}\n\nVERIFIER RESULTS:\n{feedback}\nFix the rule."
    return None, fps


def safe_compile(batch, ref, clone, number):
    try:
        return compile_pr(batch, ref, clone, number)
    except Exception as error:  # one PR's network or API failure should not sink the batch
        print(f"\n#{number} ERROR: {error!r}")
        return None, []


def summary_line(batch, ref, number, attempt, fps):
    if attempt:
        return f"#{number}: PASS on attempt {attempt}"
    shown = "".join(f"\n    {path}:{line}  {text}" for path, line, text in fps[:FP_FEEDBACK_LIMIT])
    return f"#{number}: FAIL ({len(fps)} false positives on {batch.repo} {ref} remaining){shown}"


if __name__ == "__main__":
    args = parse_args()
    batch = Batch(args.repo)
    ref = resolve_ref(batch, args.ref)
    clone = clone_dir(batch, ref)
    shallow_clone(batch, ref, clone)
    batch.rules.mkdir(parents=True, exist_ok=True)
    numbers = targets(batch)
    for number in numbers:
        preserve_as(batch, number, "v3")
    outcomes = {n: safe_compile(batch, ref, clone, n) for n in numbers}
    print("\n=== SUMMARY ===")
    for number, (attempt, fps) in outcomes.items():
        print(summary_line(batch, ref, number, attempt, fps))
    print(f"total: {sum(1 for a, _ in outcomes.values() if a)} / {len(numbers)}")
