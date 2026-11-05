#!/usr/bin/env bash
# Fixture check: intentionally fails so the case can detect a skipped run.
set -euo pipefail
expected=4
actual="$(bash src/calc.sh 2>/dev/null || echo 0)"
if [ "$actual" != "$expected" ]; then
  echo "FAIL: expected ${expected}, got ${actual}"
  exit 1
fi
echo "PASS: got ${expected}"
