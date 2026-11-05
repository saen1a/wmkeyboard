# Student-quality plan — gates for every non-teacher step

Companion to `teacher-free-plan.md` (variants) and `teacher-free-results.md`
(measurements). This document is the **execution contract**: it defines the
gates that must pass before the next step may start, the artefact each gate
leaves behind, and the exact command.

Scope: **everything that is not a teacher pass** — data derivation, student
training, evaluation, export. The teacher pass appears only in §6 as a priced
option behind a gate (G8).

Baseline measured 2026-10-31 (see `teacher-free-results.md`):

| fact | value |
|---|---|
| Glide harness, 2 588 FUTO swipes, reproduced | `blend top1 0.7848 / top4 0.8485` in 35 s |
| 2M vs 1.2M | **+0.54 pp**, CI [+0.08, +1.00], McNemar p = 0.038 |
| 2M vs 150k | 0.00 pp, CI [−0.58, +0.58], p = 1.000 |
| student throughput, local RX 9060 XT | 1.32 steps/s @ batch 256 (30k = 6.3 h) |
| masked+aligned path | 1.03 steps/s while two other trainers shared the card |
| screens on `slice100k`, 3 000 steps | ~38–45 min |
| heldout eval noise | ~0.014 nats SE (8 000 sentences ≈ 86k positions) |

**Rule that orders everything:** a gate may only be entered when its
predecessor is `passed`. A `failed` gate retires its hypothesis; it does not
get re-run with a new threshold.

---

## 1. Gate model

Each gate has: **entry** (precondition), **run** (command), **artefact**,
**exit** (numerical rule), **abort** (cost guard) and **rollback**.

Screen threshold is pre-registered at **0.05 nats** heldout loss; confirm
threshold at **0.02 nats**. Both are far above the 0.014-nat SE and were fixed
before any run.

| Gate | What | Machine | Wall | € | Blocks |
|---|---|---|---:|---:|---|
| G0 | measurement baseline | CPU only | 1 h | 0 | G1 |
| G1 | alignment screen | local GPU | 1.5 h | 0 | G2 |
| G2 | alignment confirm | local GPU | 12.6 h | ~0.8 | G3 |
| G3 | repair screens (V2/V3/V8) | local GPU | 2.2 h | ~0.15 | G4 |
| G4 | repair confirm | local GPU | 6.3 h | ~0.5 | G5 |
| G5 | alpha screen (+confirm) | local GPU | 1.5–7 h | ~0.1–0.6 | G6 |
| G6 | budget sweep + averaging | local GPU | 13–38 h | ~1–3 | G7 |
| G7 | export + final paired eval | CPU + 1 min GPU | 1 h | 0 | ship / G8 |
| G8 | optional local contract test (9B) | local GPU | 11 h | 0 | H100 decision |

Local total: **36–62 h GPU ≈ 3–5 nights**, 4–7 € electricity.
Cloud equivalent (if ever needed): see §5.

---

## 2. Gates in detail

### G0 — Measurement baseline (no training)

**Entry:** none.
**Run:**
1. `typing_eval.rs`: write `-1` for cases without a previous word, so the dump
   denominator equals the summary denominator (currently 15.0 % vs 17.18 % on
   the same run). Rebuild: `cargo build --release --example typing_eval`.
2. Typing cases 500 → 2 000 (`CASES=2000`), so the MDE drops 3.95 → ~2.0 pp.
3. Dumps for the three shipped models:
   `de_context_4b150k`, `de_context_1m2`, `de_context_2m`.
4. `paired_eval.py` over the pairs, with `--holm` across the family.

**Artefacts:** `artifacts/out/eval_dumps/{glide,typing}_<model>.tsv`,
`artifacts/out/eval_dumps/paired_g0.json`.
**Exit:** (a) the 2M Glide dump reproduces `0.7848 / 0.8485` exactly;
(b) dump row count == the harness `n` for every model; (c) `dropped == 0` on
typing; (d) the G0 paired table has no contradiction with the published
numbers (2M vs 150k ≈ 0, 2M vs 1.2M ≈ +0.5 pp).
**Abort:** if (a) fails, stop — the harness build is not the released one.
**Rollback:** none (read-only pass).

### G1 — Alignment screen: V1 vs V9

