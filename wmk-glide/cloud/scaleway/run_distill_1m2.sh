#!/usr/bin/env bash
# Teacher pass on one H100: sharded vLLM collection, two retry passes, then
# an atomic merge and validation. Works for 1.2M and 2M.
#
#   TOTAL=0       all sentences in $DATA_DIR/train.npz (recommended)
#   TOTAL=1200000 a random 1.2M subset (only useful if the corpus is larger)
#
#   bash run_distill_1m2.sh out/de_soft_1m2.npz out/de_lm_1m2
#
# Interrupting is safe: valid shards are skipped, a partial shard resumes
# from its last checkpoint, and merge_soft.py writes the final npz
# atomically. Pass 1 uses attempts=3, pass 2 only the failures with
# attempts=10.
set -euo pipefail

OUT=${1:?usage: run_distill_1m2.sh <out.npz> <data dir>}
DATA_DIR=${2:?usage: run_distill_1m2.sh <out.npz> <data dir>}
TOTAL=${TOTAL:-0}
SHARD_SIZE=${SHARD_SIZE:-5000}
BATCH=${BATCH:-32}
ATTEMPTS1=${ATTEMPTS1:-3}
ATTEMPTS2=${ATTEMPTS2:-10}
TOP_K=${TOPK:-24}
MODEL=${TEACHER_MODEL:-${TEACHER_MODEL_ID:-Qwen/Qwen3.8-27B-FP8}}
PY=${PY:-${VLLM_PY:-/opt/vllm-venv/bin/python}}
VOCAB=${VOCAB:-24576}
MAX_NLL=${MAX_NLL:-12}
EUR_PER_HOUR=${EUR_PER_HOUR:-2.88775}
MAX_HOURS=${MAX_HOURS:-12}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=${ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}
LOG=${LOG:-$(dirname "$OUT")/teacher_$(basename "${OUT%.npz}").log}
SHARD_DIR=${SHARD_DIR:-$(dirname "$OUT")/$(basename "${OUT%.npz}")_shards}
mkdir -p "$(dirname "$OUT")" "$SHARD_DIR"
exec > >(tee -a "$LOG") 2>&1
echo "=== teacher run $(date -Is) out=$OUT data=$DATA_DIR total=${TOTAL:-all}"

EXPECT=$("$PY" - "$DATA_DIR/train.npz" <<'PY'
import sys
import numpy as np
z = np.load(sys.argv[1])
print(len(z["starts"]) - 1)
PY
)
if [ "$TOTAL" != "0" ] && [ "$TOTAL" -gt "$EXPECT" ]; then
  echo "WARN: TOTAL=$TOTAL > $EXPECT sentences in train.npz; using all"
  TOTAL=$((EXPECT))
fi
echo "train.npz: $EXPECT sentences, collecting ${TOTAL:-$EXPECT}"
# The merge expects exactly the number of sentences that were selected.
if [ "$TOTAL" != "0" ]; then
  EXPECT_TOTAL=$TOTAL
else
  EXPECT_TOTAL=$EXPECT
fi

COMMON=(
  "$DATA_DIR" "$OUT"
  --model "$MODEL" --sentences "$EXPECT" --shard-size "$SHARD_SIZE"
  --batch "$BATCH" --topk "$TOP_K" --max-nll "$MAX_NLL"
  --shard-dir "$SHARD_DIR"
)
if [ "$TOTAL" != "0" ] && [ "$TOTAL" -lt "$EXPECT" ]; then
  COMMON+=(--count "$TOTAL")
fi

# Budget stop: never bill past MAX_BUDGET_EUR or MAX_HOURS unattended.
# One deadline for the whole script (not one per pass), so pass 2 can only
# spend what pass 1 left; otherwise two passes could double the cap.
MAX_BUDGET_EUR=${MAX_BUDGET_EUR:-50}
BUDGET_H=$(awk -v b="$MAX_BUDGET_EUR" -v r="$EUR_PER_HOUR" 'BEGIN{printf "%.2f", b/r}')
WALL_H=$(awk -v a="$BUDGET_H" -v b="$MAX_HOURS" 'BEGIN{printf "%.2f", (a<b?a:b)}')
WALL_S=$(awk -v h="$WALL_H" 'BEGIN{printf "%d", h*3600}')
DEADLINE=$(( $(date +%s) + WALL_S ))
echo "budget: ${MAX_BUDGET_EUR} EUR = ${BUDGET_H} h, wall-clock cap ${WALL_H} h (${WALL_S}s, one deadline)"

remaining() {
  local r=$(( DEADLINE - $(date +%s) ))
  [ "$r" -gt 0 ] || r=0
  echo "$r"
}

# Runs "$@" with only the budget that is left; returns 124 when it is spent.
run_with_deadline() {
  local remain
  remain=$(remaining)
  if [ "$remain" -le 30 ]; then
    return 124
  fi
  if command -v timeout >/dev/null; then
    timeout --signal=INT --kill-after=120 "$remain" "$@"
  else
    "$@"
  fi
}

