#!/usr/bin/env bash
# Regenerates every number the README cites, each printed beside the command that produced it.
# Reads committed files only; no network, no model, no home registry. Exit 0 only if every step ran.
#
# Inputs (all tracked by git):
#   grid        data/registry (each rule's proof, stored by `knack reprove` from the PR's
#               base/head, data/variants, both data/heldout sets, the default branch and the
#               previous release), data/rules, data/roots, data/heldout, spikes/*compile*.log;
#               printed and checked byte for byte against bench/PROOF-GRID.md, never written
#   extraction  spikes/batch/apache-airflow/decisions.jsonl, spikes/batch/fastapi-fastapi/decisions.jsonl
#   held-out    data/heldout (same- and cross-model sets per PR), data/registry/airflow.json,
#               data/registry/fastapi.json and the data/rules they install
#   bench       bench/runs-1030c.jsonl, checked against bench/REPORT-1030c.md
#   repeats     bench/REPEATS.md (the hunt needs full clones, so its record is read, not re-run)
#   breadth     the above plus data/roots, bench/tickets.jsonl
#   e2e         scripts/e2e.sh and its committed scripts/fixtures
#
# Refuses to start while another knack or pytest process runs: e2e checks the real knack home
# is untouched, and another run can write there. The last line is PROOF: PASS or
# PROOF: FAIL (<step>), with exit 0 or 1 to match.
set -u -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-reproduce.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
RUNS="bench/runs-1030c.jsonl"
REPORT="bench/REPORT-1030c.md"
EXCLUDED="fastapi-16049"
GRID="bench/PROOF-GRID.md"
# Command lines of a knack or pytest run: the module, the CLI, the scripts, or pytest.
OTHERS='pytest|-m knack|knack[.]cli|/bin/knack( |$)|scripts/(e2e|reproduce|demo_block|live-smoke)[.]sh'
SECTION=""
FIRST_FAILED=""

reproduce() { "$PY" -m knack.reproduce "$@"; }
knack() { "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' "$@"; }

# failed [WHAT]: records the current section, or WHAT, as failed; the first one names the run.
failed() {
  [ -n "$FIRST_FAILED" ] || FIRST_FAILED="${1:-$SECTION}"
}

# fail SHOWN: marks the run failed and prints the step's stderr under the command.
fail() {
  echo "FAIL  \$ $1"
  sed 's/^/    /' "$WORK/err"
  failed
}

# section NAME: prints the header; later failures are charged to NAME.
section() {
  [ -z "$SECTION" ] || echo
  SECTION="$1"
  echo "== $1 =="
}

# ancestors: this script's pid and every parent's; a test runner above us is not another run.
ancestors() {
  local pid=$$
  while [ "${pid:-1}" -gt 1 ]; do
    echo "$pid"
    pid="$(ps -o ppid= -p "$pid" | tr -d ' ')"
  done
}

# other_runs MINE: from a ps snapshot on stdin, "pid command" of each knack or pytest process
# that is not in MINE (our ancestors), not our child (the snapshot's subshell), and not a
# shell -c wrapper, whose text may name pytest while its python child is the real run.
other_runs() {
  awk -v mine=" $1 " -v self=$$ -v re="$OTHERS" \
    'index(mine, " " $1 " ") == 0 && $2 != self && !(match($3, /sh$/) && $4 == "-c") \
      && match($0, re) { $2 = ""; print }'
}

# refuse_beside_other_runs: exits before any step when another knack or pytest process runs.
refuse_beside_other_runs() {
  [ "${KNACK_REPRODUCE_IGNORE_OTHERS:-}" = 1 ] && return 0
  local mine procs first
  mine="$(ancestors | tr '\n' ' ')"
  procs="$(ps -axo pid=,ppid=,command=)"
  first="$(printf '%s\n' "$procs" | other_runs "$mine" | head -n 1)"
  [ -z "$first" ] && return 0
  echo "reproduce.sh: refusing to start because another knack or pytest process is running (pid ${first%% *}:${first#* }); stop it and rerun." >&2
  echo "PROOF: FAIL (another knack or pytest is running)"
  exit 1
}

# summary: the one PROOF line, and the exit code to match.
summary() {
  echo
  if [ -z "$FIRST_FAILED" ]; then
    echo "PROOF: PASS"
    exit 0
  fi
  echo "PROOF: FAIL ($FIRST_FAILED)"
  exit 1
}

# cited SHOWN COMMAND...: runs COMMAND; prints each output line with SHOWN beside it.
cited() {
  local shown="$1" out
  shift
  out="$("$@" 2>"$WORK/err")" || { fail "$shown"; return 1; }
  printf '%s\n' "$out" | while IFS= read -r line; do
    printf '%s  $ %s\n' "$line" "$shown"
  done
}

bench_section() {
  local shown="knack bench report --runs $RUNS --exclude-ticket $EXCLUDED"
  knack bench report --runs "$RUNS" --exclude-ticket "$EXCLUDED" >"$WORK/report.md" 2>"$WORK/err" \
    || { fail "$shown"; return 1; }
  # The tables are markdown, so the command goes above them rather than beside each row.
  echo "\$ $shown"
  cat "$WORK/report.md"
  echo
  local same=no
  diff -q "$WORK/report.md" "$REPORT" >/dev/null && same=yes
  printf 'bench report matches %s: %s  $ diff <(%s) %s\n' "$REPORT" "$same" "$shown" "$REPORT"
  [ "$same" = yes ] || failed
}

grid_section() {
  local shown="python -m knack.reproduce grid"
  reproduce grid >"$WORK/grid.md" 2>"$WORK/err" || { fail "$shown"; return 1; }
  # A markdown table, so the command goes above it, as for the bench report.
  echo "\$ $shown"
  cat "$WORK/grid.md"
  echo
  # Checked against the committed grid, never written: a stranger's clone stays clean.
  local same=no
  diff -q "$WORK/grid.md" "$GRID" >/dev/null && same=yes
  printf 'proof grid matches %s: %s  $ diff <(%s) %s\n' "$GRID" "$same" "$shown" "$GRID"
  [ "$same" = yes ] || failed
}

e2e_section() {
  local shown="bash scripts/e2e.sh" passed total
  PYTHON="$PY" bash scripts/e2e.sh >"$WORK/e2e.out" 2>&1
  local status=$?
  passed="$(grep -c '^PASS ' "$WORK/e2e.out")"
  total="$(grep -cE '^(PASS|FAIL) ' "$WORK/e2e.out")"
  printf 'e2e steps passed: %s/%s  $ %s\n' "$passed" "$total" "$shown"
  if [ "$status" -ne 0 ]; then
    sed 's/^/    /' "$WORK/e2e.out"
    failed "e2e: $(grep -m 1 '^FAIL ' "$WORK/e2e.out" | sed 's/^FAIL //')"
  fi
}

cd "$ROOT" || exit 1
refuse_beside_other_runs

section "proof grid"
grid_section
section "extraction"
cited "python -m knack.reproduce extraction" reproduce extraction
section "held-out"
cited "python -m knack.reproduce heldout" reproduce heldout
section "bench"
bench_section
section "repeats"
cited "python -m knack.reproduce repeats" reproduce repeats
section "breadth"
cited "python -m knack.reproduce breadth" reproduce breadth
section "e2e"
e2e_section
summary