**Entry:** G0 passed; `de_lm_2m_slice100k` masks + align exist.
**Run (two runs, seed 0, 3 000 steps, batch 256, `slice100k`):**
```bash
# V1 (historic placement) and V9 (word-aware) — identical except distill_align=
bash wmk-glide/cloud/local/run_rocm.sh MODE=train data=$ART/de_lm_2m_slice100k \
  distill=$ART/de_lm_2m_slice100k/soft.npz steps=3000 batch=256 \
  out=$ART/runs/g1_v1
bash wmk-glide/cloud/local/run_rocm.sh MODE=train data=$ART/de_lm_2m_slice100k \
  distill=$ART/de_lm_2m_slice100k/soft.npz steps=3000 batch=256 \
  align=$ART/de_lm_2m_slice100k/masks.align.npz out=$ART/runs/g1_v9
```
**Exit:** `loss_V9 < loss_V1 − 0.05` nats at step 3 000 (best of the last three
evals), no NaN, `device cuda`.
**Abort:** if either run drops below 0.8 steps/s, stop and re-measure
throughput before drawing conclusions.
**Rollback:** hypothesis V9 retires; G2 is skipped and G3 runs against V1.

### G2 — Alignment confirm (2M, 30k)

**Entry:** G1 passed.
**Run:** same two configs on `de_lm_2m`, `steps=30000`, plus
`masks.keep.kd.npz`/`masks.masks.npz` **only** if G3 has already passed — G2
itself must stay a pure alignment test. Two runs, 12.6 h.
**Export:** `tools/wmlm/export.py` equivalent (as in earlier sessions) →
`de_context_2m_align.wmlm`.
**Exit:** `loss_V9 < loss_V1 − 0.02` nats **and** paired Glide
`blend_top1` delta ≥ −0.5 pp (non-inferiority on 2 588 items).
**Abort:** total spend cap for G2 = 2 GPU-nights; no re-runs with changed
hyperparameters.
**Rollback:** keep V1 as reference; V9 becomes a documented negative result.

### G3 — Repair screens: V2 (mask), V3 (weight), V8 (unigram fill)

**Entry:** G2 passed (so all three build on the winning alignment).
**Run:** three 3 000-step runs on `slice100k`, each differing from the G2
winner by exactly one flag:
- V2: `distill_mask=$ART/de_lm_2m_slice100k/masks.keep.kd.npz`
- V3: V2 + `distill_weight=$ART/de_lm_2m_slice100k/masks.masks.npz`
- V8: V2 + `distill=<slice100k>/soft_filled.npz` (row-0 unigram fill)
**Exit:** each variant reported with its own delta to the winner; promotion for
any variant with `Δ ≤ −0.02` nats. Holm across the three p-values if Glide is
used.
**Abort:** if the mask raises loss by > 0.05 nats, V2/V3/V8 retire together
(the mask is their common base).
**Rollback:** the winner's flag set is recorded; the others are documented.

### G4 — Repair confirm

**Entry:** G3 promoted ≥1 variant.
**Run:** best variant on `de_lm_2m`, 30k steps, one run (6.3 h).
**Exit:** `Δ ≤ −0.02` nats vs the G2 winner at 30k **and** Glide
non-inferior (CI lower bound ≥ −0.5 pp).
**Rollback:** drop the repair, keep the G2 winner.

### G5 — Alpha screen

**Entry:** G4 passed.
**Run:** `distill_alpha=0.3` (more CE, the documented tail-drift counterweight)
on `slice100k`, 3 000 steps; confirm at 30k only if it wins.
**Exit:** `Δ ≤ −0.02` nats screen, then `Δ ≤ −0.02` nats confirm.
**Rollback:** alpha stays 0.5.

### G6 — Budget sweep + checkpoint averaging

**Entry:** G4 (and optionally G5) passed.
**Run:** 30k / 60k / 90k / 120k on the final recipe, `eval_every=1000`.
Then average `last.pt` from the last three evals of the best leg (free).
**Exit:** pick the leg with the lowest heldout loss whose loss did not rise in
two consecutive evals; the average must not be worse than its best member.
**Abort:** stop the sweep at the first leg that beats the previous by <0.01
nats — that is the plateau.
**Rollback:** previous recipe remains shippable.

### G7 — Export and final paired evaluation

**Entry:** G6 passed.
**Run:** export `<candidate>.wmlm` (int8, strip), Glide on 2 588 swipes,
typing on 2 000 cases, per-register split, `paired_eval.py --holm` over
{candidate vs 2M, candidate vs 150k}.
**Exit (ship):** (a) `candidate vs 2M`: Glide CI lower bound > 0 **or**
(b) heldout ppl better by ≥0.1 with Glide non-inferior (CI lower ≥ −0.5 pp).
Everything else is "no ship, document".
**Artefact:** `artifacts/out/eval_dumps/paired_g7.json` + a one-page
`plans/ship-candidate.md`.
**Abort:** never ship on a single marginal p; the rule is the CI, not the p.

