#!/usr/bin/env bash
# usage: run_gate.sh <gate> <name> <data_dir> <steps> [train.py flags...]
# Idempotent + resumable. Writes run.log, flags.json, DONE, and one ledger line
# per event. One trainer at a time (flock), GPU must really be cuda, and DONE
# records both the final eval and the best checkpoint the exporter will use.
set -uo pipefail
REPO=/mnt/g/C0ding/git/wmkeyboard-wmlm
ART=$REPO/wmk-glide/artifacts/out
MODELS=$REPO/wmk-glide/artifacts/models
PY=/opt/wmlm-venv/bin/python
LEDGER=$REPO/wmk-glide/plans/gate-log.md
GATE=$1; NAME=$2; DATA=$3; STEPS=$4; shift 4
OUT=$ART/runs/$GATE/$NAME
mkdir -p "$OUT"

if [ -f "$OUT/DONE" ]; then
    DONE_STEPS=$(sed -n 's/.*steps=\([0-9][0-9]*\).*/\1/p' "$OUT/DONE" | head -1)
    if [ -n "$DONE_STEPS" ] && [ "$DONE_STEPS" != "$STEPS" ]; then
        echo "[$GATE/$NAME] DONE exists for steps=$DONE_STEPS, requested $STEPS -> refusing to overwrite" >&2
        echo "## $(date -Is) fail gate=$GATE run=$NAME reason=done_steps_mismatch done=$DONE_STEPS requested=$STEPS" >> "$LEDGER"
        exit 7
    fi
    echo "[$GATE/$NAME] DONE -> skip"; exit 0
fi

# Warn, do not fail: the 2M teacher file is a documented PARTIAL merge.
for a in "$@"; do
    case "$a" in
        distill=*)
            D=${a#distill=}
            if [ -f "$D.PARTIAL" ]; then
                echo "WARN distill=$D is a PARTIAL teacher merge ($(tr '\n' ' ' < "$D.PARTIAL"))" >&2
            fi
            ;;
    esac
done

# One trainer at a time on this host.
LOCK=$ART/.trainer.lock
if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK"
    if ! flock -n 9; then
        echo "## $(date -Is) fail gate=$GATE run=$NAME reason=trainer_lock_busy" >> "$LEDGER"
        echo "another trainer holds $LOCK" >&2
        exit 6
    fi
fi

RESUMED=0; RESUME=()
if [ -f "$OUT/last.pt" ]; then RESUMED=1; RESUME=("resume=$OUT/last.pt"); fi
export HSA_ENABLE_DXG_DETECTION=1 LD_LIBRARY_PATH=/opt/rocm-7.2.1/lib \
       TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1 PYTHONUNBUFFERED=1
echo "## $(date -Is) start gate=$GATE run=$NAME steps=$STEPS resumed=$RESUMED $*" >> "$LEDGER"

# Exact flag set next to the checkpoint (plan §3), including the wrapper's own.
"$PY" - "$OUT/flags.json" "steps=$STEPS" "eval_every=500" "${RESUME[@]}" "$@" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(sys.argv[2:], fh, indent=2)
    fh.write("\n")
PY

TIMEOUT=$((STEPS / 1 + 7200))   # >=1 step/s budget plus 2 h slack
timeout "${TIMEOUT}s" "$PY" "$REPO/tools/wmlm/train.py" "$DATA" "$OUT" \
    "steps=$STEPS" "eval_every=500" "${RESUME[@]}" "$@" 2>&1 | tee -a "$OUT/run.log"
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ]; then
    echo "## $(date -Is) fail gate=$GATE run=$NAME rc=$rc" >> "$LEDGER"; exit "$rc"
fi
if ! grep -q '^device cuda' "$OUT/run.log"; then
    echo "## $(date -Is) fail gate=$GATE run=$NAME reason=no_cuda" >> "$LEDGER"; exit 5
fi
grep -qiE '\b(nan|inf)\b' "$OUT/run.log" && {
    echo "## $(date -Is) fail gate=$GATE run=$NAME reason=nan" >> "$LEDGER"; exit 3; }
if ! grep -q "eval step $STEPS " "$OUT/run.log"; then
    echo "## $(date -Is) fail gate=$GATE run=$NAME reason=no_final_eval" >> "$LEDGER"; exit 4
fi
LOSS=$(grep -oE "eval step $STEPS heldout loss [0-9.]+" "$OUT/run.log" | tail -1 | awk '{print $NF}')
BEST=$(grep -E '^eval step [0-9]+ heldout loss [0-9.]+' "$OUT/run.log" | awk '{print $3" "$6}' | sort -k2,2g | head -1)
BEST_STEP=${BEST%% *}
BEST_LOSS=${BEST##* }
SHA=$(sha256sum "$OUT/last.pt" | cut -d' ' -f1)
printf 'gate=%s run=%s steps=%s resumed=%s heldout_loss=%s best_heldout_loss=%s best_step=%s sha256=%s flags=%s\n' \
    "$GATE" "$NAME" "$STEPS" "$RESUMED" "$LOSS" "$BEST_LOSS" "$BEST_STEP" "$SHA" "$*" > "$OUT/DONE"
echo "## $(date -Is) done gate=$GATE run=$NAME loss=$LOSS best=$BEST_LOSS best_step=$BEST_STEP resumed=$RESUMED" >> "$LEDGER"
