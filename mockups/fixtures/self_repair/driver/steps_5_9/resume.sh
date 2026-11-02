#!/usr/bin/env bash
# KN-97 live: resume the KN-114 sandbox at step 5. One gated confirm, then replays and receipts verify.
set -u -o pipefail
REPO="/Users/vedant/Documents/knack"
PY="$REPO/.venv/bin/python"
HERE="$(cd "$(dirname "$0")" && pwd)"
W="/var/folders/k9/5rtt8_bd2s5cjgmgzknpl3qc0000gn/T/knack-kn114.itVgOH"
echo "sandbox: $W"; date -u +"resumed %Y-%m-%dT%H:%M:%SZ"
export HOME="$W/home" KNACK_HOME="$W/home/.knack" KNACK_REGISTRY="$W/data/registry/airflow.json"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export KNACK_SPIKE_MODELS="$W/models.jsonl"
RULE="$W/data/rules/airflow/75025.yml"; ROOT_FILE="$W/data/roots/airflow/75025.json"
KNACK=("$PY" "$HERE/traced.py"); N=9
stop() { echo "STOPPED at: $1 (sandbox kept: $W)"; exit 1; }
step() {
  N=$((N + 1)); local name="$1"; shift
  local log="$W/log/$(printf %02d $N)_$name.txt" start end rc
  { echo "\$ $*"; echo; } >"$log"
  start=$("$PY" -c 'import time; print(time.time())')
  (cd "$W/airflow"; env KNACK_SPIKE_STEP="$name" "$@") >>"$log" 2>&1; rc=$?
  end=$("$PY" -c 'import time; print(time.time())')
  echo "" >>"$log"; echo "exit $rc, wall $("$PY" -c "print(round(($end-$start)*1000,1))") ms" >>"$log"
  echo "== $name (exit $rc) =="; cat "$log"; echo; return $rc
}
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
hook() { step "$1" "$PY" "$HERE/steps.py" hook "$REPO" "$W" "$1" "$2" "$3"; }
# The hook now runs this repo's knack (main e81e98d), not the knack-gate worktree.
"$PY" - "$W/home/.config/muse/settings.json" "$PY" <<'PYEOF'
import json, shlex, sys
p, py = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = f"sh -c {shlex.quote(shlex.quote(py) + ' -m knack.hooks.pretool || true')}"
open(p, "w").write(json.dumps(d, indent=2) + "\n"); print("hook:", d["hooks"]["PreToolUse"][0]["hooks"][0]["command"])
PYEOF
V2="$(sha "$RULE")"; echo "rule on disk: $V2"
step 05b_knack_confirm_retry "${KNACK[@]}" confirm airflow-75025-1 --registry "$KNACK_REGISTRY" --by "Vedant Srivastava" || stop "5b: second confirm failed"
cp "$ROOT_FILE" "$W/rule/root_after.json"
PINNED="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["rule_sha"])' "$ROOT_FILE")"
echo "root pinned to: $PINNED"; [ "$PINNED" = "$V2" ] || stop "5b: root pinned to $PINNED, not v2 $V2"
hook 06_evasion_denied miss deny || stop "6: v2 did not deny the evasion"
hook 07_compliant_allowed compliant allow || stop "7: v2 did not allow compliant_3.py"
hook 08_corrected_allowed corrected allow || stop "8: the corrected edit was not allowed"
step 09_receipts_verify "${KNACK[@]}" receipts verify || stop "9: chain did not verify"
date -u +"finished %Y-%m-%dT%H:%M:%SZ"; echo "DONE: v2 $V2 pinned; sandbox $W"
