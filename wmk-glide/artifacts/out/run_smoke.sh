#!/usr/bin/env bash
# Remote driver for the L40S smoke test (regenerated on the box, not part of
# the repo). Kept as a file because inline ssh quoting mangles $VAR and quotes.
set -euo pipefail

set -a
. /data/env.sh
set +a
export VLLM_USE_FLASHINFER_SAMPLER=0
export PATH=/root/.cargo/bin:$PATH

export STEPS=2000
export SKIP_TRAIN=1
export SKIP_PREP=1
export CASES=100
export ROOT=/root/wmk
export ART=/root/wmk/wmk-glide/artifacts
export MODEL_OUT=/data/out/de_context_smoke.wmlm
export EVAL=/data/out/eval_smoke

cd /root/wmk
echo "=== driver start $(date -Is) steps=$STEPS"
bash wmk-glide/cloud/scaleway/prep_train_eval.sh \
  /data/out/de_soft_smoke.npz \
  /root/wmk/wmk-glide/artifacts/out/de_lm_2m \
  /data/out/de_run_smoke
echo "=== driver done $(date -Is)"
