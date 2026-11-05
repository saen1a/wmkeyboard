# NEXT SESSION — autonomous local gate run (G0–G7)

Copy everything below the line into a fresh session.

---

You are running the **student-quality gates G0–G7** autonomously. Read first,
in this order:

1. `wmk-glide/plans/student-quality-plan.md` — the gate contract
2. `wmk-glide/plans/gates.json` — thresholds and per-gate definition
3. `wmk-glide/plans/gate-log.md` — the append-only ledger (may not exist yet)
4. `wmk-glide/plans/teacher-free-results.md` — what is already measured

The plan is the contract. If a measurement contradicts it, the measurement
wins; record the contradiction in the ledger and in the final report.

## Hard constraints

- Work in `G:\C0ding\git\wmkeyboard-wmlm` (WSL: `/mnt/g/C0ding/git/wmkeyboard-wmlm`).
  **Never** work in `.kilo/worktrees/*`.
- **No mutating git command.** No commit, no checkout, no reset, no stash,
  no push. Leave the tree as it is; results are files.
- No cloud, no `scw`, no Docker, no rented GPU, no teacher pass.
- **One trainer at a time.** Two trainers on one card halve both throughputs.
  Harness/eval runs may run in parallel (CPU).
- Never modify `tools/wmlm/*.py`, `wmk-glide/experiments/*`, `native/**`
  except where this prompt explicitly says so (G0).
- Never delete a run directory. Never rebuild a `.masks.npz` while a run holds
  it mmapped (on /mnt/g the replace fails with a permission error).

## Interruption model (minimal data loss)

- Every run goes through `run_gate.sh` (create it in step 0). It:
  skips a run whose `DONE` exists, **resumes** from `last.pt` otherwise,
  writes `run.log`, checks for NaN and for the final eval line, then writes
  `DONE` with the checkpoint sha256 and the exact flag set.
- `train.py` checkpoints every `eval_every=500` steps → at 1.32 steps/s an
  interruption costs **≤ 6.3 minutes**, never a whole run.
- Resume restores weights and step, but resets the AdamW moments and replays
  the LR schedule. A resumed run may show a visible loss jump; the final eval
  stays comparable. `run_gate.sh` records `resumed=1` in `DONE` so the report
  can state it.
- **The ledger `wmk-glide/plans/gate-log.md` is the source of truth**, not the
  JSON. Append one line per event, never rewrite it.

Startup protocol: read the ledger tail; for each gate, list
`$ART/runs/<gate>/*/DONE`. A run without `DONE` is resumed automatically.
Re-running the same command after an interruption is always safe.

## Step 0 — environment and wrapper

Every WSL command is a fresh shell, so **repeat these four assignments at the
top of every command block**:

```bash
REPO=/mnt/g/C0ding/git/wmkeyboard-wmlm
ART=$REPO/wmk-glide/artifacts/out
MODELS=$REPO/wmk-glide/artifacts/models
PY=/opt/wmlm-venv/bin/python          # CPU runs: /home/saenta/wmlm-de/.venv-distill/bin/python in Ubuntu-26.04
```

Preconditions (stop and report if any fails):

```bash
wsl -d Ubuntu-24.04 -- bash -lc 'rocminfo | grep -m1 gfx'
wsl -d Ubuntu-24.04 -- bash -lc '/opt/wmlm-venv/bin/python -c "import torch;print(torch.cuda.is_available(),torch.cuda.get_device_name(0))"'
wsl -d Ubuntu-26.04 -- bash -lc '/home/saenta/wmlm-de/.venv-distill/bin/python -c "import torch,numpy;print(torch.__version__,numpy.__version__)"'
pwsh -c "powercfg /getactivescheme; (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Power').CsEnabled"
```

The GPU run must be `gfx1200` + `True` + `RX 9060 XT`. Windows standby must be
off for the night (`powercfg /change standby-timeout-ac 0`), WSL idle timeout
already set to -1.

Create `wmk-glide/cloud/local/run_gate.sh`:

