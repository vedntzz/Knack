#!/usr/bin/env bash
# KN-67 acceptance: every loop, end to end, each step PASS or FAIL.
# #75025 (real) then #900001/#900002 (synthetic merges) in a temp HOME; GitHub, Spark and
# Spark Open are test fakes (scripts/e2e_fakes.py). No network, no model, no real ~/.knack.
set -u -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
REAL_HOME="$HOME"
# The user's knack folder, wherever KNACK_HOME points it.
REAL_KNACK="${KNACK_HOME:-$REAL_HOME/.knack}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-e2e.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

ROUTES="airflow-core/src/airflow/api_fastapi/core_api/routes"
LOADER="airflow-core/src/airflow/utils/blob_loader.py"
# Every fixture is committed under scripts/fixtures; nothing comes from ~ or the network.
FIX="$ROOT/scripts/fixtures"
BASE="$FIX/75025/base"
CLONE="$WORK/airflow"
REGISTRY_DIR="$WORK/home/.knack/registries/apache-airflow"
REGISTRY="$REGISTRY_DIR/registry.json"
RECEIPTS="$WORK/home/.knack/verdicts.jsonl"
ROOT_ID="airflow-75025-1"
LOADER_RULE="airflow-900001"
LOADER_ROOT="airflow-900001-1"
ESCALATING="The public API docs promise order_by=state until its deprecation window ends in 3.2."
BAD_LESSON="a PR description is never a decision record"
FAILED=0

# A fingerprint of everything the run must not touch: the real knack home and Muse settings.
real_state() {
  find "$REAL_KNACK" "$REAL_HOME/.config/muse" -type f 2>/dev/null \
    -exec shasum {} + 2>/dev/null | sort
}

# step NAME COMMAND...: prints PASS/FAIL NAME; on failure, the step's stderr then its stdout.
step() {
  local name="$1" out err="$WORK/step.err"
  shift
  if out="$("$@" 2>"$err")"; then
    echo "PASS $name"
    return 0
  fi
  echo "FAIL $name"
  report "stderr" <"$err"
  printf '%s\n' "$out" | report "stdout"
  FAILED=1
  return 1
}

# report LABEL: indented stdin under LABEL, nothing when stdin is empty.
report() {
  local text
  text="$(cat)"
  [ -n "$text" ] && { echo "    $1:"; printf '%s\n' "$text" | sed 's/^/      /'; }
  return 0
}

# must COMMAND...: runs it; on failure names the command on stderr above its own stderr.
must() {
  "$@" && return 0
  local status=$?
  echo "command failed (exit $status): $*" >&2
  return "$status"
}

# holds FILE EXPR: EXPR, a Python expression over d (FILE's JSON), is true.
holds() {
  "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if eval(sys.argv[2]) else 1)' "$1" "$2" \
    || { echo "not true of $1: $2" >&2; return 1; }
}

# says TEXT PATTERN: TEXT holds PATTERN (grep -E), else both go to stderr.
says() {
  printf '%s' "$1" | grep -qE -- "$2" && return 0
  echo "expected /$2/ in:" >&2
  printf '%s\n' "$1" >&2
  return 1
}

