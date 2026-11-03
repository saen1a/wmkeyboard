# Student v2 — next run after the current 90k

Status: prepared 2026-11-02. Do not start while `wmk-glide/artifacts/out/runs/G6P/90k` is still running. The wrapper uses the same `.trainer.lock` and exits 6 if a trainer is active.

## What changed vs. the current 90k

| Change | Value | Why |
|---|---|---|
| **Pieces** | keep the existing 2,048 pieces | **Audit rejected the first `pieces_v2` draft:** it raised training-token `k>6` from 1.165 % to 1.192 %. Do not deploy an unvalidated piece rebuild; `prep_v2.py` remains an experiment. |
| **KD piece soft-weight** | piece rows `0.1`, word rows `1.0`, empty `0.0` | removes the `p_b=1−α` suppression without dropping CE |
| **KD align** | keep the existing `de_soft_2m.masks.align.npz` | word-aware positions; no `3+k` bug; same tokenization as the current 90k |
| **EMA** | `ema_decay=0.999` | free variance reduction; export `best_ema.pt` |
| **Top-k** | 24 (keep) | K=10 is not supported; K=16 is the next A/B, not this run |
| **Steps** | **90,000** | 60k is near plateau; 90k has a slower decay and likely lower heldout; 30k is clearly behind. Product gain still needs G7. |

Why 90k, not 30k/60k:

- 30k G5P: heldout **4.1177** (ppl 61.5).
- 60k: **4.0468** (ppl 57.2), best at 57.5k; the last 5k moved only 4.0468 → 4.0481, i.e. plateau.
- Current 90k at 55k: **4.1441** with LR 3.27e-4; the 60k at 55k was 4.0487 with LR near 0. The 90k is behind at the same step only because its cosine is slower; the final 35k decay is the remaining chance for a real gain. It is not yet proven to beat 4.0468, but 30k is clearly behind and 60k is flat.
- Product gain is still decided by G7, not ppl.

Budget note: the old 72 GPU-h cap is exceeded by this second 90k (~19.8h current + ~19h new ≈ 78h). This is an explicit operator-approved exception. Do not silently start a 30k/60k first.

## Prerequisites (CPU, already prepared)

The existing `de_lm_2m` arrays, `de_soft_2m.masks.align.npz` and the shipped
2,048 pieces are used. The first `prep_v2` draft was audited and **rejected**
because it increased training-token `k>6` from 1.165 % to 1.192 %; do not
deploy it in this run.

```bash
cd /mnt/g/C0ding/git/wmkeyboard-wmlm
PY=/opt/wmlm-venv/bin/python

# Only the soft KD piece weight is new (0.1 on piece rows, 1.0 words, 0 empty)
$PY tools/wmlm/build_kd_weight.py \
  wmk-glide/artifacts/out/de_soft_2m.masks.masks.npz \
  wmk-glide/artifacts/out/de_soft_2m.masks.kdweight.npz
```

If an artifact is missing, the wrapper fails with a clear message. `prep_v2.py`
can be optimized later; it is not part of this run.

## Start (after current 90k DONE)

```bash
cd /mnt/g/C0ding/git/wmkeyboard-wmlm
# gate: current run must be finished
test -f wmk-glide/artifacts/out/runs/G6P/90k/DONE

# optional: export/evaluate the current 90k on CPU first (G7). It does not use the GPU trainer.
# Then start exactly one trainer:
bash wmk-glide/cloud/local/run_student_v2.sh
```

The wrapper:

- refuses if `runs/G6P/90k_v2/DONE` exists for another step count;
- resumes from `last.pt` if present;
- holds `.trainer.lock`; exits 6 if the current 90k still runs;
- writes `flags.json`, `run.log`, `DONE`;
- checks `device cuda`, NaN/Inf, and the final eval;
- prints `best_heldout_loss`, `best_step`, `ema_best_loss`.

## After it finishes

1. Read `wmk-glide/artifacts/out/runs/G6P/90k_v2/DONE`.
2. Export **both** `best.pt` and `best_ema.pt` (if EMA is better) with `tools/wmlm/export.py`; keep the `.wmlm` names distinct.
3. Run the G7 paired Glide/typing eval against the shipped 2M and the current 90k candidate; use Holm correction, per-register slices, and the 2,588-swipe MDE caveat (1.74 pp at 10 % discordance). Do **not** select the checkpoint on Glide; select on heldout.
4. Record the result in `wmk-glide/plans/gate-log.md` / `gate-report.md`.

## Do not

- Do not start a 30k or 60k first; 90k is selected.
- Do not modify the current `runs/G6P/90k` directory or its checkpoints.
- Do not run two trainers on one GPU.
- Do not use the old masks/align with the new `train.npz`.
- Do not treat heldout ppl as the product metric; G7 decides.
