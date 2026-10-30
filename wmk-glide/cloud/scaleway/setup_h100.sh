#!/usr/bin/env bash
# Prepare one Scaleway H100-1-80G (Ubuntu Noble GPU OS 13, fr-par-2) for the
# German teacher run. Idempotent; re-running only fixes what is missing.
#
#   bash setup_h100.sh --check     # inspect only: GPU, CUDA, disks, Python
#   bash setup_h100.sh             # + venv, vLLM, model download, /data/env.sh
#
# What it does NOT do: install NVIDIA drivers (they ship with the GPU OS),
# touch the block/scratch filesystems, start a server, or write any secret
# to disk outside HF's own cache.
set -euo pipefail

MODEL=${MODEL:-Qwen/Qwen3.8-27B-FP8}
DATA=${DATA:-/data}
SCRATCH=${SCRATCH:-/scratch}
VENV=${VENV:-/opt/vllm-venv}
HF_HOME=${HF_HOME:-$DATA/hf-cache}
MODELS_DIR=${MODELS_DIR:-$DATA/models}
LOG=${LOG:-$DATA/setup_h100.log}
ALLOW_CUDA13=${ALLOW_CUDA13:-0}
CHECK_ONLY=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$DATA"
exec > >(tee -a "$LOG") 2>&1
echo "=== setup_h100 $(date -Is) model=$MODEL data=$DATA"

fail() { echo "FAIL: $*" >&2; exit 1; }
note() { echo "--- $*"; }

# ---------------------------------------------------------------- hardware
command -v nvidia-smi >/dev/null || fail "nvidia-smi missing: is this the GPU OS image?"
note "GPU"
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader
nvidia-smi -L

if command -v nvcc >/dev/null; then
  NVCC=$($(command -v nvcc) --version | tr '\n' ' ')
  note "CUDA: $NVCC"
  CUDA_MAJOR=$(echo "$NVCC" | sed -n 's/.*release \([0-9][0-9]*\)\..*/\1/p' | head -1)
  if [ "${CUDA_MAJOR:-0}" -ge 13 ] && [ "$ALLOW_CUDA13" != "1" ]; then
    cat <<'EOF'
WARN: the image ships CUDA >= 13. The vLLM pip wheel brings its own CUDA
      runtime (12.x), which normally co-exists with a newer driver - but if
      the wheel cannot load its libs, use the container instead. Bind the API
      to loopback only - on a public-IP instance `-p 8000:8000` publishes an
      unauthenticated OpenAI endpoint to the internet:
        docker run --gpus all -p 127.0.0.1:8000:8000 \
          -e VLLM_API_KEY="$(openssl rand -hex 16)" \
          -v /data/hf-cache:/root/.cache/huggingface \
          vllm/vllm-openai:v0.32.0 --model Qwen/Qwen3.8-27B-FP8
      (pin the image tag/digest you actually tested; `latest` drifts)
      Re-run with ALLOW_CUDA13=1 to continue with pip.
EOF
  fi
else
  note "nvcc not on PATH (fine: vLLM wheels bundle their CUDA runtime)"
fi

note "memory / disk"
free -g | head -2
df -h "$DATA" "$SCRATCH" 2>/dev/null || true
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | head -20
if ! mountpoint -q "$DATA"; then
  if [ "$CHECK_ONLY" = "1" ] || [ "${ALLOW_ROOT_DISK:-0}" = "1" ]; then
    echo "WARN: $DATA is not a separate mountpoint; a real run would write the model"
    echo "      and all outputs to the ephemeral root disk. Attach and mount the"
    echo "      block volume first (ALLOW_ROOT_DISK=1 overrides this)."
  else
    fail "$DATA is not a mountpoint: attach and mount the block volume first, or set ALLOW_ROOT_DISK=1 to run on the root disk"
  fi
fi
[ -d "$SCRATCH" ] || echo "WARN: $SCRATCH missing - scratch volume not mounted; keep the HF cache on $DATA then"

note "python"
python3 --version
python3 -c 'import shutil,sys; print("disk temp:", shutil.disk_usage("/tmp").free // (1<<30), "GiB")'

if [ "$CHECK_ONLY" = "1" ]; then
  echo "=== check only: no venv, no model, nothing written besides $LOG"
  exit 0
fi

