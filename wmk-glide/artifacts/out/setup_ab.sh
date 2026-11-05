#!/usr/bin/env bash
# Remote driver: setup only. Kept as a file - inline ssh quoting mangles
# $VAR and backslash escapes on Windows.
set -euo pipefail
export ALLOW_ROOT_DISK=1
cd /root/wmk
echo "=== setup start $(date -Is)"
bash wmk-glide/cloud/scaleway/setup_h100.sh
echo "=== setup done $(date -Is)"
