#!/usr/bin/env bash
# Local 1.2M teacher pass: 1M base + 200k chat, 240 x 5k chunks.
# Interruptible: valid chunks are skipped, a killed chunk is removed and
# rerun, and merge_soft.py writes the final npz atomically.
set -euo pipefail
export PREFIX=${PREFIX:-soft_1m2}
export CHUNKS=${CHUNKS:-240}
export PER=${PER:-5000}
export TOTAL=${TOTAL:-1200000}
export TOPIC=${TOPIC:-de_lm_1m2}
export FINAL=${FINAL:-out/de_soft_1m2.npz}
export LOG=${LOG:-out/teacher_1m2.log}
exec "$(dirname "$0")/run_teacher_chunks.sh"
