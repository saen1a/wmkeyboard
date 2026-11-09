# Gate report — student-quality G0–G7 (local)

> **Superseded 2026-11-09:** the published G6P 90k is recorded by the upstream
> data card as G7 PASS (+0.73 pp vs 2M, CI [+0.15,+1.31], p = 0.018); the
> operator decision is to ship it. The local HOLD/+0.27 below is the earlier
> strict rule (c) on the 10,856,352-byte source candidate. See
> `plans/ship-candidate.md` and `state.md` §2.7; do not mix the two harnesses.

Session: 2026-10-31 10:15 → 2026-11-01 03:08 (Europe/Berlin).
Repo: `G:\C0ding\git\wmkeyboard-wmlm` (WSL `/mnt/g/C0ding/git/wmkeyboard-wmlm`), branch `wmlm-de-research`.
Contract: `plans/student-quality-plan.md`; thresholds `plans/gates.json`; ledger `plans/gate-log.md` (source of truth).

## 1. Gate table

| Gate | Run | Steps | Resumed | Heldout loss | Δ vs reference | Decision | Wall |
|---|---|---|---:|---:|---:|---|---:|
| G0 | dumps (glide/typing, 3 models) | — | — | — | — | **passed** | ~55 min CPU |
| G1 | v1 (no align) | 3 000 | 0 | 5.1943 | reference | **passed** (screen) | 39m39s |
| G1 | v9 (align) | 3 000 | 0 | 5.0304 | −0.1639 nats | **passed** | 40m09s |
| G2 | v1 (no align) | 30 000 | 0 | 4.3087 | reference | **passed** (confirm) | 6h35m |
| G2 | v9 (align) | 30 000 | 0 | 4.1711 | −0.1376 nats | **passed** | 6h38m |
| G3 | v2 (mask) | 3 000 | 0 | 5.0402 | **+0.0098 nats** | not promoted | 40m00s |
| G3 | v3 (mask+weight) | 3 000 | 0 | 5.0283 | **−0.0021 nats** | not promoted | 40m02s |
| G3 | v8 (unigram fill) | — | — | — | — | skipped: measured no-op | 0 |
| G4 | repair confirm | — | — | — | — | **blocked**: G3 promoted no variant | — |
| G5 | alpha 0.3 | — | — | — | — | **blocked**: G4 not entered | — |
| G6 | 60k/90k/120k sweep | — | — | — | — | **blocked**: G4 not passed; `averaging=deferred` | — |
| G7 | export + final paired eval | — | — | — | — | **blocked**: G6 not passed | — |

G1/G2 thresholds: screen −0.05, confirm −0.02 nats. G3 promotion bar was pre-registered at Δ ≤ −0.02 nats against the G1 v9 3 000-step reference (5.0304).
G2 also clears the Glide non-inferiority rule: v9 0.7863 vs v1 0.7825, Δ +0.39 pp, CI [−0.12, +0.89], p = 0.1641 (CI lower ≥ −0.5 pp).

GPU time used: 15.85 h of the 72 h cap (six runs, all `resumed=0`). No cloud, no `scw`, no Docker, no teacher pass, one trainer at a time.

## 2. Paired numbers

### G0 — measurement baseline

Glide harness: 2 588 FUTO swipes, 2 000 typing cases per model. All dumps have exactly `n` rows (2 588 glide, 2 000 typing); `dropped = 0` everywhere.

2M Glide reproduced exactly: `blend top1 0.7848 / top4 0.8485`.

| Pair (A vs B) | Harness / metric | n | acc A | acc B | Δ (A−B) | p_disc | exact p | 95% CI | Holm |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 2M vs 150k | glide / blend_top1 | 2 588 | 0.7848 | 0.7848 | +0.00 pp | 0.0224 | 1.000000 | [−0.58, +0.58] pp | rank 4, thr 0.05, no reject |
| 2M vs 1.2M | glide / blend_top1 | 2 588 | 0.7848 | 0.7794 | **+0.54 pp** | 0.0155 | 0.038477 | **[+0.08, +1.00] pp** | rank 1, thr 0.0125, no reject |
| 2M vs 150k | typing / lm_nextword_top1 | 2 000 | 0.1565 | 0.1600 | −0.35 pp | 0.0615 | 0.588688 | [−1.45, +0.75] pp | rank 3, thr 0.025, no reject |
| 2M vs 1.2M | typing / lm_nextword_top1 | 2 000 | 0.1565 | 0.1525 | +0.40 pp | 0.0470 | 0.470492 | [−0.55, +1.35] pp | rank 2, thr 0.0167, no reject |

The point estimates match the published table (2M vs 150k 0.00 pp; 2M vs 1.2M +0.54 pp). Note: the published +0.54 pp p = 0.038 is unadjusted; under the required Holm correction across this four-test family it is not significant (threshold 0.0125). Exit (d) is about the point estimates, so G0 passes, but the family-wise nuance is recorded.

