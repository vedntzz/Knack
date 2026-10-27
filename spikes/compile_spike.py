# Compile spike: can Muse Spark turn a recorded decision into a history-verified ast-grep rule?
import json, os, tempfile, requests
from pathlib import Path
from q3_extract import answer_json
from knack.guard.runner import scan_file_with_rule, GuardRunnerError

SPARK = "https://api.meta.ai/v1/responses"
FIX = Path("tests/guard/fixtures")
MUST_FAIL = {"pre-fix code": FIX / "pre_fix.py",
             "held-out violation A": FIX / "rejected_alias.py",
             "held-out violation B": FIX / "violating.py",
             "held-out violation C": FIX / "replay" / "run3_public_dags.py"}
MUST_PASS = {"merged fix": FIX / "fixed.py",
             "held-out clean A": FIX / "legit_last_run_state.py",
             "held-out clean B": FIX / "unrelated_state.py"}
PROMPT = """You compile an engineering decision into an ast-grep rule (YAML) that flags code violating it.
The rule must flag code that goes against the decision, including its rejected alternative,
and must NOT flag code that follows the decision or unrelated code.
ast-grep notes: top-level keys are id, language (python), severity (error), message, rule.
Rule operators: pattern, kind, regex, inside, has, all, any, not.
Relational operators (inside, has) only check the direct parent/child by default (stopBy: neighbor);
use stopBy: end to search all ancestors/descendants.
Use id: compiled-rule. Return ONLY the YAML. No prose, no code fences.

DECISION:
{decision}

CODE BEFORE THE DECISION (violates it):
{before}

CODE AFTER THE DECISION (follows it):
{after}
"""

def ask_spark(prompt):
    body = {"model": "muse-spark-1.3", "input": prompt, "reasoning": {"summary": "auto"}}
    headers = {"Authorization": f"Bearer {os.environ['MODEL_API_KEY']}"}
    response = requests.post(SPARK, headers=headers, json=body, timeout=300)
    response.raise_for_status()
    return response.json()

def answer_text(resp):
    message = [i for i in resp["output"] if i["type"] == "message"][0]
    text = message["content"][0]["text"].strip()
    return text.removeprefix("```yaml").removeprefix("```").removesuffix("```").strip()

def scan(rule_yaml, path):
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
        f.write(rule_yaml)
    try:
        return scan_file_with_rule(path, Path(f.name)), None
    except GuardRunnerError as error:
        return [], str(error)

def evaluate(rule_yaml):
    results = []
    for label, path in {**MUST_FAIL, **MUST_PASS}.items():
        matches, error = scan(rule_yaml, path)
        should_flag = label in MUST_FAIL
        ok = error is None and (len(matches) > 0) == should_flag
        detail = error or ", ".join(f"{m.matched_text} (line {m.line})" for m in matches) or "no matches"
        results.append((label, "flag" if should_flag else "allow", len(matches), ok, detail))
    return results

def report(results):
    return "\n".join(f"{'OK ' if ok else 'BAD'} {label}: expected {exp}, got {n} matches [{detail}]"
                     for label, exp, n, ok, detail in results)

if __name__ == "__main__":
    decision = answer_json(json.load(open("spikes/q3_raw.json")))["decisions"][0]
    prompt = PROMPT.format(decision=json.dumps(decision, indent=2),
                           before=MUST_FAIL["pre-fix code"].read_text(),
                           after=MUST_PASS["merged fix"].read_text())
    for attempt in range(1, 4):
        rule_yaml = answer_text(ask_spark(prompt))
        results = evaluate(rule_yaml)
        print(f"\n=== ATTEMPT {attempt} ===\n{rule_yaml}\n\n{report(results)}")
        if all(ok for *_, ok, _ in results):
            Path("spikes/compiled_rule.yml").write_text(rule_yaml)
            print(f"\nCOMPILE GATE: PASS on attempt {attempt}")
            break
        prompt += f"\n\nYOUR PREVIOUS RULE:\n{rule_yaml}\n\nVERIFIER RESULTS:\n{report(results)}\nFix the rule."
    else:
        print("\nCOMPILE GATE: FAIL after 3 attempts")