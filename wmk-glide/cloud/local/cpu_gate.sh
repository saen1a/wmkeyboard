#!/usr/bin/env bash
# Mandatory 2 000-step CPU convergence gate. Ubuntu 26.04 CPU venv.
#
# Usage:
#   bash cpu_gate.sh <data_dir> <out_dir> [distill=]
#
# Asserts:
#   * log contains "device cpu"
#   * log contains no "nan" / "inf" (the lr token is stripped, not the line)
#   * running TRAINING loss at the last printed step < at the first
# Exits non-zero otherwise, printing both loss values on failure.

set -euo pipefail

DATA="${1:?data_dir required}"
OUT="${2:?out_dir required}"
DISTILL="${3:-}"
PY="${PY:-/home/saenta/wmlm-de/.venv-distill/bin/python}"
TRAIN="${TRAIN:-tools/wmlm/train.py}"

mkdir -p "$OUT"
LOG="$OUT/run.log"

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"

OPTS=(
    steps=2000 batch=64 d=256 layers=6 heads=4 ff=768 ctx=40 eval_every=200
)
[ -n "$DISTILL" ] && OPTS+=("distill=$DISTILL")

echo ">>> $PY $TRAIN $DATA $OUT ${OPTS[*]}"
"$PY" "$TRAIN" "$DATA" "$OUT" "${OPTS[@]}" 2>&1 | tee "$LOG"

# Assertion 1: device cpu.
if ! grep -q "device cpu" "$LOG"; then
    echo "FAIL: 'device cpu' not in log" >&2
    exit 2
fi

# Assertion 2: no nan/inf. The lr token sits on the same line as the loss
# ("step N loss X ppl Y lr Z"), so strip only the lr token -- a whole-line
# `grep -v` would delete every training line and make this check vacuous.
tmp="$(mktemp)"
sed -E 's/lr [0-9.eE+-]+//' "$LOG" > "$tmp"
if grep -iE "\\b(nan|inf)\\b" "$tmp" >/dev/null; then
    echo "FAIL: nan/inf in log (after stripping only the lr token):" >&2
    grep -iE "\\b(nan|inf)\\b" "$tmp" >&2
    rm -f "$tmp"
    exit 3
fi
rm -f "$tmp"

# Assertion 3: training loss falls.
# On a 10k-row slice the model memorises, so heldout ppl RISES by design
# (measured 2026-10-31); the gate is the running training loss, and the
# heldout curve is printed as a diagnostic.
mapfile -t steps < <(grep -oE "step [0-9]+ loss [0-9.]+" "$LOG" || true)
if [ "${#steps[@]}" -lt 2 ]; then
    echo "FAIL: need at least 2 'step ... loss ...' lines, found ${#steps[@]}" >&2
    exit 4
fi
loss_first="$(echo "${steps[0]}"  | awk '{print $NF}')"
loss_last="$(echo  "${steps[-1]}" | awk '{print $NF}')"
echo "train loss first=$loss_first last=$loss_last  (last line: ${steps[-1]})"
grep -oE "eval step [0-9]+ heldout loss [0-9.]+ ppl [0-9.]+" "$LOG" | tail -3 || true

awk -v a="$loss_first" -v b="$loss_last" 'BEGIN{exit !(a+0 > b+0)}' \
    || { echo "FAIL: training loss did not fall (first $loss_first, last $loss_last)" >&2; exit 5; }

echo "PASS: training loss $loss_first -> $loss_last"
