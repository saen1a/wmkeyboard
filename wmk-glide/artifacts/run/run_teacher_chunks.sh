#!/usr/bin/env bash
# Overnight German teacher pass: 30 x 5k chunks, validated and merged.
# Idempotent: a valid existing chunk is skipped; an invalid one is removed
# and rerun. A missing/failed chunk only costs that chunk.
set -euo pipefail

ROOT=${ROOT:-/root/wmlm-de}
PY=${PY:-/opt/wmlm-venv/bin/python}
CHUNKS=${CHUNKS:-30}
PER=${PER:-5000}
TOTAL=${TOTAL:-150000}
TOPIC=${TOPIC:-de_lm_full}
TEACHER=${TEACHER:-Qwen/Qwen3.5-4B-Base}
BATCH=${BATCH:-16}
DTYPE=${DTYPE:-float16}
VOCAB=${VOCAB:-24576}
TOPK=${TOPK:-24}
CHUNK_MASS=${CHUNK_MASS:-0.85}
MIN_MASS=${MIN_MASS:-0.85}
LOG=${LOG:-out/teacher_150k.log}
FINAL=${FINAL:-out/de_soft_150k.npz}
PREFIX=${PREFIX:-soft_150k}

cd "$ROOT"
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-/opt/rocm-7.2.1/lib}
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export HF_HOME=${HF_HOME:-/root/hf-cache}

exec >>"$LOG" 2>&1
echo "=== start $(date -Is) ==="

# One teacher run at a time; a second invocation must not share the GPU.
exec 9>/tmp/wmlm-teacher.lock
flock -n 9 || { echo "another teacher run holds /tmp/wmlm-teacher.lock"; exit 1; }

files=()
for i in $(seq 0 $((CHUNKS - 1))); do
  f="out/${PREFIX}_$i.npz"
  files+=("$f")
  if [ -f "$f" ]; then
    if "$PY" tools/wmlm/check_soft.py "$f" --vocab-size "$VOCAB" \
        --expect-sentences "$PER" --min-mass-ratio "$CHUNK_MASS"; then
      echo "skip $f (valid)"
      continue
    else
      echo "invalid $f; removing and rerunning"
      rm -f "$f"
    fi
  fi

  echo "=== chunk $i $(date -Is) ==="
  "$PY" tools/wmlm/distill_multi.py "out/$TOPIC" "$f" \
    teacher="$TEACHER" sentences="$TOTAL" start=$((i * PER)) count="$PER" \
    topk="$TOPK" batch="$BATCH" device=cuda multi=1 dtype="$DTYPE"
  "$PY" tools/wmlm/check_soft.py "$f" --vocab-size "$VOCAB" \
    --expect-sentences "$PER" --min-mass-ratio "$CHUNK_MASS"
done

echo "=== merge $(date -Is) ==="
"$PY" tools/wmlm/merge_soft.py "$FINAL" "${files[@]}" \
  --vocab-size "$VOCAB" --expect-sentences "$TOTAL" --min-mass-ratio "$MIN_MASS"
"$PY" tools/wmlm/check_soft.py "$FINAL" --vocab-size "$VOCAB" \
  --expect-sentences "$TOTAL" --min-mass-ratio "$MIN_MASS"
if ! "$PY" tools/wmlm/check_soft.py "$FINAL" --vocab-size "$VOCAB" \
  --expect-sentences "$TOTAL" --min-mass-ratio 0.90; then
  echo "WARN: mass ratio below the 90% Phase-1 gate; model may still train"
fi
sha256sum "$FINAL" > "$FINAL.sha256"
touch out/teacher_150k.DONE
echo "=== done $(date -Is) ==="