### G2 — Glide non-inferiority

| Pair | n | acc A (v9) | acc B (v1) | Δ | exact p | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| G2 v9 vs v1, blend_top1 | 2 588 | 0.7863 | 0.7825 | +0.0039 (+0.39 pp) | 0.164149 | [−0.0012, +0.0089] = [−0.12, +0.89] pp |

b = 26, c = 16, p_disc = 0.0162, dropped = 0.

### G7

Not run. `paired_g7.json` and `ship-candidate.md` do not exist because G7's entry (G6 passed) was never met.

## 3. Interruptions and resume

- No training run was interrupted. Every `DONE` file records `resumed=0`; `run_gate.sh` was exercised end-to-end and its `DONE` sha256 is present for all six runs.
- The G0 typing dump loop was cut by the 40-minute shell cap while the 2M typing dump was still running. `typing_eval` writes the `ITEMS` file only at completion, so the partial dump was absent and the run was repeated alone (10:55–11:08). No training checkpoint was involved; no data was lost.
- Preflight correction: the bare precondition probe (`rocminfo`, plain torch import) reports no GPU (`/dev/dri` and `/dev/kfd` absent, `hsa_init Failed`, `cuda.is_available()==False`). With the environment `run_gate.sh` exports (`HSA_ENABLE_DXG_DETECTION=1`), `rocminfo` shows `gfx1200`, torch sees `AMD Radeon RX 9060 XT`, and `device cuda` is printed by every run. The ledger's initial `gpu=FAIL` line is superseded by the appended `preflight_corrected gpu=OK` line.

## 4. Contradictions recorded (measurement wins)

1. **Typing `dropped`:** the prompt expects `dropped > 0` ("the -1 convention is active"); the plan exit (c) expects `dropped == 0`. Measured: `dropped = 0` on all six typing dumps, with 2 000/2 000 rows and no `-1` metric values. The `-1` sentinel exists in `typing_eval.rs` but no metric was uncomputed for this input; the plan's exit (c) is the one that holds.
2. **V8 unigram fill is a no-op:** `soft_mask.py fill` reported `filled-row0 sentences 0` on the 100k slice. `soft_filled.npz` therefore carries the same ids/probs as `soft.npz`, so V8 could not differ from V2. V8 was skipped and recorded as a measured no-op rather than run as a duplicate.
3. **G0 Holm:** as noted in §2, the published 2M-vs-1.2M +0.54 pp does not survive Holm over the four-test family.

## 5. What is still open

The teacher-free lever that remains untested is the **step budget**: the G2 winner (V9 word-aware alignment, no mask/weight, alpha 0.5) was only confirmed at 30k, while G6 would measure 60k/90k/120k and the plateau. The G3 screen shows the mask/weight/fill repairs add nothing at 3k (V2 +0.0098, V3 −0.0021, both inside the 0.014-nat SE), so there is no promoted repair to confirm and G4 cannot be entered under the current contract. G5 (alpha 0.3) is likewise blocked behind G4.

Consequently the chain must be **re-planned before spending the remaining 56 GPU-hours**: either (a) accept the G2 winner as the final recipe and pre-register a new budget gate in place of G4/G5, or (b) define a new repair hypothesis. Threshold shopping is not allowed: the −0.02 promotion bar and the −0.05 screen bar stand as written.

G8 (local 9B contract test) and the L40S teacher pass remain closed: G8 requires G7 complete, and G7 is blocked. No cloud or teacher step was taken.

Artifacts: `artifacts/out/runs/{G1,G2,G3}/*/{run.log,DONE,last.pt,best.pt}`, `artifacts/out/eval_dumps/paired_g0.json`, `artifacts/out/eval_dumps/paired_g2.json`, `artifacts/models/de_candidate_g2_{v1,v9}.wmlm`.

## 6. Post-gate audit addendum (2026-11-01)

Full audit: `plans/student-quality-audit.md`. No gate state was changed; the audit recommends a G5′ re-plan.

