#!/usr/bin/env bash
# Prep -> student training -> export -> measurement, resumable.
#
#   bash prep_train_eval.sh out/de_soft_1m2.npz artifacts/out/de_lm_1m2 \
#        artifacts/out/de_run_1m2
#
# Env:
#   CORPUS      sentences.tsv for prep.py (default: artifacts/corpora/de_1m_200k_chat.tsv)
#   STEPS=30000 BATCH=256 D=256 LAYERS=6 HEADS=4 FF=768 CTX=40
#   ALPHA=0.5   distill weight          SHARE=0.5  share of teacher batches
#   SKIP_PREP=1 / REPREP=1 / SKIP_EVAL=1 / SKIP_TRAIN=1
#
# The student is the shipped d256/6/768 (10.9 MB). `prep.py` draws its own
# 20k held-out split from the mix; the *shipped* 20k heldout
# (artifacts/data/heldout.tsv) was excluded from the corpus, so the final
# glide/typing numbers stay comparable to the published model.
set -euo pipefail

SOFT=${1:?usage: prep_train_eval.sh <soft.npz> <data dir> <run dir>}
DATA_DIR=${2:?usage: prep_train_eval.sh <soft.npz> <data dir> <run dir>}
RUN_DIR=${3:-$(dirname "$SOFT")/de_run}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=${ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}
ART=${ART:-$ROOT/wmk-glide/artifacts}
PY=${PY:-/opt/vllm-venv/bin/python}
CORPUS_GIVEN=${CORPUS:+1}          # remember whether the caller pointed at one
CORPUS=${CORPUS:-$ART/corpora/de_1m_200k_chat.tsv}
SEED_WORDS=${SEED_WORDS:-$ART/data/de_aosp.txt.gz}
STEPS=${STEPS:-30000}
BATCH=${BATCH:-256}
D=${D:-256}
LAYERS=${LAYERS:-6}
HEADS=${HEADS:-4}
FF=${FF:-768}
CTX=${CTX:-40}
ALPHA=${ALPHA:-0.5}
SHARE=${SHARE:-0.5}
VOCAB=${VOCAB:-24576}
PIECES=${PIECES:-2048}
# Results belong on the block volume, not in the repo checkout: /data
# survives a reboot and is what `transfer.sh down` fetches. Locally (no
# /data) they stay under artifacts/.
RUN_ROOT=${RUN_ROOT:-$( [ -d /data ] && echo /data || echo "$ART" )}
MODEL_OUT=${MODEL_OUT:-$RUN_ROOT/models/de_context.wmlm}
EVAL=${EVAL:-$RUN_ROOT/out/eval_$(basename "${SOFT%.npz}")}
LOG=${LOG:-$(dirname "$RUN_DIR")/prep_train_eval.log}
mkdir -p "$(dirname "$RUN_DIR")" "$(dirname "$MODEL_OUT")" "$EVAL"
exec > >(tee -a "$LOG") 2>&1
echo "=== prep_train_eval $(date -Is) soft=$SOFT data=$DATA_DIR run=$RUN_DIR"
echo "=== outputs: model=$MODEL_OUT eval=$EVAL"

# ---------------------------------------------------------------- 1. prep
# prep_npz is only reusable if it was built from the same corpus and params:
# the soft-target `.npz` holds *indices* into train.npz, so a stale train.npz
# silently re-points every teacher row at a different sentence.
corpus_hash() { sha256sum "$CORPUS" | cut -d' ' -f1; }
prep_params() { echo "vocab=$VOCAB pieces=$PIECES ctx=$CTX heldout=20000"; }
prep_matches() {
  [ -f "$DATA_DIR/train.npz" ] && [ -f "$DATA_DIR/prep.json" ] || return 1
  [ "$(corpus_hash)" = "$(sed -n 's/^corpus=//p' "$DATA_DIR/prep.json")" ] || return 1
  [ "$(prep_params)" = "$(sed -n 's/^params=//p' "$DATA_DIR/prep.json")" ] || return 1
}

