#!/usr/bin/env bash
# KN-96a: one receipt chain on the #75025 edit, every step answering the same block receipt:
# block -> argue HOLD -> argue ESCALATE -> resolve uphold -> the corrected edit passes -> verify.
# A clean sandbox HOME and clone every run; the real ~/.knack and Muse settings are never touched.
#
#   scripts/one_story.sh [OUT]    OUT defaults to bench/one_story; replaced only if it is a story
#   KNACK_STORY_MODELS=live|fake  live (default) asks Spark and Spark Open and needs MODEL_API_KEY;
#                                 fake swaps them for labelled fakes (scripts/one_story_fakes.py)
#   KNACK_STORY_BY                who resolves; defaults to this repo's git user.name
#
# OUT holds receipts.jsonl, rulings.jsonl, latency.json (this run only), story.json, edits/ and
# traces/. Same output every run except what is measured: hashes, times and latencies.
set -u -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
OUT="${1:-$ROOT/bench/one_story}"
MODELS="${KNACK_STORY_MODELS:-live}"
ROOT_75025="$ROOT/data/roots/airflow/75025.json"
HOLD_OBJECTION="Let me alias state and start_date onto DagRun.state and DagRun.start_date so the advertised names keep working."
ESCALATE_OBJECTION="A customer dashboard pins order_by=state in a contract that runs until March; removing it breaks them."
# Uphold: a person reviews the held case and the decision stands. No exception, no case, the
# rule unchanged; the alias edit stays blocked, and the corrected edit passes on its own merits.
REASON="The decision stands; the customer can sort by last_run_state and last_run_start_date."

# fail WHAT: names what stopped the story, on stderr.
fail() {
  echo "one_story: $1" >&2
  exit 1
}

# preflight: everything that can stop the story stops it before OUT or the sandbox is touched.
preflight() {
  case "$MODELS" in
    fake) ;;
    live) printenv MODEL_API_KEY >/dev/null || fail "live models need MODEL_API_KEY (or KNACK_STORY_MODELS=fake)" ;;
    *) fail "KNACK_STORY_MODELS must be live or fake, not $MODELS" ;;
  esac
  "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get("confirmed_by") and d.get("rule_sha") else 1)' \
    "$ROOT_75025" || fail "data/roots/airflow/75025.json has no confirmed_by or rule_sha"
  if [ -e "$OUT" ] && [ -n "$(ls -A "$OUT")" ] && [ ! -f "$OUT/story.json" ]; then
    fail "$OUT is not empty and holds no story.json; refusing to replace it"
  fi
  [ -n "$BY" ] || fail "no resolver: set KNACK_STORY_BY or git user.name"
}

BY="${KNACK_STORY_BY:-$(git -C "$ROOT" config user.name)}"
preflight

WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-story.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
# A sandbox HOME: the real ~/.knack and Muse settings are never read or written.
export HOME="$WORK/home"
export KNACK_HOME="$HOME/.knack"
mkdir -p "$HOME"
# No GitHub credential, no other registry; the fake story has no model key either.
unset GITHUB_TOKEN KNACK_REGISTRY
[ "$MODELS" = fake ] && unset MODEL_API_KEY BASETEN_API_KEY
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="knack story" GIT_AUTHOR_EMAIL="story@example.com"
export GIT_COMMITTER_NAME="knack story" GIT_COMMITTER_EMAIL="story@example.com"

story() { "$PY" "$ROOT/scripts/one_story.py" "$1" "$WORK" "${@:2}"; }
if [ "$MODELS" = fake ]; then
  KNACK=("$PY" "$ROOT/scripts/one_story_fakes.py")
else
  KNACK=("$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))')
fi

echo "knack one story: the #75025 edit, one receipt chain. Models: $MODELS."
echo
story install || fail "install"
echo
story hook block || fail "block"
story run argue_hold "${KNACK[@]}" argue "$HOLD_OBJECTION" || fail "argue hold"
story run argue_escalate "${KNACK[@]}" argue "$ESCALATE_OBJECTION" || fail "argue escalate"
BLOCK="$(story deny)" || fail "block receipt"
story run resolve "${KNACK[@]}" resolve "$BLOCK" uphold --reason "$REASON" --by "$BY" || fail "resolve"
story hook corrected || fail "corrected edit"
story run verify "${KNACK[@]}" receipts verify || fail "receipts verify"
story assemble "$OUT" "$MODELS" || fail "assemble"
echo "kept: $OUT (knack receipts verify --path $OUT/receipts.jsonl)"