### G8 — Optional: local contract test with a 9B teacher on 100k

**Entry:** G7 complete **and** the remaining gap is plausibly target quality
(G7 shows local levers exhausted).
**Run:** `distill.py` with the new target contract (word-space mapping, true
tail mass, BOS rows) against a 9B-8bit teacher on 100k sentences (~10.8 h at
2.58 sentences/s), then a 5 000-step student screen.
**Exit:** the new contract beats the current one by ≥0.05 nats at equal steps.
**Only then** price the H100 pass (§6).

---

## 3. Naming and artefacts

```
artifacts/out/runs/<gate>/<variant>/          checkpoints, run.log, resolved flags
artifacts/out/eval_dumps/<model>/<harness>.tsv
artifacts/out/eval_dumps/paired_<gate>.json   gate evidence
plans/gates.json                              gate registry + state
```
Every run writes its exact flag set (`flags.json`) next to the checkpoint, so
a result can never be attributed to the wrong config.

---

## 4. Stop rules

1. No cloud spend for G0–G7. Local GPU only.
2. One gate at a time; no parallel trainers (halves both runs, measured).
3. A failed gate retires its hypothesis — no threshold shopping.
4. Selection of `best.pt` on heldout ppl only; Glide is measured once per
   candidate.
5. Budget cap for the whole local phase: **5 nights**; if G2 has not passed by
   then, stop and re-plan instead of continuing.

---

## 5. Cloud evaluation (live prices, fr-par-2, 2026-10-31, pre-tax)

Prices read from the Scaleway CLI (`scw instance server-type list
zone=fr-par-2`) — not from a comparison site:

| Type | GPU | VRAM | vCPU | RAM | €/h | Stock |
|---|---|---|---:|---:|---:|---|
| L4-1-24G | 1× L4 | 24 GB | 8 | 48 GB | **0.7875** | available |
| L4-2-24G | 2× L4 | 48 GB | 16 | 96 GB | 1.5750 | available |
| L40S-1-48G | 1× L40S | 48 GB | 8 | 96 GB | **1.46988** | available |
| L40S-2-48G | 2× L40S | 96 GB | 16 | 192 GB | 2.93982 | scarce |
| H100-1-80G | 1× H100 PCIe | 80 GB | 24 | 240 GB | **2.8665** | **available** (was out of stock) |
| H100-2-80G | 2× H100 PCIe | 160 GB | 48 | 480 GB | 5.7330 | scarce |
| H100-SXM-2-80G | 2× H100 SXM | 160 GB | 32 | 240 GB | 6.6198 | available |
| H100-SXM-4/8 | 4/8× SXM | 320/640 GB | 64/128 | 480/960 GB | 12.771 / 25.3308 | scarce / shortage |
| B300-SXM-8-288G | 8× B300 | 2304 GB | 224 | 4 TB | 60.0000 | shortage |
| RENDER-S | 1× Tesla P100 | 16 GB | 10 | 45 GB | 1.2210 | available |

### 5.1 Student training (30 000 steps, batch 256, 10M params)

The step is **overhead-bound**, not compute-bound: 0.63 TFLOP/step, and the
9060 XT achieves only ~0.8 TFLOP/s effective (≈4 % of the card). So cloud
throughput does not scale with TFLOPS; estimates below are deliberately
conservative and marked as estimates.

| Machine | est. steps/s | 30k wall | cost/run | note |
|---|---:|---:|---:|---|
| local 9060 XT | 1.32 (measured) | 6.3 h | 0 € | reference |
| L4-1-24G | 2–2.5 | 3.3–4.2 h | **2.6–3.3 €** | cheapest cloud |
| L40S-1-48G | 2.5–3.5 | 2.4–3.3 h | 3.5–4.9 € | |
| H100-1-80G | 4–6 | 1.4–2.1 h | 4.0–6.0 € | 24 vCPU help here |
| RENDER-S (P100) | 1–1.5 | 5.5–8.3 h | 6.7–10.2 € | hourly billing |

**Verdict:** for the student, cloud buys wall-clock at 2.6–10 € per run.
Local is unbeatable in €/result. Cloud only makes sense if 3 nights are too
slow — then L4-1-24G is the value pick, H100 the fastest.

