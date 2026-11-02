#!/usr/bin/env bash
# KN-114 self-repair, one live run: evasion allowed + compliant denied -> both cases -> knack false-block
# -> knack confirm (gate) -> evasion denied, compliant allowed, corrected allowed -> receipts verify.
# Sandbox HOME/KNACK_HOME and a temp copy of data/; the committed registry and ~/.knack are never touched.
set -u -o pipefail

REPO="/Users/vedant/Documents/knack-gate"
PY="$REPO/.venv/bin/python"
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$(mktemp -d "${TMPDIR:-/tmp}/knack-kn114.XXXXXX")"
echo "sandbox: $W"
date -u +"started %Y-%m-%dT%H:%M:%SZ"
export HOME="$W/home" KNACK_HOME="$W/home/.knack"
mkdir -p "$HOME" "$W/log" "$W/rule"
cp -R "$REPO/data" "$W/data"
export KNACK_REGISTRY="$W/data/registry/airflow.json"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="knack self-repair" GIT_AUTHOR_EMAIL="self-repair@example.com"
export GIT_COMMITTER_NAME="knack self-repair" GIT_COMMITTER_EMAIL="self-repair@example.com"
export KNACK_SPIKE_MODELS="$W/models.jsonl"
RULE="$W/data/rules/airflow/75025.yml"
ROOT_FILE="$W/data/roots/airflow/75025.json"
KNACK=("$PY" "$HERE/traced.py")
N=0

stop() { echo "STOPPED at: $1 (sandbox kept: $W)"; exit 1; }
steps() { "$PY" "$HERE/steps.py" "$1" "$REPO" "$W" "${@:2}"; }
step() {
  N=$((N + 1)); local name="$1"; shift
  local log="$W/log/$(printf %02d $N)_$name.txt" start end rc
  { echo "\$ $*"; echo; } >"$log"
  start=$("$PY" -c 'import time; print(time.time())')
  (cd "$W/airflow" 2>/dev/null || cd "$W"; env KNACK_SPIKE_STEP="$name" "$@") >>"$log" 2>&1; rc=$?
  end=$("$PY" -c 'import time; print(time.time())')
  echo "" >>"$log"; echo "exit $rc, wall $("$PY" -c "print(round(($end-$start)*1000,1))") ms" >>"$log"
  echo "== $name (exit $rc) =="; cat "$log"; echo
  return $rc
}
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
hook() { step "$1" "$PY" "$HERE/steps.py" hook "$REPO" "$W" "$1" "$2" "$3"; }

steps install || stop install
cp "$RULE" "$W/rule/v1.yml"; cp "$ROOT_FILE" "$W/rule/root_before.json"
V1="$(sha "$RULE")"; echo "rule v1 sha: $V1"

hook 01_evasion_allowed miss allow || stop "1: the evasion was not allowed"
MISS="$(steps receipt airflow-75025 allow)" || stop "1: no allow receipt"; echo "evasion allow receipt: $MISS"
hook 02_compliant_denied compliant deny || stop "2: v1 did not deny compliant_3.py"
FALSE="$(steps receipt airflow-75025 deny)" || stop "2: no deny receipt"; echo "compliant deny receipt: $FALSE"

step 03_record_must_fail "$PY" "$HERE/steps.py" record "$REPO" "$W" "$MISS" || stop "3: must-fail case not recorded"
step 04_knack_false_block "${KNACK[@]}" false-block "$FALSE" --registry "$KNACK_REGISTRY" --work "$W/work" || stop "4: knack false-block did not install"
cp "$RULE" "$W/rule/v2.yml"; V2="$(sha "$RULE")"; echo "rule v2 sha: $V2"
[ "$V1" != "$V2" ] || stop "4: the rule did not change"
diff -u "$W/rule/v1.yml" "$W/rule/v2.yml" >"$W/rule/v1_v2.diff"; cat "$W/rule/v1_v2.diff"

step 05_knack_confirm "${KNACK[@]}" confirm airflow-75025-1 --registry "$KNACK_REGISTRY" --by "Vedant Srivastava" || stop "5: confirm failed"
cp "$ROOT_FILE" "$W/rule/root_after.json"
PINNED="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["rule_sha"])' "$ROOT_FILE")"
echo "root pinned to: $PINNED"; [ "$PINNED" = "$V2" ] || stop "5: root pinned to $PINNED, not v2 $V2"

hook 06_evasion_denied miss deny || stop "6: v2 did not deny the evasion"
hook 07_compliant_allowed compliant allow || stop "7: v2 did not allow compliant_3.py"
hook 08_corrected_allowed corrected allow || stop "8: the corrected edit was not allowed"
step 09_receipts_verify "${KNACK[@]}" receipts verify || stop "9: chain did not verify"
date -u +"finished %Y-%m-%dT%H:%M:%SZ"
echo "DONE: v1 $V1 -> v2 $V2; sandbox $W"