```bash
#!/usr/bin/env bash
# usage: run_gate.sh <gate> <name> <data_dir> <steps> [train.py flags...]
# Idempotent + resumable. Writes run.log, DONE, and one ledger line per event.
set -uo pipefail
REPO=/mnt/g/C0ding/git/wmkeyboard-wmlm
ART=$REPO/wmk-glide/artifacts/out
MODELS=$REPO/wmk-glide/artifacts/models
PY=/opt/wmlm-venv/bin/python
LEDGER=$REPO/wmk-glide/plans/gate-log.md
GATE=$1; NAME=$2; DATA=$3; STEPS=$4; shift 4
OUT=$ART/runs/$GATE/$NAME
mkdir -p "$OUT"
if [ -f "$OUT/DONE" ]; then echo "[$GATE/$NAME] DONE -> skip"; exit 0; fi
RESUMED=0; RESUME=()
if [ -f "$OUT/last.pt" ]; then RESUMED=1; RESUME=("resume=$OUT/last.pt"); fi
export HSA_ENABLE_DXG_DETECTION=1 LD_LIBRARY_PATH=/opt/rocm-7.2.1/lib \
       TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1 PYTHONUNBUFFERED=1
echo "## $(date -Is) start gate=$GATE run=$NAME steps=$STEPS resumed=$RESUMED $*" >> "$LEDGER"
TIMEOUT=$((STEPS / 1 + 7200))   # ≥1 step/s budget plus 2 h slack
timeout "${TIMEOUT}s" "$PY" "$REPO/tools/wmlm/train.py" "$DATA" "$OUT" \
    "steps=$STEPS" "eval_every=500" "${RESUME[@]}" "$@" 2>&1 | tee -a "$OUT/run.log"
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ]; then
    echo "## $(date -Is) fail gate=$GATE run=$NAME rc=$rc" >> "$LEDGER"; exit "$rc"
fi
grep -qiE '\b(nan|inf)\b' "$OUT/run.log" && {
    echo "## $(date -Is) fail gate=$GATE run=$NAME reason=nan" >> "$LEDGER"; exit 3; }
if ! grep -q "eval step $STEPS " "$OUT/run.log"; then
    echo "## $(date -Is) fail gate=$GATE run=$NAME reason=no_final_eval" >> "$LEDGER"; exit 4
fi
LOSS=$(grep -oE "eval step $STEPS heldout loss [0-9.]+" "$OUT/run.log" | tail -1 | awk '{print $NF}')
SHA=$(sha256sum "$OUT/last.pt" | cut -d' ' -f1)
printf 'gate=%s run=%s steps=%s resumed=%s heldout_loss=%s sha256=%s flags=%s\n' \
    "$GATE" "$NAME" "$STEPS" "$RESUMED" "$LOSS" "$SHA" "$*" > "$OUT/DONE"
echo "## $(date -Is) done gate=$GATE run=$NAME loss=$LOSS resumed=$RESUMED" >> "$LEDGER"
```

Run it with `bash` from `/mnt/g/...` in **Ubuntu-24.04** (GPU). `eval_every=500`
is the interruption granularity; do not raise it.

## Step 1 — G0 measurement baseline

1. Fix the typing dump denominator: in
   `native/wm-engine/examples/typing_eval.rs`, write **`-1`** instead of `0`
   for every metric the case does not compute (no previous word). Do not
   change stdout. Rebuild in WSL: `cargo build --release --example typing_eval`.
2. Re-run all dumps, 2 000 typing cases:

