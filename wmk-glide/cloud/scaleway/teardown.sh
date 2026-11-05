#!/usr/bin/env bash
# Collect results, verify them, and only then allow teardown.
#
#   bash teardown.sh <user@host>                              # down + verify
#   bash teardown.sh <user@host> --terminate <instance-id>     # + terminate
#
# Why a separate script: `transfer.sh down` is a plain rsync and can finish
# partially. Terminating the instance with `with-block=true` destroys the only
# copy of the soft targets, so the terminate must be gated on a hash match,
# not on "rsync exited 0".
#
# Verification covers EVERY file under <remote>/out plus the exported student
# (models/*.wmlm). Teacher checkpoints are re-downloadable and stay on the box,
# so they are the only thing exempt - and the marker is never written unless at
# least one artifact was actually compared.
set -euo pipefail

HOST=${1:?usage: teardown.sh <user@host> [--terminate <instance-id>]}
MODE=${2:-}
INSTANCE=${3:-}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=${ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}
ART=${ART:-$ROOT/wmk-glide/artifacts}
KEY=${SCW_SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}
REMOTE_ART=${REMOTE_ART:-/data}
MARKER="$ART/teardown-verified"

# A stale marker from an earlier run must never survive an aborted teardown.
rm -f "$MARKER"

# Same allowlist as transfer.sh: this value is interpolated into a remote
# shell string below.
case "$REMOTE_ART" in
  ""|*[!A-Za-z0-9._/-]*|*/../*|*/..|*//*) echo "refusing unsafe remote path: $REMOTE_ART" >&2; exit 2 ;;
  /*) : ;;
  *) echo "refusing relative remote path: $REMOTE_ART" >&2; exit 2 ;;
esac

# -n: ssh must not consume the loop's stdin (see the while-read below).
SSH="ssh -n -i $KEY -o StrictHostKeyChecking=${SSH_HOSTKEY:-accept-new} -o BatchMode=yes"

echo "=== teardown: collecting results from $HOST:$REMOTE_ART"
"$SCRIPT_DIR/transfer.sh" down "$HOST"

echo "=== teardown: verifying hashes"
REMOTE_LIST=$($SSH "$HOST" "cd $REMOTE_ART && find out models -maxdepth 3 -type f \
  \( -name '*.npz' -o -name '*.sha256' -o -name '*.wmlm' -o -name '*.json' -o -name '*.txt' \) \
  2>/dev/null | sort")
if [ -z "$REMOTE_LIST" ]; then
  echo "FAIL: nothing found under $REMOTE_ART/{out,models}; refusing to bless a teardown" >&2
  exit 1
fi

missing=0
checked=0
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  case "$rel" in
    # teacher checkpoints: deliberately not pulled (transfer.sh MODELS=0)
    models/*)
      case "$rel" in
        *.wmlm|*.wmlm.sha256) : ;;
        *) continue ;;
      esac
      ;;
  esac
  local_path="$ART/$rel"
  if [ ! -f "$local_path" ]; then
    echo "MISSING locally: $rel" >&2
    missing=$((missing + 1))
    continue
  fi
  remote_hash=$($SSH "$HOST" "sha256sum '$REMOTE_ART/$rel'" 2>/dev/null | cut -d' ' -f1)
  local_hash=$(sha256sum "$local_path" | cut -d' ' -f1)
  if [ -z "$remote_hash" ] || [ "$remote_hash" != "$local_hash" ]; then
    echo "HASH MISMATCH: $rel (${local_hash:-?} != ${remote_hash:-none})" >&2
    missing=$((missing + 1))
    continue
  fi
  checked=$((checked + 1))
done <<< "$REMOTE_LIST"

if [ "$missing" != "0" ] || [ "$checked" = "0" ]; then
  echo "FAIL: $missing unverified, $checked verified; instance NOT safe to terminate" >&2
  exit 1
fi

# Atomic marker: a partially written file must never look like a pass.
printf '%s\n' "verified $(date -Is) host=$HOST artifacts=$checked" > "$MARKER.tmp"
mv "$MARKER.tmp" "$MARKER"
echo "=== teardown: $checked artifacts verified ($MARKER)"

if [ "$MODE" != "--terminate" ]; then
  echo "=== teardown: not terminating. Run:"
  echo "    scw instance server terminate <id> zone=fr-par-2 with-ip=true with-block=true --wait"
  exit 0
fi
[ -n "$INSTANCE" ] || { echo "FAIL: --terminate needs an instance id" >&2; exit 2; }
command -v scw >/dev/null || {
  echo "FAIL: scw not on PATH; run 'scw instance server terminate $INSTANCE zone=fr-par-2 \
with-ip=true with-block=true --wait' yourself" >&2
  exit 2
}
[ -f "$MARKER" ] || { echo "FAIL: no verified marker; refusing to terminate" >&2; exit 2; }
echo "=== teardown: terminating $INSTANCE"
scw instance server terminate "$INSTANCE" zone=fr-par-2 with-ip=true with-block=true --wait
rm -f "$MARKER"
echo "=== teardown: done"
