#!/usr/bin/env bash
# Student v2: 90k, new pieces, KD piece soft-weight, EMA.
# usage: run_student_v2.sh   (env: STEPS=90000 TOPK=24 EMA=0.999)
# Idempotent/resumable. One trainer at a time (flock). Writes flags.json,
# run.log and DONE next to the checkpoint.
set -uo pipefail
REPO=/mnt/g/C0ding/git/wmkeyboard-wmlm
ART=$REPO/wmk-glide/artifacts/out
PY=/opt/wmlm-venv/bin/python
DATA=$ART/de_lm_2m
OUT=$ART/runs/G6P/90k_v2
SOFT=$ART/de_soft_2m.npz
ALIGN=$ART/de_soft_2m.masks.align.npz
WEIGHT=$ART/de_soft_2m.masks.kdweight.npz
STEPS=${STEPS:-90000}
TOPK=${TOPK:-24}
EMA=${EMA:-0.999}

mkdir -p "$OUT"

if [ -f "$OUT/DONE" ]; then
    DONE_STEPS=$(sed -n 's/.*steps=\([0-9][0-9]*\).*/\1/p' "$OUT/DONE" | head -1)
    if [ -n "$DONE_STEPS" ] && [ "$DONE_STEPS" != "$STEPS" ]; then
        echo "[student_v2] DONE exists for steps=$DONE_STEPS, requested $STEPS -> refusing" >&2
        exit 7
    fi
    echo "[student_v2] DONE -> skip"; exit 0
fi

if [ "${PREFLIGHT_ONLY:-0}" != "1" ] && [ ! -f "$ART/runs/G6P/90k/DONE" ]; then
    echo "current runs/G6P/90k is not DONE; refusing to start (wait for the current 90k)" >&2
    exit 8
fi
if [ ! -f "$SOFT" ]; then echo "missing soft $SOFT" >&2; exit 2; fi
if [ -f "$SOFT.PARTIAL" ]; then
    echo "WARN soft is a PARTIAL teacher merge ($(tr '\n' ' ' < "$SOFT.PARTIAL"))" >&2
fi
for f in "$DATA/train.npz" "$DATA/heldout.npz" "$DATA/vocab.txt" "$ALIGN" "$WEIGHT"; do
    if [ ! -f "$f" ]; then echo "missing $f (build the v2 artifacts first)" >&2; exit 2; fi
done
if [ ! -f "$REPO/tools/wmlm/train_v2.py" ]; then echo "missing train_v2.py" >&2; exit 2; fi

# Shape and invariant preflight, CPU only.
"$PY" - "$DATA" "$SOFT" "$ALIGN" "$WEIGHT" <<'PY'
import os, sys, numpy as np
data, soft, align, weight = sys.argv[1:5]
v = [l.rstrip("\n") for l in open(os.path.join(data, "vocab.txt"), encoding="utf-8")]
words = [t for t in v[16:] if not t.startswith("\u2581") and not t.startswith("##")]
assert len(v) == 24576, len(v)
assert len(words) == 22512, len(words)
z = np.load(soft)
rows = int(z["ids"].shape[0])
a = np.load(align); w = np.load(weight)
assert a["pos"].shape == (rows,), a["pos"].shape
assert w["weight"].shape == (rows,), w["weight"].shape
tr = np.load(os.path.join(data, "train.npz")); he = np.load(os.path.join(data, "heldout.npz"))
assert len(he["starts"]) - 1 == 20000, len(he["starts"]) - 1
assert len(tr["starts"]) - 1 == 1980000, len(tr["starts"]) - 1
print("preflight rows", rows, "train", len(tr["starts"])-1, "heldout", len(he["starts"])-1,
      "vocab", len(v), "words", len(words), "piece_weight_mean", float(w["weight"].mean()))
PY
rc=$?; [ "$rc" -ne 0 ] && { echo "preflight failed rc=$rc" >&2; exit 2; }
if [ "${PREFLIGHT_ONLY:-0}" = "1" ]; then
    echo "[student_v2] preflight ok"; exit 0
fi

# One trainer at a time on this host.
LOCK=$ART/.trainer.lock
if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK"
    if ! flock -n 9; then
        echo "another trainer holds $LOCK (wait for current 90k DONE)" >&2
        exit 6
    fi
fi

RESUMED=0; RESUME=()
if [ -f "$OUT/last.pt" ]; then RESUMED=1; RESUME=("resume=$OUT/last.pt"); fi
export HSA_ENABLE_DXG_DETECTION=1 LD_LIBRARY_PATH=/opt/rocm-7.2.1/lib \
       TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1 PYTHONUNBUFFERED=1

FLAGS=(
  "steps=$STEPS" "eval_every=500" "batch=256" "lr=1e-3"
  "d=256" "layers=6" "heads=4" "ff=768" "ctx=40" "seed=0" "drop_prefix=0.3"
  "distill=$SOFT" "distill_alpha=0.3" "distill_share=0.5"
  "distill_align=$ALIGN" "distill_weight=$WEIGHT" "distill_impl=gather"
  "distill_topk=$TOPK" "ema_decay=$EMA"
)
"$PY" - "$OUT/flags.json" "${FLAGS[@]}" "${RESUME[@]}" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(sys.argv[2:], fh, indent=2); fh.write("\n")
PY

echo "[student_v2] start steps=$STEPS topk=$TOPK ema=$EMA resumed=$RESUMED" | tee -a "$OUT/run.log"
TIMEOUT=$((STEPS + 7200))
timeout "${TIMEOUT}s" "$PY" "$REPO/tools/wmlm/train_v2.py" "$DATA" "$OUT" \
    "${FLAGS[@]}" "${RESUME[@]}" 2>&1 | tee -a "$OUT/run.log"
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ]; then echo "[student_v2] fail rc=$rc" >&2; exit "$rc"; fi
if ! grep -q '^device cuda' "$OUT/run.log"; then echo "no cuda" >&2; exit 5; fi
grep -qiE '\b(nan|inf)\b' "$OUT/run.log" && { echo "nan/inf" >&2; exit 3; }
if ! grep -q "eval step $STEPS " "$OUT/run.log"; then echo "no final eval" >&2; exit 4; fi
LOSS=$(grep -oE "eval step $STEPS heldout loss [0-9.]+" "$OUT/run.log" | tail -1 | awk '{print $NF}')
BEST=$(grep -E '^eval step [0-9]+ heldout loss [0-9.]+' "$OUT/run.log" | awk '{print $3" "$6}' | sort -k2,2g | head -1)
BEST_STEP=${BEST%% *}; BEST_LOSS=${BEST##* }
EMA_BEST=$(grep -E '^eval step [0-9]+ ema heldout loss [0-9.]+' "$OUT/run.log" | awk '{print $7}' | sort -g | head -1 || true)
SHA=$(sha256sum "$OUT/last.pt" | cut -d' ' -f1)
printf 'gate=G6P run=90k_v2 steps=%s resumed=%s heldout_loss=%s best_heldout_loss=%s best_step=%s ema_best_loss=%s sha256=%s flags=%s\n' \
    "$STEPS" "$RESUMED" "$LOSS" "$BEST_LOSS" "$BEST_STEP" "${EMA_BEST:-NA}" "$SHA" "${FLAGS[*]}" > "$OUT/DONE"
echo "[student_v2] DONE loss=$LOSS best=$BEST_LOSS@$BEST_STEP ema=${EMA_BEST:-NA}" | tee -a "$OUT/run.log"