# ---------------------------------------------------------------- venv
# VENV is environment-overridable and gets deleted with -rf; resolve it and
# require a plain path below /opt or /data (a raw `case /data/*` would also
# accept /data/../etc).
VENV_REAL=$(realpath -m -- "$VENV" 2>/dev/null || echo "")
case "$VENV_REAL" in
  /opt/*|/data/*) : ;;
  *) fail "VENV=$VENV resolves to '${VENV_REAL:-?}', outside /opt or /data; refusing to manage it" ;;
esac
if [ -L "$VENV" ]; then
  fail "VENV=$VENV is a symlink; refusing to delete through it"
fi
if [ -d "$VENV" ] && mountpoint -q "$VENV"; then
  fail "VENV=$VENV is a mountpoint"
fi
VENV=$VENV_REAL
if [ ! -x "$VENV/bin/python" ] || [ "$FORCE" = "1" ]; then
  note "creating venv $VENV"
  rm -rf "$VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -U pip wheel
  note "installing ${VLLM_SPEC:-vllm} + hf_transfer + transformers (this takes a few minutes)"
  # shellcheck disable=SC2086  # VLLM_SPEC may be a pinned requirement
  "$VENV/bin/pip" install ${VLLM_SPEC:-vllm} hf_transfer ${TRANSFORMERS_SPEC:-transformers}
else
  note "venv exists: $("$VENV/bin/python" -V), vllm $("$VENV/bin/pip" show vllm 2>/dev/null | awk '/^Version/{print $2}')"
fi
"$VENV/bin/python" - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0), torch.cuda.get_device_properties(0).total_memory // (1 << 30), "GiB")
PY

# ---------------------------------------------------------------- rust
# prep_train_eval.sh builds the measurement harness from native/wm-engine;
# the GPU OS image ships no Rust toolchain (cost one manual step on the
# L40S smoke run).
if command -v cargo >/dev/null; then
  note "rust: $(cargo --version)"
else
  note "installing rustup (needed for the wm-engine harness)"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
  cargo --version
fi

# ---------------------------------------------------------------- model
export HF_HOME
export HF_HUB_ENABLE_HF_TRANSFER=1
mkdir -p "$MODELS_DIR" "$HF_HOME"
TARGET="$MODELS_DIR/$(basename "$MODEL")"
if [ -f "$TARGET/config.json" ] && [ "$FORCE" != "1" ]; then
  note "model already at $TARGET"
else
  note "downloading $MODEL -> $TARGET"
  if [ -n "${HF_TOKEN:-}" ]; then
    # Token stays in this process only; never echoed, never written here.
    "$VENV/bin/python" - "$MODEL" "$TARGET" <<'PY'
import os, sys
from huggingface_hub import snapshot_download
model, target = sys.argv[1], sys.argv[2]
snapshot_download(repo_id=model, local_dir=target, token=os.environ.get("HF_TOKEN"),
                  max_workers=8)
print("downloaded", model, "->", target)
PY
  else
    "$VENV/bin/python" - "$MODEL" "$TARGET" <<'PY'
import sys
from huggingface_hub import snapshot_download
model, target = sys.argv[1], sys.argv[2]
snapshot_download(repo_id=model, local_dir=target, max_workers=8)
print("downloaded", model, "->", target)
PY
  fi
fi
du -sh "$TARGET" || true

# ---------------------------------------------------------------- env.sh
cat > "$DATA/env.sh" <<EOF
# Generated by setup_h100.sh on $(date -Is). No secrets.
export HF_HOME=$HF_HOME
export HF_HUB_ENABLE_HF_TRANSFER=1
export MODELS_DIR=$MODELS_DIR
export TEACHER_MODEL=$TARGET
export TEACHER_MODEL_ID=$MODEL
export VLLM_PY=$VENV/bin/python
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1
# The GPU OS image ships no nvcc, so FlashInfer's JIT sampler cannot build its
# kernel. Sampling is irrelevant here (max_tokens=1, prompt_logprobs only).
export VLLM_USE_FLASHINFER_SAMPLER=0
export PATH=$HOME/.cargo/bin:$PATH
EOF
"$VENV/bin/pip" freeze > "$DATA/pip-freeze.txt"
note "wrote $DATA/env.sh and $DATA/pip-freeze.txt"
echo "=== setup_h100 done $(date -Is)"
