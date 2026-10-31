#!/usr/bin/env bash
# Regenerates every number the README cites, each printed beside the command that produced it.
# Reads committed files only; no network, no model, no home registry. Exit 0 only if every step ran.
#
# Inputs (all tracked by git):
#   grid        data/registry, data/rules, data/roots, data/heldout, spikes/*compile*.log;
#               written to bench/PROOF-GRID.md as well as printed
#   extraction  spikes/batch/apache-airflow/decisions.jsonl, spikes/batch/fastapi-fastapi/decisions.jsonl
#   held-out    data/heldout (same- and cross-model sets per PR), data/registry/airflow.json,
#               data/registry/fastapi.json and the data/rules they install
#   bench       bench/runs-1030c.jsonl, checked against bench/REPORT-1030c.md
#   repeats     bench/REPEATS.md (the hunt needs full clones, so its record is read, not re-run)
#   breadth     the above plus data/roots, bench/tickets.jsonl
#   e2e         scripts/e2e.sh and its committed scripts/fixtures
set -u -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/knack-reproduce.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
RUNS="bench/runs-1030c.jsonl"
REPORT="bench/REPORT-1030c.md"
EXCLUDED="fastapi-16049"
GRID="bench/PROOF-GRID.md"
FAILED=0

reproduce() { "$PY" -m knack.reproduce "$@"; }
knack() { "$PY" -c 'import sys; from knack.cli import main; sys.exit(main(sys.argv[1:]))' "$@"; }

# fail SHOWN: marks the run failed and prints the step's stderr under the command.
fail() {
  echo "FAIL  \$ $1"
  sed 's/^/    /' "$WORK/err"
  FAILED=1
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
  [ "$same" = yes ] || FAILED=1
}

grid_section() {
  local shown="python -m knack.reproduce grid"
  reproduce grid >"$WORK/grid.md" 2>"$WORK/err" || { fail "$shown"; return 1; }
  # A markdown table, so the command goes above it, as for the bench report.
  echo "\$ $shown > $GRID"
  cat "$WORK/grid.md"
  cp "$WORK/grid.md" "$GRID"
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
    FAILED=1
  fi
}

cd "$ROOT" || exit 1

echo "== proof grid =="
grid_section
echo
echo "== extraction =="
cited "python -m knack.reproduce extraction" reproduce extraction
echo
echo "== held-out =="
cited "python -m knack.reproduce heldout" reproduce heldout
echo
echo "== bench =="
bench_section
echo
echo "== repeats =="
cited "python -m knack.reproduce repeats" reproduce repeats
echo
echo "== breadth =="
cited "python -m knack.reproduce breadth" reproduce breadth
echo
echo "== e2e =="
e2e_section

exit "$FAILED"