1. **G2 exported checkpoint.** `DONE` recorded the final eval (4.3087 / 4.1711), but `export.py` uses `best.pt`, which is step 28,500 with 4.3023 / 4.1686. The exported candidates and the Glide non-inferiority are the best checkpoints; the G2 Δ on them is −0.1337 (final-eval Δ −0.1376). Both pass. The wrapper now records `best_heldout_loss` and `best_step`.
2. **G3 V8 root cause.** `soft_mask.py fill` tested `probs[a:a+topk].sum()` (24 rows) instead of `probs[a].sum()`; `soft_filled.npz` is array-identical to `soft.npz` (100,000/100,000 row-0 empty). A fixed copy fills 99,999/100,000; the fixed V8 screen is 5.0335 vs 5.0304 (no promotion). The original V8 "skipped no-op" is now explained as a code bug, not a data property.
3. **Alpha 0.3 is the strongest 3k lever.** `distill_alpha=0.3` with V9 align and no mask reaches **4.9792** vs 5.0304 reference (**−0.0512 nats**) and 5.0402 V2 (**−0.0610**); with the Piece mask 4.9821. This would pass the pre-registered G5 screen; G5 was blocked behind G4, so it was never run. `distill_share=1.0` (5.0610) and a constant `<unk>` tail (5.0551) are negative.
4. **Typing evaluation bias.** `typing_eval.rs` skips non-ASCII-lowercase words: 8.68% of heldout word tokens (umlauts/ß) are unscored; it uses QWERTY and `primary_language="en"`; its default `SEEDS` path is missing from the repo root, so the base next-word metric is 0. German bigram seeds changed `lm_nextword_top1` by 0.0 pp (200-case check). Use typing as a relative metric only; Glide top1 remains the product metric.
5. **`paired_eval.py` asymmetric `-1`.** A `-1` in A and a computed value in B fails with "item_id sets differ" (verified rc=2). A fixed copy keeps rows, aligns, then drops pairs (n=2, dropped=1, rc=0). Current G0 dumps contain no `-1`, so G0 is unaffected.
6. **Glide sweep.** On a 2-fold split, `RESULTS=16` buys top-4 +0.25…+0.31 pp and top-1 +0.00…+0.08 pp; `RESULTS=32` is identical; `WEIGHT=0.5`/`CAP=5` are already optimal. A wider beam is a top-4/latency decision, not a top-1 lever.
7. **Budget.** 19.17 GPU-hours used of 72 (gates 15.85 + five audit screens 3.32). The next open step is **G5′: alpha 0.3, 30k, with a paired Glide non-inferiority test**, then G6′ on that recipe (60k, then 90k if ≥0.01; 120k would exceed the cap).
8. **G5′ passed (2026-11-01).** Alpha 0.3, V9 align, no mask, 30k: best **4.1177** at step 28,500 (final 4.1183) vs G2-best 4.1686 → **−0.0509 nats**. Glide **0.7871** vs G2-V9 0.7863 = +0.08 pp, CI [−0.43, +0.58], p=0.8804 → non-inferiority passes. vs shipped 2M: +0.23 pp, CI [−0.31, +0.77], p=0.4709 → non-inferior, **not ship** (strict CI lower >0 fails). The final recipe is now V9 align + alpha 0.3, no mask. G6′ 60k is next.
9. **G6′ 60k (2026-11-02).** Same alpha-0.3 recipe, 60k: best **4.0468** at step 57,500 (final 4.0481) vs 30k best 4.1177 → **−0.0709 nats**; the leg beats the previous by ≥0.01, so 90k is required by the plateau rule. 120k is not started: 39.07 + 19.8 + 26.4 > 72 GPU-h. G6′ 90k starts; G7 follows on its best checkpoint.
10. **G6′ 90k / G7 (2026-11-03).** 90k: best **4.0071** at step 88,000 (final 4.0077); vs 60k 4.0468 → **−0.0397 nats**; vs shipped 2M **4.1913 → −0.1842 nats**. G7 on the 90k candidate: Glide **0.7875** vs 2M 0.7848 = +0.27 pp, CI [−0.27, +0.81], p=0.410; vs 1.2M +0.81 pp, CI [+0.31, +1.35], p=0.0038 (Holm reject). Typing next-word 0.1725 vs 2M 0.1565 = **+1.60 pp**, CI [+0.65, +2.55], p=0.00179 (Holm reject); vs 1.2M +2.00 pp, p=0.00029 (Holm reject). Typing strip full set 0.6750 vs 0.6665 = **+0.85 pp**, CI [+0.10, +1.60]; per-register chat +1.20 pp, news +1.00 pp, mean +1.10, no slice degraded. Ship rule: (b) passes; (c) misses the strict full-set 1.0 pp strip bar by 0.15 pp (per-register mean clears it) → **HOLD**, strong near-miss. `ship-candidate.md` records the decision. Budget 58.36/72 GPU-h; 13.64 h left; no new training started.
11. **G0 Holm table correction (2026-11-03).** The earlier G0 table assigned the sorted Holm ranks in input order (the combine zipped the sorted results against the unsorted family). Correct: 2M-vs-1.2M Glide p=0.0385 is rank 1, threshold 0.0125; 2M-vs-1.2M typing p=0.4705 rank 2, 0.0167; 2M-vs-150k typing p=0.5887 rank 3, 0.025; 2M-vs-150k Glide p=1.0 rank 4, 0.05. No test rejects under Holm; the G0 conclusion (no contradiction with the published point estimates) is unchanged. `paired_g0.json`'s family rank fields are stale for this reason; the `holm` array is correct.
