#!/usr/bin/env bash
# KN-113: posttoolbatch_live.sh with watch's three keys only in files in the sandbox's KNACK_HOME, none exported.
# Real models, one run, no retries. Temp HOME and KNACK_HOME; the real ~/.knack is only read (github_token).
set -u -o pipefail
ROOT=/Users/vedant/Documents/knack
PY="$ROOT/.venv/bin/python"
S=/private/tmp/claude-501/-Users-vedant-Documents-knack/8a14c651-6e15-420d-8a70-0e98b3e44052/scratchpad
W="$(mktemp -d "$S/ptb.XXXXXX")"
echo "W=$W"
REAL_HOME="$HOME"
export HOME="$W/home" KNACK_HOME="$W/home/.knack"
# The keys go into files, mode 600, never printed; then they leave the environment.
mkdir -p "$KNACK_HOME"
(umask 077 && cp "$REAL_HOME/.knack/github_token" "$KNACK_HOME/github_token" \
  && printf %s "$MODEL_API_KEY" > "$KNACK_HOME/model_api_key" \
  && printf %s "$BASETEN_API_KEY" > "$KNACK_HOME/baseten_api_key") || { echo "key files failed"; exit 1; }
chmod 600 "$KNACK_HOME/github_token" "$KNACK_HOME/model_api_key" "$KNACK_HOME/baseten_api_key"
unset GITHUB_TOKEN MODEL_API_KEY BASETEN_API_KEY META_API_KEY
echo "--- key files"; for f in github_token model_api_key baseten_api_key; do stat -f "%Sp %z bytes \$KNACK_HOME/$f" "$KNACK_HOME/$f"; done
echo "key vars in env: $(env | grep -c -E '^(GITHUB_TOKEN|MODEL_API_KEY|BASETEN_API_KEY|META_API_KEY)=')"
unset XDG_CONFIG_HOME XDG_DATA_HOME XDG_STATE_HOME XDG_CACHE_HOME KNACK_REGISTRY
mkdir -p "$HOME"
MUSE_SETTINGS="$HOME/.config/muse/settings.json"
BASE=70a781622611f09ec34f0bbc34c4f05c59ad4c67
HEAD=91da700f20f5cad271869fb681953f6d877c75f2
FILES="providers/common/compat/src/airflow/providers/common/compat/_resumable_job_mixin.py
providers/common/compat/tests/unit/common/compat/test__resumable_job_mixin.py"
knack() { (cd "$W/airflow" && "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' "$@"); }
fetch() { curl -sf -H "Authorization: Bearer $(cat "$KNACK_HOME/github_token")" -H "Accept: application/vnd.github.raw" "https://api.github.com/repos/apache/airflow/contents/$2?ref=$1"; }

# The registry: a copy of the committed data/, as it was before #75271 merged.
cp -R "$ROOT/data" "$W/data"
"$PY" - "$W/data/registry/airflow.json" <<'PY'
import json, sys
path = sys.argv[1]; d = json.load(open(path))
d["rules"] = [e for e in d["rules"] if "75271" not in e["rule"]]
open(path, "w").write(json.dumps(d, indent=2) + "\n")
PY
rm "$W/data/rules/airflow/75271.yml" "$W/data/roots/airflow/75271-1.json" "$W/data/roots/airflow/75271-2.json"
rm -r "$W/data/heldout/airflow/75271"
cp "$W/data/registry/airflow.json" "$W/airflow.before.json"

# The sandbox clone: #75271's base files, origin apache/airflow; branch pr-75271 holds the head.
mkdir -p "$W/airflow"
for f in $FILES; do mkdir -p "$W/airflow/$(dirname "$f")"; fetch "$BASE" "$f" > "$W/airflow/$f" || { echo "fetch base $f failed"; exit 1; }; done
git -C "$W/airflow" init -q -b main
git -C "$W/airflow" remote add origin https://github.com/apache/airflow.git
git -C "$W/airflow" add -A && git -C "$W/airflow" -c user.name=live -c user.email=live@example.com commit -q -m base

echo "\$ knack watch --registry \$W/data/registry/airflow.json --muse-settings \$HOME/.config/muse/settings.json"
knack watch --registry "$W/data/registry/airflow.json" --muse-settings "$MUSE_SETTINGS" 2>&1
echo "exit $?"
echo "--- \$HOME/.config/muse/settings.json"; cat "$MUSE_SETTINGS"

(cd "$W/airflow" && git checkout -q -b pr-75271 \
  && for f in $FILES; do fetch "$HEAD" "$f" > "$f" || exit 1; done \
  && git -c user.name=live -c user.email=live@example.com commit -q -am "Live proof merge (#75271)" \
  && git checkout -q main) || { echo "head fixture failed"; exit 1; }
echo "main at $(git -C "$W/airflow" rev-parse --short HEAD), pr-75271 at $(git -C "$W/airflow" rev-parse --short pr-75271)"

# One real Muse Code session, as the bench runs it. Muse's own model key is passed to muse only, as before.
echo "watch.json before muse: $(cat "$W/data/registry/watch.json")"
SESSION="$(uuidgen | tr 'A-Z' 'a-z')"
PROMPT='Run exactly this one shell command in the current directory, once, and then stop: git -c core.hooksPath=/dev/null merge --ff-only pr-75271'
echo "\$ muse exec --disable-web-tools --disable-request-user-input --session-id $SESSION '$PROMPT'"
(cd "$W/airflow" && MUSE_NO_AUTO_UPDATE=1 META_API_KEY="$(cat "$KNACK_HOME/model_api_key")" \
  muse exec --disable-web-tools --disable-request-user-input --session-id "$SESSION" "$PROMPT") > "$W/muse_exec.log" 2>&1
echo "muse exit $?"
cat "$W/muse_exec.log"
echo "main now at $(git -C "$W/airflow" rev-parse --short HEAD)"
(cd "$W/airflow" && MUSE_NO_AUTO_UPDATE=1 muse export --session "$SESSION" --out "$W/export.json") 2>&1
echo "export exit $?"
echo "SESSION=$SESSION"

# Wait for watch's background run to exit, at most 30 min; a failed run leaves watch.json as it was.
for i in $(seq 180); do
  pgrep -f "knack.watch.hook post-merge --registry $W" > /dev/null || break
  sleep 10
done
echo "--- background run gone after ~$(( (i - 1) * 10 ))s (pgrep: $(pgrep -f "knack.watch.hook post-merge --registry $W" | wc -l | tr -d ' ') left)"
echo "--- watch.json after: $(cat "$W/data/registry/watch.json")"
echo "--- watch.log"; cat "$W/data/registry/watch.log"
echo "--- work"; ls -R "$W/data/registry/work" 2>&1 | head -40
echo "--- registry diff"; diff "$W/airflow.before.json" "$W/data/registry/airflow.json"
echo "--- key values found outside the key files"
for f in github_token model_api_key baseten_api_key; do
  echo "$f: $(grep -rlF -f "$KNACK_HOME/$f" "$W" | grep -v -x "$KNACK_HOME/$f" | wc -l | tr -d ' ') files"
  grep -rlF -f "$KNACK_HOME/$f" "$W" | grep -v -x "$KNACK_HOME/$f" | sed "s#$W#\$W#"
done