knack() { "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' "$@"; }
faked() { "$PY" "$ROOT/scripts/e2e_fakes.py" "$@"; }
in_clone() { (cd "$CLONE" && "$@"); }

make_clone() {
  # The pre-fix route files and the pre-#900001 loader, in a repo whose origin is apache/airflow.
  must mkdir -p "$CLONE/$ROUTES/public" "$CLONE/$ROUTES/ui" "$(dirname "$CLONE/$LOADER")" || return 1
  must cp "$BASE/$ROUTES/public/dags.py" "$CLONE/$ROUTES/public/dags.py" || return 1
  must cp "$BASE/$ROUTES/ui/dags.py" "$CLONE/$ROUTES/ui/dags.py" || return 1
  must cp "$FIX/900001/base/$LOADER" "$CLONE/$LOADER" || return 1
  must git -C "$CLONE" init -q -b main || return 1
  must git -C "$CLONE" remote add origin https://github.com/apache/airflow.git || return 1
  must git -C "$CLONE" add -A || return 1
  must git -C "$CLONE" commit -q -m base
}

# edit_event EDIT_JSON [FILE]: a Muse edit_file PreToolUse event, find/replace from JSON.
edit_event() {
  "$PY" - "$1" "$CLONE" "${2:-$ROUTES/public/dags.py}" <<'EOF'
import json, sys
edit, cwd, path = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
tool_input = {"path": path, "find": edit["find"], "replace": edit["replace"]}
print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "edit_file",
                  "tool_input": tool_input, "cwd": cwd, "session_id": "e2e"}))
EOF
}

pretool() { (cd "$CLONE" && "$PY" -m knack.hooks.pretool); }
ALIAS="$ROOT/tests/hooks/fixtures/edit_75025_alias.json"

# denied OUT: OUT is the Muse deny envelope.
denied() {
  printf '%s' "$1" | "$PY" -c 'import json,sys; h=json.load(sys.stdin)["hookSpecificOutput"]; sys.exit(h["permissionDecision"] != "deny")'
}

# last_receipt EXPR: EXPR over r, the newest receipt, is true.
last_receipt() {
  tail -n 1 "$RECEIPTS" | "$PY" -c 'import json,sys; r=json.load(sys.stdin); sys.exit(0 if eval(sys.argv[1]) else 1)' "$1" \
    || { echo "newest receipt fails: $1" >&2; tail -n 1 "$RECEIPTS" >&2; return 1; }
}

# latest_deny: the hash of the newest deny receipt.
latest_deny() {
  "$PY" -c 'import json,sys; print([r for r in map(json.loads, open(sys.argv[1])) if r["decision"] == "deny"][-1]["hash"])' "$RECEIPTS"
}

init_step() {
  # The root alone is not enough: init writes it even when it discards the rule.
  faked init --repo apache/airflow --prs 1 || return 1
  must test -f "$REGISTRY_DIR/roots/$ROOT_ID.json" || return 1
  must test -f "$REGISTRY_DIR/rules/75025.yml" || return 1
  must grep -q '"rules/75025.yml"' "$REGISTRY"
}

confirm_step() {
  # Confirmed, by the named reviewer, pinned to the sha of the rule file now installed.
  local out sha
  out="$(in_clone faked confirm "$ROOT_ID" --by "e2e reviewer")" || return 1
  echo "$out"
  says "$out" "Confirmed, pinned to rule [0-9a-f]{12}" || return 1
  sha="$(shasum -a 256 "$REGISTRY_DIR/rules/75025.yml" | cut -d' ' -f1)"
  holds "$REGISTRY_DIR/roots/$ROOT_ID.json" "d['status'] == 'Confirmed' and d['rule_sha'] == '$sha' and d['confirmed_by'] == 'e2e reviewer'"
}

warn_step() {
  # A prompt that names the Dag list sort gets the Confirmed decision and its quote injected.
  local out
  out="$("$PY" -c 'import json,sys; print(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": sys.argv[1], "cwd": sys.argv[2], "session_id": "e2e"}))' \
    "Let get_dags sort by order_by=state and start_date again" "$CLONE" | in_clone "$PY" -m knack.hooks.warn)" || return 1
  echo "$out"
  says "$out" '"hookEventName": "UserPromptSubmit"' || return 1
  says "$out" "$ROOT_ID" && says "$out" "removed them rather than aliasing them"
}

alias_denied() {
  local out
  out="$(edit_event "$ALIAS" | pretool)" || return 1
  echo "$out"
  denied "$out" || return 1
  says "$out" "https://github.com/apache/airflow/pull/75025"
}

