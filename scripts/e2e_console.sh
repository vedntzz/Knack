#!/usr/bin/env bash
# KN-96: the whole #75025 story through knack console, every page checked over HTTP.
# block via the installed PreToolUse hook -> / switches on /events -> block page -> argue (HOLD)
# -> argue page -> argue (escalate) -> argue links held -> resolve uphold -> held page
# -> the corrected edit passes -> day page -> knack receipts verify.
#
#   scripts/e2e_console.sh           fake Spark and Spark Open (scripts/one_story_fakes.py)
#   scripts/e2e_console.sh --live    the real models; needs MODEL_API_KEY
#
# A sandbox HOME and clone every run; the real knack home and Muse settings are never touched.
# The console is started on its fixed port, 7655, and stopped on exit, Ctrl-C or kill included. Prints one line per step
# and nothing measured, so every run prints the same; the last line is E2E: PASS or
# E2E: FAIL (<step>), with exit 0 or 1 to match.
set -u -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
CONSOLE_PID=""
LISTENER_PID=""
WORK=""

# fd 3: the run's own stdout, so a trap that fires inside a step still prints there.
exec 3>&1

# failed STEP [WHY]: the step's own output, then the verdict line; stops the run.
failed() {
  exec >&3
  echo "FAIL  $1"
  [ -n "${2:-}" ] && echo "    $2"
  [ -n "$WORK" ] && [ -f "$WORK/step.log" ] && sed 's/^/    /' "$WORK/step.log"
  echo "E2E: FAIL ($1)"
  exit 1
}

# step NAME COMMAND...: runs COMMAND in this shell with its output kept; ok or the failure.
step() {
  "${@:2}" >"$WORK/step.log" 2>&1 || failed "$1"
  echo "ok  $1"
}

helper() { "$PY" "$ROOT/scripts/e2e_console.py" "$1" "$WORK" "${@:2}"; }
# person: a step a person runs; resolve has no terminal here, so the person sets KNACK_HUMAN=1.
person() { KNACK_HUMAN=1 "$@"; }
story() { "$PY" "$ROOT/scripts/one_story.py" "$1" "$WORK" "${@:2}"; }

case "${1:-}" in
  "") MODELS=fake ;;
  --live) MODELS=live ;;
  *) failed preflight "unknown option $1 (the only option is --live)" ;;
esac
[ "$#" -le 1 ] || failed preflight "too many arguments"
if [ "$MODELS" = live ] && ! printenv MODEL_API_KEY >/dev/null; then
  failed preflight "--live needs MODEL_API_KEY"
fi

# halt PID: TERM, up to 5 s to exit, then KILL; a stuck child never hangs the run.
halt() {
  kill "$1" 2>/dev/null || return 0
  for _ in $(seq 50); do kill -0 "$1" 2>/dev/null || break; sleep 0.1; done
  kill -KILL "$1" 2>/dev/null
  wait "$1" 2>/dev/null
}

# stop: the listener first (an open /events stream holds the console), the console, the sandbox.
stop() {
  for pid in $LISTENER_PID $CONSOLE_PID; do halt "$pid"; done
  rm -rf "$WORK"
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-e2e-console.XXXXXX")"
trap stop EXIT
# Ctrl-C or a kill fails the run by name; the EXIT trap still stops everything.
trap 'failed interrupted' INT TERM
# A sandbox HOME: the real knack home and Muse settings are never read or written.
export HOME="$WORK/home"
export KNACK_HOME="$HOME/.knack"
mkdir -p "$HOME"
unset GITHUB_TOKEN KNACK_REGISTRY KNACK_CONSOLE_RECEIPTS
[ "$MODELS" = fake ] && unset MODEL_API_KEY BASETEN_API_KEY
export E2E_MODELS="$MODELS"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="knack e2e" GIT_AUTHOR_EMAIL="e2e@example.com"
export GIT_COMMITTER_NAME="knack e2e" GIT_COMMITTER_EMAIL="e2e@example.com"

# start_console: knack console in the clone, as a person runs it there; / then waits for a deny.
start_console() {
  helper free || return 1
  (cd "$WORK/airflow" && exec "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' console) \
    >"$WORK/console.log" 2>&1 &
  CONSOLE_PID=$!
  helper up "$CONSOLE_PID" && helper waits
}

# block: listens on /events first, then sends the alias edit through the installed hook.
block() {
  # exec, so $! is the listener's own PID and stop() can kill it, not a wrapper subshell's.
  (exec "$PY" "$ROOT/scripts/e2e_console.py" listen "$WORK") >"$WORK/listener.log" 2>&1 &
  LISTENER_PID=$!
  for _ in $(seq 100); do [ -f "$WORK/listening" ] && break; sleep 0.1; done
  [ -f "$WORK/listening" ] || { cat "$WORK/listener.log"; return 1; }
  story hook block
}

# events: the listener heard the deny the hook recorded.
events() {
  wait "$LISTENER_PID"
  LISTENER_PID=""
  helper heard
}

# block_page: the deny links the page, and the page shows the block.
block_page() { helper linked && helper page block; }

echo "knack console e2e: the #75025 edit, blocked, argued, upheld and corrected. Models: $MODELS."
step install story install
step console start_console
step block block
step events events
step "block page" block_page
step "argue covered" helper argue covered
step "argue page" helper page argue
step "argue uncovered" helper argue uncovered
step "argue links held" helper page "argue links held"
step "resolve uphold" person helper resolve
step "held page" helper page held
step corrected story hook corrected
step "day page" helper page day
step verify helper verify
echo "E2E: PASS"
