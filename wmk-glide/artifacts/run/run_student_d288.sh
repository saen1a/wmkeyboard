#!/usr/bin/env bash
set -euo pipefail

cd /root/wmlm-de
export LD_LIBRARY_PATH=/opt/rocm-7.2.1/lib
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export PYTHONUNBUFFERED=1

exec >>out/student_d288.log 2>&1
echo "=== d288 start $(date -Is) ==="

if [ ! -f out/student_d288.TRAINED ]; then
  /opt/wmlm-venv/bin/python tools/wmlm/train.py out/de_lm_full out/de_run_d288 \
    steps=30000 batch=256 d=288 layers=6 heads=4 ff=896 ctx=40 \
    distill=out/de_soft_150k.npz distill_alpha=0.5 distill_share=0.5
  touch out/student_d288.TRAINED
fi

/opt/wmlm-venv/bin/python tools/wmlm/export.py \
  out/de_run_d288/best.pt out/de_lm_full/vocab.txt out/de_context_d288.wmlm \
  --langs=de --name=German
./bin/lm_probe out/de_context_d288.wmlm "ich will nach" hause berlin > out/lm_probe_d288.txt
touch out/student_d288.DONE
echo "=== d288 done $(date -Is) ==="
