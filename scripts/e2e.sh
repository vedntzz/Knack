#!/usr/bin/env bash
# KN-40 acceptance: init -> confirm -> alias denied -> fix allowed -> argue holds -> receipts verify.
# Runs in a temp HOME against a fixture clone of apache/airflow; GitHub and Spark are test fakes.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
REAL_HOME="$HOME"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-e2e.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

ROUTES="airflow-core/src/airflow/api_fastapi/core_api/routes"
BASE="$ROOT/spikes/batch/apache-airflow/src/75025/base"
CLONE="$WORK/airflow"
REGISTRY_DIR="$WORK/home/.knack/registries/apache-airflow"
ROOT_ID="airflow-75025-1"
FAILED=0

# A fingerprint of everything the run must not touch: real ~/.knack and Muse settings.
real_state() {
  find "$REAL_HOME/.knack" "$REAL_HOME/.config/muse" -type f 2>/dev/null \
    -exec shasum {} + 2>/dev/null | sort
}

# step NAME COMMAND...: prints PASS/FAIL NAME; output only on failure.
step() {
  local name="$1" out
  shift
  if out="$("$@" 2>&1)"; then
    echo "PASS $name"
  else
    echo "FAIL $name"
    printf '%s\n' "$out" | sed 's/^/    /'
    FAILED=1
  fi
}

knack() { "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' "$@"; }
faked() { "$PY" "$ROOT/scripts/e2e_fakes.py" "$@"; }

make_clone() {
  # The pre-fix route files in a repo whose origin is apache/airflow.
  mkdir -p "$CLONE/$ROUTES/public" "$CLONE/$ROUTES/ui"
  cp "$BASE/$ROUTES/public/dags.py" "$CLONE/$ROUTES/public/dags.py"
  cp "$BASE/$ROUTES/ui/dags.py" "$CLONE/$ROUTES/ui/dags.py"
  git -C "$CLONE" init -q -b main
  git -C "$CLONE" remote add origin https://github.com/apache/airflow.git
  git -C "$CLONE" add -A
  git -C "$CLONE" -c user.name=e2e -c user.email=e2e@example.com commit -q -m base
}

# edit_event FIND_FILE: a Muse edit_file PreToolUse event on public/dags.py, find/replace from JSON.
edit_event() {
  "$PY" - "$1" "$CLONE" "$ROUTES/public/dags.py" <<'EOF'
import json, sys
edit, cwd, path = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
tool_input = {"path": path, "find": edit["find"], "replace": edit["replace"]}
print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "edit_file",
                  "tool_input": tool_input, "cwd": cwd, "session_id": "e2e"}))
EOF
}

pretool() { (cd "$CLONE" && "$PY" -m knack.hooks.pretool); }

init_step() {
  faked init --repo apache/airflow --prs 1 || return 1
  test -f "$REGISTRY_DIR/registry.json" && test -f "$REGISTRY_DIR/roots/$ROOT_ID.json"
}

confirm_step() {
  (cd "$CLONE" && faked confirm "$ROOT_ID" --by "e2e reviewer") || return 1
  grep -q '"status": *"Confirmed"' "$REGISTRY_DIR/roots/$ROOT_ID.json"
}

alias_denied() {
  local out
  out="$(edit_event "$ROOT/tests/hooks/fixtures/edit_75025_alias.json" | pretool)" || return 1
  echo "$out"
  printf '%s' "$out" | "$PY" -c 'import json,sys; h=json.load(sys.stdin)["hookSpecificOutput"]; sys.exit(h["permissionDecision"] != "deny")' || return 1
  printf '%s' "$out" | grep -q "https://github.com/apache/airflow/pull/75025"
}

fix_allowed() {
  # The merged fix: drop state and start_date from the allowed list. Allow is silence.
  local out fix="$WORK/fix.json"
  printf '%s' '{"find": "\"next_dagrun\", \"state\", \"start_date\"]", "replace": "\"next_dagrun\"]"}' >"$fix"
  out="$(edit_event "$fix" | pretool)" || return 1
  echo "$out"
  test -z "$out" && last_receipt_is allow
}

# last_receipt_is DECISION: the guard really ran rule airflow-75025, not silence from no registry.
last_receipt_is() {
  tail -n 1 "$WORK/home/.knack/verdicts.jsonl" | "$PY" -c 'import json,sys; r=json.load(sys.stdin); sys.exit((r["decision"], r["rule_id"]) != (sys.argv[1], "airflow-75025"))' "$1"
}

receipts_step() {
  local out
  out="$(knack receipts verify)" || { echo "$out"; return 1; }
  echo "$out"
  test "$(wc -l <"$WORK/home/.knack/verdicts.jsonl")" -ge 2
}

untouched() { test "$(real_state)" = "$BEFORE"; }

BEFORE="$(real_state)"
export HOME="$WORK/home"
mkdir -p "$HOME"
# No live credential or registry override reaches any step; git reads no user config.
unset GITHUB_TOKEN MODEL_API_KEY BASETEN_API_KEY KNACK_REGISTRY
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
cd "$ROOT" || exit 1
make_clone >/dev/null 2>&1 || { echo "FAIL fixture clone"; exit 1; }

step "knack init" init_step
step "knack confirm" confirm_step
step "alias edit denied" alias_denied
step "correct fix allowed" fix_allowed
step "argue holds" faked argue "$REGISTRY_DIR/roots"
step "receipts verify" receipts_step
step "real HOME untouched" untouched

exit "$FAILED"