fix_allowed() {
  # The merged fix: drop state and start_date from the allowed list. Allow is silence.
  local out fix="$WORK/fix.json"
  printf '%s' '{"find": "\"next_dagrun\", \"state\", \"start_date\"]", "replace": "\"next_dagrun\"]"}' >"$fix"
  out="$(edit_event "$fix" | pretool)" || return 1
  echo "$out"
  test -z "$out" && last_receipt "(r['decision'], r['rule_id']) == ('allow', 'airflow-75025')"
}

argue_hold() {
  # The objection restates the rejected alias, so Spark holds on the verbatim quote.
  local out
  out="$(in_clone faked argue "The frontend still sends order_by=state. Let me alias state and start_date onto DagRun.state and DagRun.start_date.")" || return 1
  echo "$out"
  says "$out" "^HOLD" && says "$out" "removed them rather than aliasing them"
}

argue_escalate() {
  # Spark escalates; Spark Open, asked blind, holds: the check is logged and no case recorded.
  local out checks="$REGISTRY_DIR/self_checks.jsonl"
  out="$(in_clone faked argue "$ESCALATING" 2>&1)" || return 1
  echo "$out"
  says "$out" "ESCALATE: held for a person" || return 1
  says "$out" "knack resolve [0-9a-f]{64} allow\|retire" || return 1
  # argue names Spark by its model id; the fake answers in its place.
  says "$out" "muse-spark-1.3 yes, fake-spark-open no; logged only" || return 1
  must test ! -d "$REGISTRY_DIR/cases" || return 1
  test "$(grep -c '"trigger":"argue"' "$checks")" -eq 1
}

resolve_allow() {
  local out
  out="$(in_clone knack resolve "$(latest_deny)" allow --reason "frontend migration needs one release" --by "e2e lead")" || return 1
  echo "$out"
  says "$out" "allowed by e2e lead \(airflow-75025, $ROOT_ID\)" || return 1
  last_receipt "r['resolution']['action'] == 'allow' and r['decision'] == 'allow'"
}

retry_allowed() {
  # The exact edit a person allowed passes: an allow on the same edit snapshot as the deny.
  local out edit
  edit="$("$PY" -c 'import json,sys; print([r for r in map(json.loads, open(sys.argv[1])) if r["decision"] == "deny"][-1]["edit_sha256"])' "$RECEIPTS")"
  out="$(edit_event "$ALIAS" | pretool)" || return 1
  echo "$out"
  test -z "$out" && last_receipt "(r['decision'], r['rule_id'], r['edit_sha256']) == ('allow', 'airflow-75025', '$edit')"
}

# other_alias: the alias edit with one more comment line, so no resolution covers it.
other_alias() {
  "$PY" -c 'import json,sys; e=json.load(open(sys.argv[1])); e["replace"]=e["replace"].replace("_DAG_SORT_ALIASES = {", "# Kept for the old UI.\n_DAG_SORT_ALIASES = {", 1); print(json.dumps(e))' "$ALIAS" >"$WORK/other_alias.json"
}

resolve_retire() {
  # A fresh deny, then a person retires the decision: its rule leaves the registry.
  local out
  other_alias || return 1
  out="$(edit_event "$WORK/other_alias.json" | pretool)" || return 1
  denied "$out" || return 1
  out="$(in_clone knack resolve "$(latest_deny)" retire --reason "sort aliases are back by design" --by "e2e lead")" || return 1
  echo "$out"
  says "$out" "retired by e2e lead" || return 1
  holds "$REGISTRY" "not any('75025' in e['rule'] for e in d['rules'])"
}

retired_silent() {
  local out
  out="$(edit_event "$WORK/other_alias.json" | pretool)" || return 1
  echo "$out"
  test -z "$out"
}