echo "=== pass 1 (attempts=$ATTEMPTS1, remaining=$(remaining)s) $(date -Is)"
set +e
run_with_deadline "$PY" "$SCRIPT_DIR/distill_vllm.py" "${COMMON[@]}" --attempts "$ATTEMPTS1"
RC1=$?
set -e
if [ "$RC1" = "124" ] || [ "$RC1" = "130" ]; then
  echo "FAIL: wall-clock/budget cap ${WALL_H} h reached in pass 1; stopping before merge." >&2
  echo "      Valid shards are kept; raise MAX_HOURS/MAX_BUDGET_EUR or resume later." >&2
  exit 3
elif [ "$RC1" != "0" ]; then
  echo "FAIL: pass 1 exited $RC1" >&2
  exit 1
fi

FAILURES="$SHARD_DIR/failures.jsonl"
if [ -f "$FAILURES" ] && grep -q '"event": "failed"' "$FAILURES"; then
  if [ "$(remaining)" -le 120 ]; then
    echo "FAIL: budget exhausted before pass 2; not retrying." >&2
    exit 3
  fi
  echo "=== pass 2: retrying permanent failures (attempts=$ATTEMPTS2, remaining=$(remaining)s) $(date -Is)"
  run_with_deadline "$PY" "$SCRIPT_DIR/distill_vllm.py" "${COMMON[@]}" \
    --retry-failures "$FAILURES" --attempts "$ATTEMPTS2"
else
  echo "=== pass 2: no permanent failures recorded"
fi

mapfile -t SHARDS < <(find "$SHARD_DIR" -maxdepth 1 -name '*.npz' \
  ! -name '*.partial.npz' ! -name '*.tmp.npz' | sort)
if [ "${#SHARDS[@]}" = "0" ]; then
  echo "FAIL: no shards in $SHARD_DIR" >&2
  exit 1
fi
INCOMPLETE=$(find "$SHARD_DIR" -maxdepth 1 -name '*.INCOMPLETE' | wc -l)
MISSING=$(cat "$SHARD_DIR"/*.INCOMPLETE 2>/dev/null | grep -c . || true)
echo "shards: ${#SHARDS[@]}, incomplete shards: $INCOMPLETE ($MISSING sentences missing)"
if [ "$INCOMPLETE" != "0" ]; then
  if [ "${PARTIAL_MERGE:-0}" = "1" ]; then
    # Staged runs and smoke tests: merge what is complete. Incomplete shards
    # are kept too — the sentences that did succeed are valid rows.
    echo "PARTIAL_MERGE=1: $INCOMPLETE shard(s) incomplete; merging their valid sentences as well"
  else
    echo "FAIL: $INCOMPLETE shard(s) still incomplete after pass 2; not merging." >&2
    echo "      Re-run this script (it resumes), inspect $SHARD_DIR/*.INCOMPLETE," >&2
    echo "      or set PARTIAL_MERGE=1 for a staged/smoke run." >&2
    exit 1
  fi
fi
# With --count the run collects a prefix of the selection; a partial merge
# must expect exactly the sentences that are on disk, not the full corpus.
if [ "${PARTIAL_MERGE:-0}" = "1" ] || [ "$EXPECT_TOTAL" != "$EXPECT" ]; then
  EXPECT_TOTAL=$("$PY" - "${SHARDS[@]}" <<'PY'
import sys
import numpy as np
print(sum(len(np.load(p, allow_pickle=False)["sentences"]) for p in sys.argv[1:]))
PY
)
  echo "partial merge: expecting $EXPECT_TOTAL sentences from ${#SHARDS[@]} shards"
fi

echo "=== merge $(date -Is)"
"$PY" "$ROOT/wmk-glide/tools/merge_soft.py" "$OUT" "${SHARDS[@]}" \
  --vocab-size "$VOCAB" --expect-sentences "$EXPECT_TOTAL" --min-mass-ratio 0.90

echo "=== validate $(date -Is)"
"$PY" "$ROOT/wmk-glide/tools/check_soft.py" "$OUT" --vocab-size "$VOCAB" --expect-sentences "$EXPECT_TOTAL"
sha256sum "$OUT" > "$OUT.sha256"
cat "$OUT.sha256"
# A partial merge must not look like a finished run: same hashes, distinct
# marker. train.py accepts either file, but a later reader can tell them apart.
if [ "${PARTIAL_MERGE:-0}" = "1" ] || [ "$EXPECT_TOTAL" != "$EXPECT" ]; then
  rm -f "$OUT.DONE"
  {
    echo "partial: $(date -Is)"
    echo "sentences: $EXPECT_TOTAL of $EXPECT"
    echo "shards: ${#SHARDS[@]}"
    echo "incomplete_shards: $INCOMPLETE"
  } > "$OUT.PARTIAL"
  echo "=== partial teacher run done (marker $OUT.PARTIAL, no .DONE)"
else
  rm -f "$OUT.PARTIAL"
  touch "$OUT.DONE"
  echo "=== teacher run done $(date -Is)"
fi

