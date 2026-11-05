#!/usr/bin/env bash
# WSL Ubuntu 24.04 + ROCm 7.2.1 wrapper. Runs `bench_steps.py` or `train.py`.
#
# Usage:
#   bash run_rocm.sh MODE=bench|train data=<dir> [distill=<file>]
#                     [mask=<file>] [weight=<file>] [steps=N] [batch=N]
#                     [ctx=N] [d=N layers=N heads=N ff=N] [out=<dir>]
#
# Env (override before calling):
#   PY       Python interpreter (default /opt/wmlm-venv/bin/python)
#   ROCM_LIB ROCm lib path    (default /opt/rocm-7.2.1/lib)

set -euo pipefail

# Accept the documented `k=v` arguments, then fall back to the environment.
# The header and README invoke this as `run_rocm.sh MODE=train data=...`; an
# argument-free `"${MODE:-bench}"` default would silently run a benchmark
# against an empty data dir for anyone asking for a training run.
for arg in "$@"; do
    case "$arg" in
        MODE=*)   MODE="${arg#*=}" ;;
        data=*)   data="${arg#*=}" ;;
        distill=*) distill="${arg#*=}" ;;
        mask=*)   mask="${arg#*=}" ;;
        weight=*) weight="${arg#*=}" ;;
        steps=*)  steps="${arg#*=}" ;;
        batch=*)  batch="${arg#*=}" ;;
        ctx=*)    ctx="${arg#*=}" ;;
        d=*)      d="${arg#*=}" ;;
        layers=*) layers="${arg#*=}" ;;
        heads=*)  heads="${arg#*=}" ;;
        ff=*)     ff="${arg#*=}" ;;
        out=*)    out="${arg#*=}" ;;
        *) echo "run_rocm.sh: unknown argument '$arg'" >&2; exit 2 ;;
    esac
done

MODE="${MODE:-bench}"
PY="${PY:-/opt/wmlm-venv/bin/python}"
ROCM_LIB="${ROCM_LIB:-/opt/rocm-7.2.1/lib}"
DATA="${data:-}"
DISTILL="${distill:-}"
MASK="${mask:-}"
WEIGHT="${weight:-}"
STEPS="${steps:-200}"
BATCH="${batch:-256}"
CTX="${ctx:-40}"
D_="${d:-256}"
LAYERS="${layers:-6}"
HEADS="${heads:-4}"
FF="${ff:-768}"
OUT="${out:-/tmp/run_rocm}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
LOCAL="$REPO/wmk-glide/cloud/local"
TRAIN="$REPO/tools/wmlm/train.py"

export HSA_ENABLE_DXG_DETECTION=1
export LD_LIBRARY_PATH="${ROCM_LIB}:${LD_LIBRARY_PATH:-}"
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export PYTHONUNBUFFERED=1

precondition() {
    "$PY" - <<'PYEOF'
import sys, torch
ok = torch.cuda.is_available()
name = torch.cuda.get_device_name(0) if ok else "<no cuda>"
print(f"precondition ok={ok} device={name} torch={torch.__version__}", flush=True)
sys.exit(0 if ok else 1)
PYEOF
}

# Fail loudly instead of benchmarking an empty directory.
if [ -z "$DATA" ]; then
    echo "run_rocm.sh: data=<dir> is required (see the usage header)" >&2
    exit 2
fi
if [ ! -d "$DATA" ]; then
    echo "run_rocm.sh: data dir does not exist: $DATA" >&2
    exit 2
fi

case "$MODE" in
    bench)
        precondition
        CMD=(
            "$PY" "$LOCAL/bench_steps.py"
            "--data"    "$DATA"
            "--steps"   "$STEPS"
            "--batch"   "$BATCH"
            "--ctx"     "$CTX"
            "--d"       "$D_"
            "--layers"  "$LAYERS"
            "--heads"   "$HEADS"
            "--ff"      "$FF"
            "--device"  "auto"
        )
        [ -n "$DISTILL" ] && CMD+=("--distill" "$DISTILL")
        [ -n "$MASK"     ] && CMD+=("--mask"     "$MASK")
        [ -n "$WEIGHT"   ] && CMD+=("--weight"   "$WEIGHT")
        [ -n "${JSON:-}" ] && CMD+=("--json"     "${JSON}")
        echo ">>> bench_steps.py"
        "${CMD[@]}"
        ;;
    train)
        precondition
        mkdir -p "$OUT"
        echo ">>> train.py (tee to $OUT/run.log)"
        o=("steps=$STEPS" "batch=$BATCH" "ctx=$CTX" "d=$D_" "layers=$LAYERS" "heads=$HEADS" "ff=$FF")
        [ -n "$DISTILL" ] && o+=("distill=$DISTILL")
        [ -n "$MASK"     ] && o+=("distill_mask=$MASK")
        [ -n "$WEIGHT"   ] && o+=("distill_weight=$WEIGHT")
        "$PY" "$TRAIN" "$DATA" "$OUT" "${o[@]}" 2>&1 | tee "$OUT/run.log"
        ;;
    *)
        echo "MODE must be bench|train (got: $MODE)" >&2
        exit 2
        ;;
esac
