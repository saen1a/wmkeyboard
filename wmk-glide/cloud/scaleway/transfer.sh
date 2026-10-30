#!/usr/bin/env bash
# Move corpus, prep data and results between this machine and the H100.
#
#   bash transfer.sh up    <user@host>    # corpus + artifacts scripts up
#   bash transfer.sh down  <user@host>    # soft targets, model, eval, logs down
#   bash transfer.sh check <user@host>    # sizes + sha256 on both sides
#
# SSH options come from the environment so no key path or secret is ever
# echoed: SCW_SSH_KEY_PATH (default ~/.ssh/id_ed25519), SCW_SSH_USER,
# SCW_INSTANCE_IP. A path in $1 still wins for quick tests.
# Nothing here prints the contents of credentials files.
set -euo pipefail

MODE=${1:?usage: transfer.sh up|down|check <user@host>}
HOST=${2:?usage: transfer.sh up|down|check <user@host>}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=${ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}
ART=${ART:-$ROOT/wmk-glide/artifacts}
KEY=${SCW_SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}
REMOTE_ROOT=${REMOTE_ROOT:-/root/wmk}
# Where the run actually writes: the README sends teacher output and models
# to the block volume, not into the repo checkout.
REMOTE_ART=${REMOTE_ART:-/data}
# These two are interpolated into a remote shell string, so they must not be
# able to carry shell syntax. Reject every character outside the allowlist and
# any `..` component - a bare `case /[A-Za-z0-9._/-]*` would still accept
# `/data;rm -rf /` because the trailing `*` matches anything.
for _p in "$REMOTE_ROOT" "$REMOTE_ART"; do
  case "$_p" in
    ""|*[!A-Za-z0-9._/-]*|*/../*|*/..|*//*) echo "refusing unsafe remote path: $_p" >&2; exit 2 ;;
    /*) : ;;
    *) echo "refusing relative remote path: $_p" >&2; exit 2 ;;
  esac
done
# accept-new on first contact (fresh instance, unknown IP); SSH_STRICT=1 once
# the host key is trusted (rotation or repeated runs on a fixed IP).
SSH_HOSTKEY=${SSH_STRICT:+yes}; SSH_HOSTKEY=${SSH_HOSTKEY:-accept-new}
RSYNC_RSH="ssh -i $KEY -o StrictHostKeyChecking=$SSH_HOSTKEY -o ServerAliveInterval=30"
# Never ship anything that can hold a credential. The filled env file lives
# outside the repo, but a copy next to the template must not travel.
EXCLUDES=(--exclude '*.pyc' --exclude '__pycache__' --exclude 'node_modules' --exclude '.git'
          --include 'credentials.example.env' --exclude '*.env'
          --exclude '*.key' --exclude '*.pem'
          --exclude 'id_*' --exclude '*_ed25519')

echo "=== transfer $MODE $HOST (root $ROOT -> $REMOTE_ROOT, results $REMOTE_ART)"

case "$MODE" in
  up)
    ssh -i "$KEY" -o StrictHostKeyChecking="$SSH_HOSTKEY" "$HOST" \
      "mkdir -p $REMOTE_ART/out $REMOTE_ART/models $REMOTE_ART/logs \
                $REMOTE_ROOT/wmk-glide/artifacts/corpora $REMOTE_ROOT/wmk-glide/artifacts/data \
                $REMOTE_ROOT/wmk-glide/tools $REMOTE_ROOT/wmk-glide/cloud/scaleway \
                $REMOTE_ROOT/wmk-glide/experiments \
                $REMOTE_ROOT/tools/wmlm $REMOTE_ROOT/native/wm-engine \
                $REMOTE_ROOT/app/src/main/assets/dictionaries $REMOTE_ROOT/app/src/main/assets/avro"
    rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
      "$ROOT/tools/wmlm/" "$HOST:$REMOTE_ROOT/tools/wmlm/"
    rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
      "$ROOT/wmk-glide/tools/" "$HOST:$REMOTE_ROOT/wmk-glide/tools/"
    # prep_train_eval.sh copies glide_lm_blend_eval.rs from here into the
    # engine's examples/ directory before building it.
    rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
      "$ROOT/wmk-glide/experiments/" "$HOST:$REMOTE_ROOT/wmk-glide/experiments/"
    rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
      "$ROOT/wmk-glide/cloud/scaleway/" "$HOST:$REMOTE_ROOT/wmk-glide/cloud/scaleway/"
    # The measurement phase builds and runs the Rust harness on the box.
    # `include_str!` in native/wm-engine/src/cjk pulls in the app assets
    # (pinyin syllables), so those tiny dictionaries have to travel too.
    rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
      "$ROOT/native/wm-engine/" "$HOST:$REMOTE_ROOT/native/wm-engine/"
    rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
      "$ROOT/app/src/main/assets/dictionaries/" \
      "$HOST:$REMOTE_ROOT/app/src/main/assets/dictionaries/"
    rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
      "$ROOT/app/src/main/assets/avro/" \
      "$HOST:$REMOTE_ROOT/app/src/main/assets/avro/"
    # Corpora + eval data. Soft targets and models stay local during setup.
    # The raw corpora (~256 MB) are only needed if prep.py runs on the box;
    # prep usually happens locally, so skip them unless CORPORA=1. This is
    # the difference between ~30 s and ~3 min on a home uplink.
    if [ "${CORPORA:-0}" = "1" ]; then
      rsync -az --info=progress2 -e "$RSYNC_RSH" \
        "$ART/corpora/de_1m_200k_chat.tsv" "$ART/corpora/de_2m_mix.tsv" \
        "$ART/corpora/de_2m_mix.tsv.manifest.json" "$ART/corpora/de_2m_mix.tsv.sha256" \
        "$HOST:$REMOTE_ROOT/wmk-glide/artifacts/corpora/"
    else
      rsync -az --info=progress2 -e "$RSYNC_RSH" \
        "$ART/corpora/de_2m_mix.tsv.manifest.json" "$ART/corpora/de_2m_mix.tsv.sha256" \
        "$HOST:$REMOTE_ROOT/wmk-glide/artifacts/corpora/"
      echo "note: corpora not uploaded (CORPORA=1 to include the raw TSVs for prep.py)"
    fi
    rsync -az --info=progress2 -e "$RSYNC_RSH" \
      "$ART/data/heldout.tsv" "$ART/data/german.json" "$ART/data/de_150k.txt" \
      "$ART/data/de_150k_comp3.txt" "$ART/data/de_aosp.txt.gz" "$ART/data/de_swipes.jsonl" \
      "$HOST:$REMOTE_ROOT/wmk-glide/artifacts/data/"
    # Fixed 100+100 sentence selection for the teacher A/B, so every model and
    # every host measures exactly the same sentences.
    if [ -f "$ART/out/ab_sentences.tsv" ]; then
      rsync -az --info=progress2 -e "$RSYNC_RSH" \
        "$ART/out/ab_sentences.tsv" "$HOST:$REMOTE_ROOT/wmk-glide/artifacts/out/"
    fi
    # Prepared corpora (vocab.txt + train.npz + heldout) the collector and
    # the student read. Skip the huge shard dirs of a previous run.
    for d in "$ART"/out/de_lm_*; do
      [ -d "$d" ] || continue
      rsync -az --info=progress2 "${EXCLUDES[@]}" -e "$RSYNC_RSH" \
        "$d" "$HOST:$REMOTE_ROOT/wmk-glide/artifacts/out/"
    done
    echo "=== up done"
    ;;
  down)
    mkdir -p "$ART/out" "$ART/models" "$ART/logs"
    rsync -az --info=progress2 -e "$RSYNC_RSH" \
      "$HOST:$REMOTE_ART/out/" "$ART/out/"
    # Models are re-downloadable inputs: the 27B alone is 29 GB, and pulling
    # it made teardown move 28.8 GB over a home uplink for nothing. The
    # exported student is tiny (~11 MB) and lives next to them in
    # /data/models (prep_train_eval.sh RUN_ROOT), so it always comes along.
    rsync -az --info=progress2 -e "$RSYNC_RSH" \
      --include '*.wmlm' --include '*.wmlm.sha256' --exclude '*' \
      "$HOST:$REMOTE_ART/models/" "$ART/models/" 2>/dev/null || true
    if [ "${MODELS:-0}" = "1" ]; then
      rsync -az --info=progress2 -e "$RSYNC_RSH" \
        "$HOST:$REMOTE_ART/models/" "$ART/models/"
    else
      echo "note: teacher checkpoints stay on the box (MODELS=1 to pull them)"
    fi
    rsync -az --info=progress2 -e "$RSYNC_RSH" \
      "$HOST:$REMOTE_ART/logs/" "$ART/logs/" 2>/dev/null || true
    echo "=== down done; verify with: $0 check $HOST"
    ;;
  check)
    echo "--- local"
    (cd "$ART" && find out models -name '*.npz' -o -name '*.sha256' -o -name '*.wmlm' | sort | xargs -r sha256sum)
    echo "--- remote ($REMOTE_ART)"
    ssh -i "$KEY" "$HOST" "cd $REMOTE_ART && find out models -name '*.npz' -o -name '*.sha256' -o -name '*.wmlm' | sort | xargs -r sha256sum"
    ;;
  *)
    echo "unknown mode: $MODE" >&2
    exit 2
    ;;
esac

