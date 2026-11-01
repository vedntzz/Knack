#!/usr/bin/env bash
# KN-78 demo opener: run 3's recorded edit, blocked by the real user-level PreToolUse hook.
# A clean sandbox HOME and clone every run; committed fixtures only. No model, no network.
# Same output every run except what is measured: two latencies and the receipt hash in
# the Console link (the receipt chains its timestamp).
set -u -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-demo.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

ROUTES="airflow-core/src/airflow/api_fastapi/core_api/routes"
BASE="$ROOT/scripts/fixtures/75025/base"
RUN3="tests/guard/fixtures/replay/run_neutral_3.diff"
CLONE="$WORK/airflow"
SETTINGS="$WORK/home/.config/muse/settings.json"
REGISTRY_DIR="$WORK/home/.knack/registries/apache-airflow"

# fail WHAT: names the step that broke, on stderr, and stops the demo.
fail() {
  echo "demo_block: $1 failed" >&2
  exit 1
}

make_clone() {
  # #75025's pre-fix route files, in a repo whose origin is apache/airflow.
  mkdir -p "$CLONE/$ROUTES/public" "$CLONE/$ROUTES/ui" || return 1
  cp "$BASE/$ROUTES/public/dags.py" "$CLONE/$ROUTES/public/dags.py" || return 1
  cp "$BASE/$ROUTES/ui/dags.py" "$CLONE/$ROUTES/ui/dags.py" || return 1
  git -C "$CLONE" init -q -b main || return 1
  git -C "$CLONE" remote add origin https://github.com/apache/airflow.git || return 1
  git -C "$CLONE" add -A && git -C "$CLONE" commit -q -m base
}

install_registry() {
  # The committed airflow registry, roots as recorded (no promotion), where knack init puts it.
  "$PY" - "$ROOT/data/registry/airflow.json" "$REGISTRY_DIR" <<'EOF'
import json, shutil, sys
from pathlib import Path
source, out = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(source.read_text())
shutil.copytree(source.parent / data["roots_dir"], out / "roots")
(out / "rules").mkdir()
for entry in data["rules"]:
    rule = source.parent / entry["rule"]
    shutil.copy(rule, out / "rules" / rule.name)
    entry["rule"] = f"rules/{rule.name}"
data["roots_dir"] = "roots"
(out / "registry.json").write_text(json.dumps(data, indent=2) + "\n")
print(f"registry: {data['repo']}, {len(data['rules'])} rules -> ~/.knack/registries/{out.name}")
EOF
}

install_hook() {
  # The user-level Muse hook: every write_file/edit_file goes through knack.hooks.pretool.
  "$PY" - "$SETTINGS" "$PY" <<'EOF'
import json, shlex, sys
from pathlib import Path
settings, python = Path(sys.argv[1]), sys.argv[2]
command = f"sh -c {shlex.quote(shlex.quote(python) + ' -m knack.hooks.pretool || true')}"
entry = {"matcher": "write_file|edit_file", "hooks": [{"type": "command", "command": command}]}
settings.parent.mkdir(parents=True)
settings.write_text(json.dumps({"schema_version": 1, "hooks": {"PreToolUse": [entry]}}, indent=2) + "\n")
print("user hook: ~/.config/muse/settings.json PreToolUse write_file|edit_file -> knack.hooks.pretool")
EOF
}

replay_run3() {
  # Each hunk of run 3 becomes the edit_file event Muse sends; the installed command runs it.
  "$PY" - "$ROOT/$RUN3" "$CLONE" "$SETTINGS" "$WORK/home/.knack/verdicts.jsonl" <<'EOF'
import json, subprocess, sys, time
from pathlib import Path
diff, clone, settings, receipts = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
command = json.loads(settings.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
hunks, path = [], None
for line in diff.read_text().splitlines():
    if line.startswith("+++ b/"):
        path = line[6:]
    elif line.startswith("@@"):
        hunks.append((path, [], []))
    elif hunks and line[:1] in (" ", "-", "+") and not line.startswith(("---", "+++")):
        # Context lines go to both sides; removed to find, added to replace.
        if line[0] != "+":
            hunks[-1][1].append(line[1:])
        if line[0] != "-":
            hunks[-1][2].append(line[1:])
for path, find, replace in hunks:
    if not (clone / path).is_file():
        print(f"not replayed: {path} (not in the sandbox clone)")
        continue
    tool_input = {"path": path, "find": "\n".join(find), "replace": "\n".join(replace)}
    event = {"hook_event_name": "PreToolUse", "tool_name": "edit_file", "tool_input": tool_input, "cwd": str(clone), "session_id": "demo-run3"}
    print(f"edit_file {path}: -{len(find)} +{len(replace)} lines")
    started = time.perf_counter()
    done = subprocess.run(["sh", "-c", command], input=json.dumps(event), capture_output=True, text=True, cwd=clone)
    elapsed = (time.perf_counter() - started) * 1000
    if not done.stdout.strip():
        sys.exit(f"hook allowed {path}; stderr: {done.stderr}")
    envelope = json.loads(done.stdout)
    deny = [json.loads(r) for r in receipts.read_text().splitlines() if json.loads(r)["decision"] == "deny"][-1]
    print("\n== deny payload ==")
    print(done.stdout.strip())
    print("\n== reason, as the agent reads it ==")
    print(envelope["hookSpecificOutput"]["permissionDecisionReason"])
    print("\n== latency ==")
    print(f"guard verdict: {deny['latency_ms']:.1f} ms (ast-grep scan, from the deny receipt)")
    print(f"hook round trip: {elapsed:.0f} ms (sh -c, Python start to deny envelope, as Muse runs it)")
    sys.exit(0)
sys.exit("no hunk of run 3 reached the hook")
EOF
}

# A sandbox HOME: the real ~/.knack and Muse settings are never read or written.
export HOME="$WORK/home"
mkdir -p "$HOME"
# No credential reaches the hook; git reads no user config.
unset GITHUB_TOKEN MODEL_API_KEY BASETEN_API_KEY KNACK_REGISTRY
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="knack demo" GIT_AUTHOR_EMAIL="demo@example.com"
export GIT_COMMITTER_NAME="knack demo" GIT_COMMITTER_EMAIL="demo@example.com"
cd "$ROOT" || exit 1

echo "knack demo: an agent's recorded edit (run 3) meets the PreToolUse hook. No model, no network."
echo
echo "== install =="
make_clone || fail "sandbox clone"
echo "clone: apache/airflow at the base of #75025"
install_registry || fail "registry install"
install_hook || fail "hook install"
echo
echo "== replay $RUN3 =="
replay_run3 || fail "run 3 replay"
