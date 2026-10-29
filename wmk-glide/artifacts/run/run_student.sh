#!/usr/bin/env bash
set -euo pipefail

cd /root/wmlm-de
export LD_LIBRARY_PATH=/opt/rocm-7.2.1/lib
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export PYTHONUNBUFFERED=1

exec >>out/student.log 2>&1
echo "=== student start $(date -Is) ==="

if [ ! -f out/student.TRAINED ]; then
  /opt/wmlm-venv/bin/python tools/wmlm/train.py out/de_lm_full out/de_run \
    steps=30000 batch=256 d=256 layers=6 heads=4 ff=768 ctx=40 \
    distill=out/de_soft_150k.npz distill_alpha=0.5 distill_share=0.5
  touch out/student.TRAINED
fi

/opt/wmlm-venv/bin/python tools/wmlm/export.py \
  out/de_run/best.pt out/de_lm_full/vocab.txt out/de_context.wmlm \
  --langs=de --name=German
./bin/lm_probe out/de_context.wmlm "ich will nach" hause berlin > out/lm_probe.txt
touch out/student.DONE
echo "=== student done $(date -Is) ==="
