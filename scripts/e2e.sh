#!/usr/bin/env bash
# KN-40 acceptance: init -> confirm -> alias denied -> fix allowed -> argue holds -> receipts verify.
# Runs in a temp HOME against a fixture clone of apache/airflow; GitHub and Spark are test fakes.
set -u -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
REAL_HOME="$HOME"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-e2e.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

ROUTES="airflow-core/src/airflow/api_fastapi/core_api/routes"
# Every fixture is committed under scripts/fixtures; nothing comes from ~ or the network.
BASE="$ROOT/scripts/fixtures/75025/base"
CLONE="$WORK/airflow"
REGISTRY_DIR="$WORK/home/.knack/registries/apache-airflow"
ROOT_ID="airflow-75025-1"
FAILED=0

# A fingerprint of everything the run must not touch: real ~/.knack and Muse settings.
real_state() {
  find "$REAL_HOME/.knack" "$REAL_HOME/.config/muse" -type f 2>/dev/null \
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

knack() { "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' "$@"; }
faked() { "$PY" "$ROOT/scripts/e2e_fakes.py" "$@"; }

make_clone() {
  # The pre-fix route files in a repo whose origin is apache/airflow.
  must mkdir -p "$CLONE/$ROUTES/public" "$CLONE/$ROUTES/ui" || return 1
  must cp "$BASE/$ROUTES/public/dags.py" "$CLONE/$ROUTES/public/dags.py" || return 1
  must cp "$BASE/$ROUTES/ui/dags.py" "$CLONE/$ROUTES/ui/dags.py" || return 1
  must git -C "$CLONE" init -q -b main || return 1
  must git -C "$CLONE" remote add origin https://github.com/apache/airflow.git || return 1
  must git -C "$CLONE" add -A || return 1
  must git -C "$CLONE" commit -q -m base
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
  # The root alone is not enough: init writes it even when it discards the rule.
  faked init --repo apache/airflow --prs 1 || return 1
  must test -f "$REGISTRY_DIR/roots/$ROOT_ID.json" || return 1
  must test -f "$REGISTRY_DIR/rules/75025.yml" || return 1
  must grep -q '"rules/75025.yml"' "$REGISTRY_DIR/registry.json"
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
# CI has no git identity; every commit here is made as this one.
export GIT_AUTHOR_NAME="knack e2e" GIT_AUTHOR_EMAIL="e2e@example.com"
export GIT_COMMITTER_NAME="knack e2e" GIT_COMMITTER_EMAIL="e2e@example.com"
cd "$ROOT" || exit 1

# Every later step needs the clone, so its failure stops the run.
step "fixture clone" make_clone || exit 1

step "knack init" init_step
step "knack confirm" confirm_step
step "alias edit denied" alias_denied
step "correct fix allowed" fix_allowed
step "argue holds" faked argue "$REGISTRY_DIR/roots"
step "receipts verify" receipts_step
step "real HOME untouched" untouched

exit "$FAILED"