# Decide whether prep has to run. A pre-prepped data dir that was uploaded
# from the laptop has no prep.json, so an absent manifest must NOT trigger a
# rebuild from the hardcoded 1.2M default - that would clobber the 2M
# train.npz that the soft targets index into.
prep_needed=0
if [ "${SKIP_PREP:-0}" = "1" ]; then
  echo "=== prep skipped (SKIP_PREP=1)"
elif [ "${REPREP:-0}" = "1" ]; then
  prep_needed=1
  echo "=== prep forced (REPREP=1)"
elif [ ! -f "$DATA_DIR/train.npz" ]; then
  if [ "${CORPUS_GIVEN:-0}" != "1" ]; then
    echo "FAIL: $DATA_DIR/train.npz missing and no CORPUS= given" >&2
    echo "      pass CORPUS=<corpus.tsv> or upload a prepared out/de_lm_*" >&2
    exit 1
  fi
  prep_needed=1
elif prep_matches; then
  echo "=== prep skipped (train.npz matches $DATA_DIR/prep.json)"
elif [ "${CORPUS_GIVEN:-0}" = "1" ]; then
  prep_needed=1
  echo "=== prep: corpus/params differ from $DATA_DIR/prep.json"
else
  echo "=== WARN: $DATA_DIR/train.npz has no matching prep.json; reusing it as-is"
  echo "          (REPREP=1 to rebuild, CORPUS=<tsv> to point at a corpus)"
fi

if [ "$prep_needed" = "1" ]; then
  SEED_TXT=$SEED_WORDS
  CLEANUP=""
  if [ "${SEED_WORDS##*.}" = "gz" ]; then
    CLEANUP=$(mktemp -d)
    trap 'rm -rf "$CLEANUP"' EXIT
    SEED_TXT=$CLEANUP/seed_words.txt
    zcat "$SEED_WORDS" > "$SEED_TXT"
  fi
  echo "=== prep $(date -Is) corpus=$CORPUS"
  mkdir -p "$DATA_DIR"
  "$PY" "$ROOT/tools/wmlm/prep.py" "$CORPUS" "$DATA_DIR" \
    vocab="$VOCAB" pieces="$PIECES" ctx="$CTX" seed_words="$SEED_TXT" heldout=20000
  {
    echo "corpus=$(corpus_hash)"
    echo "corpus_path=$CORPUS"
    echo "params=$(prep_params)"
    echo "prepped_at=$(date -Is)"
  } > "$DATA_DIR/prep.json"
fi

# ---------------------------------------------------------------- 2. train
if [ "${SKIP_TRAIN:-0}" != "1" ]; then
  mkdir -p "$RUN_DIR"
  RESUME=()
  if [ -f "$RUN_DIR/last.pt" ]; then
    RESUME=(resume="$RUN_DIR/last.pt")
    echo "=== resume from $RUN_DIR/last.pt"
  fi
  echo "=== train $(date -Is) steps=$STEPS"
  TRAIN_TO=()
  if [ "${TRAIN_TIMEOUT_H:-3}" != "0" ] && command -v timeout >/dev/null; then
    TRAIN_TO=(timeout --signal=INT --kill-after=120 "$(awk -v h="${TRAIN_TIMEOUT_H:-3}" 'BEGIN{printf "%d", h*3600}')")
  fi
  "${TRAIN_TO[@]}" "$PY" "$ROOT/tools/wmlm/train.py" "$DATA_DIR" "$RUN_DIR" \
    steps="$STEPS" batch="$BATCH" d="$D" layers="$LAYERS" heads="$HEADS" ff="$FF" ctx="$CTX" \
    distill="$SOFT" distill_alpha="$ALPHA" distill_share="$SHARE" "${RESUME[@]}"
fi

# ---------------------------------------------------------------- 3. export
if [ "${SKIP_EXPORT:-0}" = "1" ]; then
  echo "=== export skipped (SKIP_EXPORT=1)"