```bash
cd /mnt/g/C0ding/git/wmkeyboard-wmlm
REPO=$PWD; ART=$REPO/wmk-glide/artifacts/out; MODELS=$REPO/wmk-glide/artifacts/models
mkdir -p "$ART/eval_dumps"
export RESULTS=8 COLS=11 THREADS=8 FREQ=0.5 GAP=2.0 WEIGHT=0.5 CAP=5
export CASES=2000 SCATTER=fast MODES=base,lm SAVINGS=0 LMBLEND=0.5 LMBCAP=5.0
for m in de_context_4b150k de_context_1m2 de_context_2m; do
  ITEMS=$ART/eval_dumps/glide_$m.tsv native/wm-engine/target/release/examples/glide_lm_blend_eval \
    wmk-glide/artifacts/data/de_swipes.jsonl wmk-glide/artifacts/data/german.json \
    wmk-glide/artifacts/data/de_150k_comp3.txt $MODELS/$m.wmlm
  ITEMS=$ART/eval_dumps/typing_$m.tsv native/wm-engine/target/release/examples/typing_eval \
    wmk-glide/artifacts/data/de_150k.txt $ART/de_lm_2m/heldout.tsv $MODELS/$m.wmlm
done
```

3. Paired checks (run from Ubuntu-26.04, CPU venv):
   `paired_eval.py <A> <B> --metric blend_top1` for 2m↔1m2 and 2m↔150k, and
   `--metric lm_nextword_top1` on typing.

**Exit:** 2M Glide reproduces `0.7848 / 0.8485`; dump row count == the
harness `n`; typing `dropped > 0` (the -1 convention is active) and the
pair deltas reproduce the committed table (2M vs 150k ≈ 0 pp; 2M vs 1.2M
≈ +0.5 pp, CI excludes 0).
**Abort:** if the Glide numbers differ, stop — wrong harness build.

## Step 2 — G1 alignment screen (2 × 45 min)

Data `$ART/de_lm_2m_slice100k`, both runs identical except the align flag:

```bash
bash run_gate.sh G1 v1 $ART/de_lm_2m_slice100k 3000 \
  distill=$ART/de_lm_2m_slice100k/soft.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
bash run_gate.sh G1 v9 $ART/de_lm_2m_slice100k 3000 \
  distill=$ART/de_lm_2m_slice100k/soft.npz distill_align=$ART/de_lm_2m_slice100k/masks.align.npz \
  batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
```

**Exit:** `loss(v9) < loss(v1) − 0.05` nats (read both `DONE` files).
**Fail:** V9 retires. Continue with G3 using `v1` as reference; skip G2.

## Step 3 — G2 alignment confirm (2 × 6.3 h)

Full data, 30k steps, **no mask/weight** (pure alignment test):

```bash
bash run_gate.sh G2 v1 $ART/de_lm_2m 30000 distill=$ART/de_soft_2m.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
bash run_gate.sh G2 v9 $ART/de_lm_2m 30000 distill=$ART/de_soft_2m.npz distill_align=$ART/de_soft_2m.masks.align.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
```

Export both and measure paired Glide:

```bash
$PY tools/wmlm/export.py $ART/runs/G2/v1/best.pt $ART/de_lm_2m/vocab.txt $MODELS/de_candidate_g2_v1.wmlm
$PY tools/wmlm/export.py $ART/runs/G2/v9/best.pt $ART/de_lm_2m/vocab.txt $MODELS/de_candidate_g2_v9.wmlm
# then ITEMS=... glide_lm_blend_eval for each, then paired_eval --metric blend_top1
```

**Exit:** `loss(v9) < loss(v1) − 0.02` nats **and** Glide delta ≥ −0.5 pp
(non-inferiority). Otherwise keep V1 as reference and record the negative.

## Step 4 — G3 repair screens (3 × 45 min)

Reference for all three is the **G1/G2 winner at 3 000 steps on `slice100k`**
(already on disk; do not re-run it). Build the filled soft file once:

```bash
$PY tools/wmlm/soft_mask.py unigram $ART/de_lm_2m $ART/de_soft_2m.unigram.npz
$PY tools/wmlm/soft_mask.py fill $ART/de_lm_2m $ART/de_lm_2m_slice100k/soft.npz \
    $ART/de_lm_2m_slice100k/masks.masks.npz $ART/de_lm_2m_slice100k/soft_filled.npz \
    --unigram $ART/de_soft_2m.unigram.npz
```