# merge_pr NUMBER SUBJECT: a real squash-style merge of the fixture's head onto main.
merge_pr() {
  must git -C "$CLONE" checkout -q -b "pr-$1" || return 1
  must cp "$FIX/$1/head/$LOADER" "$CLONE/$LOADER" || return 1
  must git -C "$CLONE" commit -q -am "$2" || return 1
  must git -C "$CLONE" checkout -q main || return 1
  # The installed hook fires too; with no keys in the sandbox it says so and leaves the merge pending.
  must git -C "$CLONE" merge -q --ff-only "pr-$1" 2>"$WORK/hook.err"
}

watch_step() {
  # knack watch installs both hooks; a real merge; the hook's run (fakes) installs #900001's rule.
  local out
  out="$(in_clone knack watch --muse-settings "$WORK/home/.config/muse/settings.json")" || return 1
  echo "$out"
  merge_pr 900001 "Read blobs one at a time (#900001)" || return 1
  out="$(in_clone faked watch-merged --registry "$REGISTRY")" || return 1
  echo "$out"
  says "$out" "1 merged PR: #900001" || return 1
  holds "$REGISTRY" "any(e['rule'].endswith('900001.yml') and e['proof'] and e['root_ids'] == ['$LOADER_ROOT'] for e in d['rules'])"
}

inferred_silent() {
  # The new root is a machine guess: its rule matches the edit, and still never blocks.
  local out edit="$WORK/inferred.json"
  holds "$REGISTRY_DIR/roots/$LOADER_ROOT.json" "d['status'] != 'Confirmed'" || return 1
  printf '%s' '{"find": "async def load(items):", "replace": "import asyncio\n\n\nasync def fetch_all(blobs):\n    data = await asyncio.gather(*(b.read() for b in blobs))\n    return data\n\n\nasync def load(items):"}' >"$edit"
  out="$(edit_event "$edit" "$LOADER" | pretool)" || return 1
  echo "$out"
  test -z "$out" && last_receipt "r['rule_id'] == '$LOADER_RULE' and r['decision'] == 'allow' and r['matched']"
}

# loop KIND CASE RULE: knack miss|false-block on a loader edit; the fake compiler returns RULE.
loop() {
  faked edit-case "$2" "$CLONE" "$WORK/$2.json" || return 1
  in_clone env KNACK_E2E_RULE="$3" "$PY" "$ROOT/scripts/e2e_fakes.py" "$1" "$WORK/$2.json" \
    --heldout "$FIX/heldout" --work "$WORK/miss" --adversary spark-open
}

miss_step() {
  # A must-fail edit the rule let through is recorded; every gate re-proves the new rule.
  local out
  out="$(loop miss miss_return broad)" || { echo "$out"; return 1; }
  echo "$out"
  says "$out" "recorded must-fail case" || return 1
  says "$out" "fails: guard edit .* adds no new match; recompiling" || return 1
  for gate in cases proof "held-out same" "held-out cross" "fresh cross-model"; do
    says "$out" "PASS $gate:" || return 1
  done
  # The installed file is now the recompiled rule, which also catches the bare return.
  says "$out" "installed $LOADER_RULE" && grep -q 'return await asyncio.gather' "$REGISTRY_DIR/rules/900001.yml"
}

kept_step() {
  # A recompile that fails a gate exits 1 and leaves the installed rule byte for byte.
  local out before after
  before="$(shasum "$REGISTRY_DIR/rules/900001.yml")"
  out="$(loop miss miss_imported bad)" && { echo "$out"; echo "exit 0 on a failed gate" >&2; return 1; }
  echo "$out"
  after="$(shasum "$REGISTRY_DIR/rules/900001.yml")"
  says "$out" "FAIL proof:" || return 1
  says "$out" "kept the old $LOADER_RULE: [0-9]+ gate\(s\) failed" && test "$before" = "$after"
}