elif [ "${SKIP_TRAIN:-0}" = "1" ] && [ ! -f "$RUN_DIR/best.pt" ]; then
  # Prep-only run: nothing to export, and eval cannot run without a model.
  echo "=== export skipped (SKIP_TRAIN=1 and no $RUN_DIR/best.pt; prep only)"
  echo "=== prep-only run finished $(date -Is)"
  exit 0
else
  echo "=== export $(date -Is)"
  "$PY" "$ROOT/tools/wmlm/export.py" "$RUN_DIR/best.pt" "$DATA_DIR/vocab.txt" "$MODEL_OUT" \
    --langs=de --name=German
  sha256sum "$MODEL_OUT" | tee "$MODEL_OUT.sha256"
  ls -l "$MODEL_OUT"
fi

if [ "${SKIP_EVAL:-0}" = "1" ]; then
  echo "=== eval skipped"
  exit 0
fi
[ -f "$MODEL_OUT" ] || { echo "FAIL: $MODEL_OUT missing but eval was requested (unset SKIP_TRAIN/SKIP_EXPORT or export first)" >&2; exit 1; }

# ---------------------------------------------------------------- 4. measure
echo "=== build harness $(date -Is)"
# The glide harness lives in wmk-glide/experiments; the engine only builds
# examples from its own examples/ directory (see HANDOFF.md). Always copy:
# `transfer.sh up` rsyncs the engine without --delete, so a stale example
# would otherwise survive an edit to the source.
GLIDE_SRC="$ROOT/wmk-glide/experiments/glide_lm_blend_eval.rs"
GLIDE_DST="$ROOT/native/wm-engine/examples/glide_lm_blend_eval.rs"
if [ -f "$GLIDE_SRC" ]; then
  cp -f "$GLIDE_SRC" "$GLIDE_DST"
  echo "copied $GLIDE_SRC -> $GLIDE_DST"
fi
[ -f "$GLIDE_DST" ] || { echo "FAIL: $GLIDE_DST missing (run transfer.sh up)" >&2; exit 1; }
command -v cargo >/dev/null || {
  echo "FAIL: cargo missing; run setup_h100.sh (installs rustup) or set PATH=/root/.cargo/bin:\$PATH" >&2
  exit 1
}
cargo build --release --example typing_eval --example glide_lm_blend_eval \
  --manifest-path "$ROOT/native/wm-engine/Cargo.toml"
BIN="$ROOT/native/wm-engine/target/release/examples"
[ -x "$BIN/glide_lm_blend_eval" ] || { echo "FAIL: $BIN/glide_lm_blend_eval not built" >&2; exit 1; }

echo "=== typing_eval $(date -Is)"
CASES=${CASES:-500} SCATTER=${SCATTER:-fast} MODES=${MODES:-base,lm} SAVINGS=0 \
  LMBLEND=0.5 LMBCAP=5.0 \
  "$BIN/typing_eval" "$ART/data/de_150k.txt" "$ART/data/heldout.tsv" "$MODEL_OUT" \
  | tee "$EVAL/typing.txt"

echo "=== glide 150k $(date -Is)"
RESULTS=${RESULTS:-8} COLS=${COLS:-11} THREADS=${THREADS:-8} FREQ=0.5 GAP=2.0 WEIGHT=0.5 CAP=5 \
  "$BIN/glide_lm_blend_eval" "$ART/data/de_swipes.jsonl" "$ART/data/german.json" \
  "$ART/data/de_150k.txt" "$MODEL_OUT" | tee "$EVAL/glide_150k.txt"

echo "=== glide 150k+compounds $(date -Is)"
RESULTS=${RESULTS:-8} COLS=${COLS:-11} THREADS=${THREADS:-8} FREQ=0.5 GAP=2.0 WEIGHT=0.5 CAP=5 \
  "$BIN/glide_lm_blend_eval" "$ART/data/de_swipes.jsonl" "$ART/data/german.json" \
  "$ART/data/de_150k_comp3.txt" "$MODEL_OUT" | tee "$EVAL/glide_comp3.txt"

echo "=== prep_train_eval done $(date -Is); results in $EVAL"