```bash
BASE="batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0"
ALIGN="distill_align=$ART/de_lm_2m_slice100k/masks.align.npz"   # only if G1 passed
bash run_gate.sh G3 v2 $ART/de_lm_2m_slice100k 3000 distill=$ART/de_lm_2m_slice100k/soft.npz $ALIGN \
  distill_mask=$ART/de_lm_2m_slice100k/masks.keep.kd.npz $BASE
bash run_gate.sh G3 v3 $ART/de_lm_2m_slice100k 3000 distill=$ART/de_lm_2m_slice100k/soft.npz $ALIGN \
  distill_mask=$ART/de_lm_2m_slice100k/masks.keep.kd.npz \
  distill_weight=$ART/de_lm_2m_slice100k/masks.masks.npz $BASE
bash run_gate.sh G3 v8 $ART/de_lm_2m_slice100k 3000 distill=$ART/de_lm_2m_slice100k/soft_filled.npz $ALIGN \
  distill_mask=$ART/de_lm_2m_slice100k/masks.keep.kd.npz $BASE
```

**Exit:** each `Δ ≤ −0.02` nats vs the reference is promoted.
**Abort:** if V2 is worse by >0.05 nats, V2/V3/V8 retire together.

## Step 5 — G4 repair confirm (6.3 h)

Best promoted variant, full data, 30k, same flags as its screen but
`distill=$ART/de_soft_2m.npz`, `distill_align=$ART/de_soft_2m.masks.align.npz`,
`distill_mask=$ART/de_soft_2m.masks.keep.kd.npz` (+ weight if V3).
**Exit:** `Δ ≤ −0.02` nats vs the G2 winner at 30k **and** Glide ≥ −0.5 pp.
Export and pair it against `de_candidate_g2_*`.

## Step 6 — G5 alpha screen (45 min + 6.3 h)

`distill_alpha=0.3` on top of the G4 winner, 3 000 steps on `slice100k`,
compared to the same base at alpha 0.5. Confirm at 30k only if the screen is
`≤ −0.02` nats.

## Step 7 — G6 budget sweep (12.6 / 18.9 / 25.2 h)

Final recipe on `de_lm_2m` at 60k, then 90k, then 120k — **stop at the first
leg that beats the previous by <0.01 nats** (plateau). Do not start 90k/120k
if the plateau rule already fired.

Checkpoint averaging is **deferred**: `train.py` keeps only `last.pt`/`best.pt`,
no per-eval snapshots, and this session must not modify it. Record
`averaging=deferred` in the ledger.

## Step 8 — G7 export and final evaluation (1 h)

Export the best leg's `best.pt`, run Glide (2 588 swipes) and typing
(2 000 cases) with `ITEMS`, then `paired_eval --metric blend_top1` (and
`lm_nextword_top1`) against `de_context_2m` and `de_context_4b150k`, with
`--holm` across the family. Split the typing set by `field=1` (chat) vs
`field=0` (news) and report both.

**Ship rule:** candidate vs 2M Glide **CI lower > 0**, or heldout ppl better
by ≥0.1 with Glide CI lower ≥ −0.5 pp. Anything else is "no ship, documented".

## Failure and budget protocol

- A failed gate records its metric and retires the hypothesis. Do not rerun
  with a different threshold.
- A run that fails twice for the same reason (OOM, NaN, missing file) is
  reported and skipped; continue with the next independent gate.
- Caps: **72 GPU-hours total**, **5 calendar nights**, one trainer. Count from
  `run.log` timestamps (`start`/`done` lines in the ledger).
- If the caps are hit mid-chain: finish the current run, write the report, stop.

## Final report

Append to `wmk-glide/plans/gate-report.md`:

1. A table: gate, run, steps, resumed (0/1), heldout loss, Δ vs reference,
   decision (promoted / retired / skipped), wall time.
2. The paired numbers from G0 and G7 with `n`, `p_disc`, exact p, CI.
3. What was interrupted and how it was resumed (so the next session knows the
   checkpoint quality).
4. One paragraph: which teacher-free lever is still open, and whether the
   next step is G8 (local 9B contract test) or the L40S teacher pass.

Do not write a summary anywhere else; `gate-report.md` is the single output.
