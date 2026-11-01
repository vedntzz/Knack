#!/usr/bin/env bash
# KN-67 live smoke: the paths e2e.sh fakes, against the real services. Off unless KNACK_LIVE=1.
# Needs GITHUB_TOKEN and MODEL_API_KEY (BASETEN_API_KEY adds watch's self-check), and the home
# registry for apache/airflow (knack init --repo apache/airflow) with #75025 Confirmed.
# Writes: receipts and a ruling to the real ~/.knack (that is the point); watch runs on a copy
# of the registry in a temp folder, so the home registry's rules are never touched.
set -u -o pipefail

if [ "${KNACK_LIVE:-}" != "1" ]; then
  echo "SKIP live smoke: set KNACK_LIVE=1 (calls GitHub, api.meta.ai and Baseten)"
  exit 0
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-live.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

ROUTES="airflow-core/src/airflow/api_fastapi/core_api/routes"
FIX="$ROOT/scripts/fixtures/75025"
OPENER="$ROOT/tests/guard/fixtures/replay/run3_public_dags.py"
KNACK_DIR="${KNACK_HOME:-$HOME/.knack}"
HOME_REGISTRY="$KNACK_DIR/registries/apache-airflow"
SANDBOX="$WORK/airflow"
COPY="$WORK/registry"
PR="${KNACK_LIVE_PR:-75025}"
SPARK_URL="https://api.meta.ai/v1/responses"
FAILED=0

# step NAME COMMAND...: prints PASS/FAIL NAME; the step's own output is indented under it.
step() {
  local name="$1" out
  shift
  if out="$("$@" 2>&1)"; then
    echo "PASS $name"
    printf '%s\n' "$out" | sed 's/^/    /'
    return 0
  fi
  echo "FAIL $name"
  printf '%s\n' "$out" | sed 's/^/    /'
  FAILED=1
  return 1
}

# says TEXT PATTERN: TEXT holds PATTERN (grep -E).
says() {
  printf '%s' "$1" | grep -qE -- "$2" && return 0
  echo "expected /$2/"
  return 1
}

knack() { "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' "$@"; }

keys_step() {
  local missing=0
  for key in GITHUB_TOKEN MODEL_API_KEY; do
    printenv "$key" >/dev/null || { echo "$key is not set"; missing=1; }
  done
  printenv BASETEN_API_KEY >/dev/null || echo "BASETEN_API_KEY is not set: watch skips its self-check"
  test "$missing" -eq 0 && test -f "$HOME_REGISTRY/registry.json"
}

make_sandbox() {
  # #75025's pre-fix route files, in a repo whose origin is apache/airflow.
  mkdir -p "$SANDBOX/$ROUTES/public" "$SANDBOX/$ROUTES/ui" || return 1
  cp "$FIX/base/$ROUTES/public/dags.py" "$SANDBOX/$ROUTES/public/dags.py" || return 1
  cp "$FIX/base/$ROUTES/ui/dags.py" "$SANDBOX/$ROUTES/ui/dags.py" || return 1
  git -C "$SANDBOX" init -q -b main || return 1
  git -C "$SANDBOX" remote add origin https://github.com/apache/airflow.git || return 1
  git -C "$SANDBOX" add -A && git -C "$SANDBOX" commit -q -m base
}

opener_denied() {
  # The bench opener's public/dags.py, written whole, through the real hook and home registry.
  local out
  out="$("$PY" - "$OPENER" "$SANDBOX" "$ROUTES/public/dags.py" <<'EOF' | (cd "$SANDBOX" && "$PY" -m knack.hooks.pretool)
import json, sys
content, cwd, path = open(sys.argv[1]).read(), sys.argv[2], sys.argv[3]
print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "write_file",
                  "tool_input": {"path": path, "content": content}, "cwd": cwd, "session_id": "live-smoke"}))
EOF
)" || return 1
  echo "$out"
  says "$out" '"permissionDecision": "deny"' && says "$out" "github.com/apache/airflow/pull/75025"
}

argue_live() {
  # Spark itself rules on the deny just made; the ruling names the model that was asked.
  local out
  echo "POST $SPARK_URL (model muse-spark-1.3, MODEL_API_KEY)"
  out="$(cd "$SANDBOX" && knack argue "The frontend still sends order_by=state. Let me alias state and start_date onto DagRun.state and DagRun.start_date.")" || { echo "$out"; return 1; }
  echo "$out"
  says "$out" "^(HOLD|ESCALATE)" || return 1
  tail -n 1 "$KNACK_DIR/rulings.jsonl" | "$PY" -c 'import json,sys; r=json.load(sys.stdin); print("ruling model:", r["model"]); sys.exit(r["model"] != "muse-spark-1.3" or r["reply"].startswith("Spark could not"))'
}

copy_registry() {
  # Watch installs into the registry it watches, so it watches a copy.
  mkdir -p "$COPY" && cp -R "$HOME_REGISTRY/registry.json" "$HOME_REGISTRY/roots" "$HOME_REGISTRY/rules" "$COPY/"
}

watch_merge() {
  # A real merge naming #PR; the post-merge hook knack watch installed runs the live pipeline.
  local out
  copy_registry || return 1
  (cd "$SANDBOX" && knack watch --registry "$COPY/registry.json" --muse-settings "$WORK/muse.json") || return 1
  git -C "$SANDBOX" checkout -q -b "pr-$PR" || return 1
  cp "$FIX/head/$ROUTES/public/dags.py" "$SANDBOX/$ROUTES/public/dags.py" || return 1
  cp "$FIX/head/$ROUTES/ui/dags.py" "$SANDBOX/$ROUTES/ui/dags.py" || return 1
  git -C "$SANDBOX" commit -q -am "Live smoke merge (#$PR)" && git -C "$SANDBOX" checkout -q main || return 1
  out="$(git -C "$SANDBOX" merge --ff-only "pr-$PR" 2>&1)" || { echo "$out"; return 1; }
  echo "$out"
  says "$out" "1 merged PR: #$PR" && says "$out" "\[5/5\] install"
}

step "live keys and home registry" keys_step || exit 1
step "sandbox clone" make_sandbox || exit 1
step "opener replay denies" opener_denied
step "knack argue live" argue_live
step "watch merge in the sandbox" watch_merge

exit "$FAILED"