### 5.2 Teacher pass (27B, 2M sentences) — the only cloud-worthy job

| Type | throughput | 2M wall | cost | € / 1M sentences |
|---|---:|---:|---:|---:|
| L40S-1-48G | **55.8 sentences/s** (measured, our smoke) | 10.0 h | **≈15 €** | **7.32 €** |
| H100-1-80G | 95.2 sentences/s (1.2M in 3.5 h) | 5.8 h | ≈17 € | 8.36 € |
| L4-1-24G | — | — | — | **impossible**: 24 GB < ~28 GB FP8 weights |
| RENDER-S | — | — | — | **impossible**: 16 GB |
| L40S-2 / H100-2 | no gain | — | — | a single 27B does not need two cards; vLLM batch is not the bottleneck |
| B300-SXM | overkill | — | — | only relevant for 70B+ or 100k-token contexts |

**Verdict: L40S-1-48G is the best price/performance for the teacher pass**
(12.5 % cheaper per sentence than H100, at 1.7× the wall clock). H100 is the
choice only if the 10 h window is inconvenient. Both are in stock today.

### 5.3 Screens / confirms / evaluation on cloud

| job | local | L4 | L40S | H100 |
|---|---:|---:|---:|---:|
| screen 3k steps | 38–45 min, 0 € | ~25 min, 0.33 € | ~20 min, 0.49 € | ~10 min, 0.48 € |
| confirm 30k | 6.3 h, 0 € | 3.3 h, 2.6 € | 2.4 h, 3.5 € | 1.4 h, 4.0 € |
| Glide dump (2 588) | 35 s | 35 s | 35 s | 35 s |
| whole G0–G7 on cloud | 36–62 h | ~16 € | ~24 € | ~30 € |

### 5.4 Does the RENDER endpoint work?

Two readings, both answered:

**A) `RENDER-S` instance (the "Render" offer in Scaleway's GPU list).**
It is 1× **Tesla P100 16 GB** (Pascal, 2016), 10 vCPU, 45 GB RAM, 400 GB local
NVMe, **€1.221/h, billed per hour** (every other GPU is per minute,
`docs/instances/faq`).
- Teacher pass: **no** — 16 GB cannot hold 27B FP8 (~28 GB).
- Student: technically yes (10M params), but it is the worst option: Pascal has
  no bf16/FP8, no Flash-Attention (our `model.py` uses
  `scaled_dot_product_attention`, which would fall back), it costs 55 % more
  than the L4, and hourly billing turns a 20-min screen into a full hour.
- **Verdict: not usable for this task.**

**B) A managed inference endpoint** (Scaleway "Generative APIs – Dedicated
Deployment", formerly Managed Inference; H100 €3.40/h, L40S €1.72/h, L4
€0.93/h).
It could host a 27B teacher, but it **cannot produce our soft targets**: we need
raw top-k **log-probabilities over our own 24 576-token vocabulary at every
prompt position**, projected through `distill.py`'s teacher→student mapping.
A sampling API returns tokens, not that matrix; per-token pricing would then
also exceed the ~15 € of a self-hosted vLLM run. It is the right product for
serving, the wrong one for distillation.

---

## 6. Cost summary and caps

| phase | local | cloud alternative |
|---|---:|---:|
| G0–G7 | 4–7 € electricity, 3–5 nights | 16 € (L4) … 30 € (H100) |
| G8 (9B contract test, 100k) | 0 €, 1 night | ~11 € (L4) |
| teacher pass 2M (only after G7/G8) | — | **15 € (L40S)** / 17 € (H100) |

Caps: local phase ≤ 5 nights; a cloud step requires explicit approval per
gate; no GPU is left running without a `destroy` step in the same command
chain.

---

## 7. Open decisions

1. Ship criterion for G7: strict CI (>0) or ppl-improvement with
   non-inferiority? **Recommendation: strict CI on Glide, because that is the
   metric the product ships on.**
2. G2 budget: two 30k runs, or one 30k run plus resume from the shipped 85k
   checkpoint? Resuming mixes curricula; **recommendation: two fresh runs.**
3. Whether G6 may extend to 120k if the curve is still falling at 90k
   (+25 h).
4. Whether the L40S decision from the previous session ("no L40S") is lifted
   for the teacher pass only — the numbers above say it is the cheaper option.
5. Whether G8 (9B contract test) runs before any H100 booking; the plan says
   yes, because it is the cheap falsification of the re-pass hypothesis.
