#!/usr/bin/env bash
# Usage: guard_changed.sh RULE ROOT FILE... ; exits 1 if any file is blocked.
set -uo pipefail

knack="${KNACK:-.venv/bin/knack}"
rule="$1"
root="$2"
shift 2

blocked=0
for file in "$@"; do
  echo "== $file"
  # knack exits 1 only on a block; guard errors fail open with exit 0.
  "$knack" guard check "$file" --rule "$rule" --root "$root" || blocked=1
done
exit "$blocked"