false_block_step() {
  # An edit the rule wrongly denies becomes a must-pass case; the narrowed rule allows it.
  local out
  out="$(loop false-block false_block_pings narrow)" || { echo "$out"; return 1; }
  echo "$out"
  says "$out" "recorded must-pass case" || return 1
  says "$out" "PASS cases: every must-fail edit denied, every must-pass edit allowed" || return 1
  says "$out" "installed $LOADER_RULE" || return 1
  test "$(ls "$REGISTRY_DIR/cases/$LOADER_RULE" | wc -l)" -eq 3
}

self_check_step() {
  # #900002 slips past the rule; Spark and Spark Open, asked blind, both say it takes the
  # rejected path, so a case is recorded. The argue check, where they disagreed, recorded none.
  local out checks="$REGISTRY_DIR/self_checks.jsonl"
  # Only rules that block are self-checked, so the loader root is Confirmed first.
  in_clone faked confirm "$LOADER_ROOT" --by "e2e reviewer" --no-gate || return 1
  # Watch's loop reads held-out sets from default_heldout(registry): ../heldout/<registry stem>.
  must mkdir -p "$WORK/home/.knack/registries/heldout/registry" || return 1
  must cp -R "$FIX/heldout/900001" "$WORK/home/.knack/registries/heldout/registry/" || return 1
  merge_pr 900002 "Batch blob reads behind a task list (#900002)" || return 1
  out="$(in_clone env KNACK_E2E_RULE=final "$PY" "$ROOT/scripts/e2e_fakes.py" watch-merged --registry "$REGISTRY")" || return 1
  echo "$out"
  says "$out" "fake-spark yes, fake-spark-open yes; recording must-fail case" || return 1
  says "$out" "installed $LOADER_RULE" || return 1
  "$PY" - "$checks" <<'EOF'
import json, sys
checks = [json.loads(line) for line in open(sys.argv[1])]
agreed = [c for c in checks if all(a["yes"] for a in c["answers"])]
recorded = [c for c in checks if c["case_key"]]
sys.exit(0 if len(checks) == 2 and agreed == recorded and len(recorded) == 1 else 1)
EOF
}

gate_holds() {
  # Re-pinning the recompiled loader rule re-reads every Confirmed PR; none is lost, so it stands.
  local out
  out="$(in_clone faked confirm "$LOADER_ROOT" --by "e2e reviewer")" || return 1
  echo "$out"
  says "$out" "gate: re-extracting 2 PR\(s\)" || return 1
  holds "$REGISTRY_DIR/roots/$LOADER_ROOT.json" "d['status'] == 'Confirmed' and d['rule_sha']"
}

gate_rolls_back() {
  # A reject whose lesson makes the extractor lose #900001: exit 1, everything restored.
  local out before="$(shasum "$REGISTRY" "$REGISTRY_DIR/roots/$ROOT_ID.json")"
  out="$(in_clone faked reject "$ROOT_ID" --reason "$BAD_LESSON" --by "e2e reviewer")" && { echo "$out"; echo "exit 0 on a lost root" >&2; return 1; }
  echo "$out"
  says "$out" "Confirmed -> Unknown rolled back" || return 1
  says "$out" "$LOADER_ROOT \(#900001\) no longer extracted" || return 1
  test "$before" = "$(shasum "$REGISTRY" "$REGISTRY_DIR/roots/$ROOT_ID.json")" || return 1
  ! grep -q "$BAD_LESSON" "$WORK/home/.knack/corrections.jsonl"
}

guard_error_open() {
  # A rule ast-grep cannot load is our bug: the Confirmed rule's edit is allowed and logged.
  local out rule="$REGISTRY_DIR/rules/900001.yml"
  must cp "$rule" "$WORK/rule.saved" || return 1
  printf 'id: %s\nlanguage: python\nrule: {nonsense: 1}\n' "$LOADER_RULE" >"$rule"
  out="$(edit_event "$WORK/inferred.json" "$LOADER" | pretool)"
  must cp "$WORK/rule.saved" "$rule" || return 1
  echo "$out"
  test -z "$out" || return 1
  last_receipt "(r['rule_id'], r['decision']) == ('$LOADER_RULE', 'guard-error')" || return 1
  grep -rqs . "$CLONE/.knack/guard_errors.log" "$WORK/home/.knack/guard_errors.log"
}

