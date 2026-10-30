#!/usr/bin/env bash
# Remote driver: 3-model teacher A/B on the fixed sentence set.
set -euo pipefail
set -a
. /data/env.sh
set +a
cd /root/wmk
echo "=== ab start $(date -Is)"
"$VLLM_PY" wmk-glide/cloud/scaleway/benchmark_prompt_logprobs.py \
  --data wmk-glide/artifacts/out/de_lm_2m \
  --models /data/models/Qwen3.8-27B-FP8,Qwen/Qwen3.5-9B-Base,Qwen/Qwen3.5-4B-Base \
  --sentences-file wmk-glide/artifacts/out/ab_sentences.tsv \
  --per-class 100 --batch 16 --out /data/out/ab_3way.json
echo "=== ab done $(date -Is)"