reprove_step() {
  # Every gate re-run on the installed rule; the proof is stored, pinned to that rule's sha.
  local out sha
  out="$(in_clone faked reprove --variants "$FIX/variants" --heldout "$FIX/heldout" --work "$WORK/reprove")" || { echo "$out"; return 1; }
  echo "$out"
  says "$out" "$LOADER_RULE: every gate run holds" || return 1
  sha="$(shasum -a 256 "$REGISTRY_DIR/rules/900001.yml" | cut -d' ' -f1)"
  holds "$REGISTRY" "(lambda p: p['rule_sha'] == '$sha' and p['reproved_at'] and set(p['heldout_sets']) == {'same', 'cross'})(d['rules'][-1]['proof'])"
}

console_step() {
  # The first deny: its verdict cites the root and quote; its rulings are the HOLD and ESCALATE.
  local first out="$WORK/console.json"
  first="$("$PY" -c 'import json,sys; print([r for r in map(json.loads, open(sys.argv[1])) if r["decision"] == "deny"][0]["hash"])' "$RECEIPTS")"
  faked console "$first" >"$out" || return 1
  cat "$out"
  holds "$out" "'removed them rather than aliasing them' in json.dumps(d['/verdict/$first'])" || return 1
  holds "$out" "[r['decision'] for r in d['/verdict/$first/rulings']] == ['hold', 'escalate']"
}

receipts_step() {
  local out
  out="$(knack receipts verify)" || { echo "$out"; return 1; }
  echo "$out"
  says "$out" "chain intact"
}

grid_step() {
  # The committed proof grid, from data/ alone.
  local out
  out="$("$PY" -m knack.reproduce grid)" || return 1
  echo "$out"
  says "$out" "PASS"
}

untouched() { test "$(real_state)" = "$BEFORE"; }

BEFORE="$(real_state)"
export HOME="$WORK/home"
export KNACK_HOME="$HOME/.knack"
mkdir -p "$HOME"
# No live credential or registry override reaches any step; git reads no user config.
unset GITHUB_TOKEN MODEL_API_KEY BASETEN_API_KEY KNACK_REGISTRY
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
# CI has no git identity; every commit here is made as this one.
export GIT_AUTHOR_NAME="knack e2e" GIT_AUTHOR_EMAIL="e2e@example.com"
export GIT_COMMITTER_NAME="knack e2e" GIT_COMMITTER_EMAIL="e2e@example.com"
cd "$ROOT" || exit 1

# Every later step needs the clone, so its failure stops the run.
step "fixture clone" make_clone || exit 1

step "knack init" init_step
step "knack confirm pins the rule sha" confirm_step
step "warn injects the decision" warn_step
step "alias edit denied" alias_denied
step "correct fix allowed" fix_allowed
step "argue HOLD" argue_hold
step "argue ESCALATE, second model disagrees: logged only" argue_escalate
step "resolve allow" resolve_allow
step "retry of the allowed edit passes" retry_allowed
step "resolve retire" resolve_retire
step "retired rule stops blocking" retired_silent
step "watch on a real merge installs a new proven rule" watch_step
step "Inferred rule never blocks" inferred_silent
step "miss recorded, recompiled, re-proved, installed" miss_step
step "failing gates keep the old rule" kept_step
step "false-block records a must-pass case and installs" false_block_step
step "self-check records a case only when both models agree" self_check_step
step "confirm passes the regression gate" gate_holds
step "regression gate rolls back a bad correction" gate_rolls_back
step "guard error fails open" guard_error_open
step "reprove fills proof" reprove_step
step "console /verdict and /rulings JSON" console_step
step "receipts verify" receipts_step
step "proof grid prints" grid_step
step "real HOME untouched" untouched

exit "$FAILED"
