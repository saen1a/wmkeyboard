# Student-quality audit — data, pipeline, harness, levers

Session: 2026-11-01, main repo `G:\C0ding\git\wmkeyboard-wmlm` (WSL `/mnt/g/C0ding/git/wmkeyboard-wmlm`).
Mode: read-only audit + fixed-copy verification + five 3k diagnostics and one inference sweep.
No mutating git command, no cloud/scw/Docker, no teacher pass; one trainer at a time (wrapper `flock`).

Scope: `tools/wmlm/{prep,slice_data,distill,soft_mask,train,model,export,paired_eval}.py`,
the teacher scripts under `wmk-glide/cloud/scaleway/`, `native/wm-engine/examples/{typing_eval,glide_lm_blend_eval}.rs`,
`native/wm-engine/src/predict.rs`, `wmk-glide/cloud/local/run_gate.sh`, and all artifacts under
`wmk-glide/artifacts/{out,data,corpora}` used by G0–G3.

Orchestration note: the live-research subagent completed. The three `general` subagents for
data/pipeline/harness were stopped by a subagent credit limit before doing work; their task IDs are
recoverable (`ses_e6948afb3ffe29kQIAvfs6lLL9`, `ses_e6948afacffet6SHvK45jFfP1L`,
`ses_e6948afaaffePDL4W0CjpYpkGF`). The findings below were produced directly by the main agent,
with real-data checks and fixed-copy verification.

## 0. Executive summary

1. **The strongest measured lever was blocked by the gate chain.** `distill_alpha=0.3` on the V9-aligned
   G2 winner, **without** the Piece mask, reaches heldout **4.9792** at 3k, versus **5.0304** (G1 V9
   reference) and **5.0402** (G3 V2). That is **−0.0512 nats** vs the reference and **−0.0610** vs V2,
   about 3.6× the 0.014-nat SE. The original G5 screen was gated behind G4, which was gated behind a
   G3 promotion; G3 promoted nothing, so the alpha lever was never tested. It now should be.
2. **V8 was not a test: it was a code no-op.** `soft_mask.py fill` tested `probs[a : a + topk].sum()`
   (a 24-row window) instead of `probs[a].sum()` (one row). All 100,000 slice sentences have an empty
   row 0, but fill reported 0. `soft_filled.npz` is array-identical to `soft.npz` (verified).
   After the one-line fix, fill fills 99,999/100,000; the fixed 3k screen is **5.0335** (no promotion).
3. **The student/core algorithm is mostly sound, but the KD/CE mix was too KD-heavy.** More teacher
   batches hurt: `distill_share=1.0` gives **5.0610** (+0.0208 vs V2). Less KD helps: alpha 0.3 gives
   −0.0512. The mask/weight/fill/tail/`<unk>` experiments do not move heldout at 3k.
4. **G2's gate loss is not the exported checkpoint's loss.** `DONE` recorded the final eval
   (4.3087 / 4.1711), but `best.pt` is step 28,500 (4.3023 / 4.1686) and `export.py` uses `best.pt`.
   The G2 Δ on the exported models is −0.1337, not −0.1376; both pass, but the evidence must name the
   checkpoint. The hardened wrapper now records both.
5. **Typing evaluation is biased.** `typing_eval.rs` skips words whose bytes are not ASCII lowercase:
   **8.68%** of heldout word tokens (umlauts/ß) are never scored. It also uses QWERTY keys and
   `primary_language="en"`, and its default `SEEDS` path resolves outside the repo when run from the
   repo root, so the base next-word metric is exactly 0. `lm_nextword_top1` is usable as a relative
   metric only. German bigram seeds changed it by 0.0 pp in a 200-case check.
6. **`paired_eval.py` has an asymmetric `-1` bug.** It drops `-1` rows per file, then requires identical
   item-id sets; a `-1` in A and a computed value in B makes the pair fail (verified rc=2). A fixed copy
   (keep rows, align, then drop pairs) returns n=2, dropped=1, rc=0. Current G0 dumps contain no `-1`,
   so G0 is unaffected; any future mode-specific metric pair is not.
7. **Inference knobs are not a top-1 lever.** On a 2-fold Glide split, `RESULTS=16` gives **top-4
   +0.25…+0.31 pp**, top-1 +0.00…+0.08 pp; `RESULTS=32` is identical to 16; `WEIGHT=0.5`/`CAP=5` are
   already best. Use 16 only if top-4/latency trade-off is acceptable.
8. **Licence/provenance risk.** The 2M mix contains **301,703 OpenSubtitles rows (15.1%)** under
   CC BY-NC-style terms; the manifest itself says "check before shipping a derived model". The 2M
   soft file is also a **PARTIAL** merge (1,979,982 of 1,980,000 sentences; 18 missing; `.PARTIAL`, no
   `.DONE`). Both must be recorded in any ship decision.

## 1. Verified facts (real data)

| Fact | Value |
|---|---|
| `de_lm_2m/train.npz` | 1,980,000 sentences, 40,556,654 tokens |
| `de_lm_2m/heldout.npz` | 20,000 sentences, 409,207 tokens |
| `de_lm_2m_slice100k/train.npz` | 100,000 sentences, 2,043,890 tokens |
| slice `soft.npz` | 100,000 sentences, 1,076,068 rows, top-24, ids 0..22527 |
| slice row-0 empty | **100,000 / 100,000** |
| slice all empty rows | **101,224** (row 0 + 1,224 offset misses) |
| slice non-empty prob sum | mean 0.9999968, min 0.99951 |
| `masks.masks.json` | empty 101,224; piece 163,373; le3 24,833; rows 1,076,068 |
| `keep.kd` zeros | 163,373 (Piece rows) |
| `keep.kdce` | `kd` and `ce` are **array-identical**; CE gate adds nothing |
| `soft_filled.npz` | `ids` and `probs` **array-identical** to `soft.npz`; 100,000 row-0 empty |
| slices vs full soft | 10/10 sampled sentence blocks bit-identical; `sentences` remapped 0..99,999 |
| `de_soft_2m.npz` | 1,979,982 sentences, 21,378,590 rows, top-24, max id 22,527 |
| 2M teacher mapping | 22,512 / 24,576 student words mapped (`multi=1`); 2,064 = 16 specials + 2,048 pieces |
| 2M teacher log | 18 permanent failures; **729 accepted with high NLL**; mass 90.6% |
| `.PARTIAL` | `sentences: 1979982 of 1980000`, 396 shards, 18 incomplete |
| `de_swipes.jsonl` | **2,594 lines**, harness `n=2,588` (6 invalid/filtered) |
| Heldout typing words | 20,000 lines, 223,725 word tokens; 89.23% ASCII-eligible; **8.68% non-ASCII skipped** |
| Seeds path | repo-root default `../../app/...` = **missing**; `native/wm-engine` cwd = exists; no `de_bigrams.txt` asset |
| Eval cap | `train.py evaluate` scores 8,000 of 20,000 heldout sentences |
| G2 final vs best | final 4.3087/4.1711; **best 4.3023/4.1686 at step 28,500**; export uses `best.pt` |

## 2. Findings

Severity is impact on decision quality or correctness, not effort.

### High

**H1 — `soft_mask.py fill` checks a 24-row window.** `tools/wmlm/soft_mask.py:522`.
`if probs[a : a + topk].sum() != 0: continue` should be `if probs[a].sum() != 0: continue`.
Because row 1 of every sentence is non-empty, the sum of rows `a..a+23` is never zero;
V8 was silently a no-op and `soft_filled.npz` equals `soft.npz`. Verified: 100,000/100,000 row-0
empty; window test 0/10,000; fixed copy fills 99,999/100,000 (the last sentence is skipped by
`a + topk > rows`), non-row-0 arrays unchanged. Fixed-copy V8 screen: **5.0335** vs 5.0304 reference
(+0.0031) and 5.0402 V2 (−0.0067): the bug was real, the lever is not.
Status: verified patch on a copy; **not applied** (protected file).

**H2 — `paired_eval.py` asymmetric `-1` drop.** `tools/wmlm/paired_eval.py:118-124` and `align` at 137.
`read_tsv` removes `-1` rows from each file independently; `align` then requires equal id sets.
A metric computed in B but `-1` in A fails with `item_id sets differ`. Verified synthetic A
`[1,-1,1]` vs B `[1,1,1]` → rc=2. Fixed copy keeps the rows, aligns, then drops pairs where either
value is `-1`: n=2, dropped=1, rc=0. The `dropped=max(a,b)` line also under-reports; use the pair count.
Current G0 dumps have no `-1`, so G0/G2 are unaffected; future typing mode pairs are.
Status: verified patch on a copy; **not applied**.

**H3 — Alpha 0.3 is a real lever, and the gate chain blocked it.** 3k diagnostics on the same
`slice100k` / V9 alignment / seed 0 / batch 256:

| run | flags | heldout | Δ vs ref 5.0304 | Δ vs V2 5.0402 |
|---|---|---:|---:|---:|
| G1 V9 | align, alpha .5 | 5.0304 | 0 | −0.0098 |
| G3 V2 | align + keep.kd | 5.0402 | +0.0098 | 0 |
| **alpha03** | align + keep.kd + **alpha .3** | **4.9821** | **−0.0483** | **−0.0581** |
| **alpha03_nomask** | align + **alpha .3** | **4.9792** | **−0.0512** | **−0.0610** |
| share1 | align + keep.kd + **share 1.0** | 5.0610 | +0.0306 | +0.0208 |
| tail0938 | align + keep.kd + constant `<unk>` tail | 5.0551 | +0.0247 | +0.0149 |
| v8fix | align + keep.kd + fixed fill | 5.0335 | +0.0031 | −0.0067 |
| V3 | align + keep.kd + weight | 5.0283 | −0.0021 | −0.0119 |

The no-mask alpha 0.3 is the best 3k result and needs fewer moving parts than V2/V3. The mask/weight
add nothing; the fill adds nothing; more KD and a constant tail hurt. The G5 plan already proposed
alpha 0.3 but was gated on G4; G4 was gated on a G3 promotion; G3 promoted nothing. The correct
re-plan is a **G5′ confirm at 30k** on the alpha 0.3 recipe, with Glide non-inferiority (see §6).

**H4 — G2 gate loss vs exported checkpoint.** `train.py:443-450` saves `last.pt` every eval and
`best.pt` on the minimum; `run_gate.sh:31` recorded only the final eval; `export.py` uses `best.pt`.
For G2: final 4.3087/4.1711, best **4.3023/4.1686 at step 28,500**. The exported candidates are the
best checkpoints; the G2 Glide non-inferiority was measured on them. The gate Δ should state the
checkpoint: Δ(best) = −0.1337, Δ(final) = −0.1376. Both pass. The hardened wrapper now writes
`best_heldout_loss` and `best_step`; the old G2 `DONE` lacks them.

**H5 — Typing evaluation is not the product distribution.** `native/wm-engine/examples/typing_eval.rs:274`
skips every word whose bytes are not ASCII lowercase; 8.68% of heldout word tokens (umlauts/ß) are
never scored. The harness uses QWERTY keys (`qwerty_keys`, line 50) and `english_sources=true` /
`primary_language="en"` (lines 240-242), not the German QWERTZ layout. Its default `SEEDS` is
`../../app/.../en_bigrams.txt`; from the repo root that path is missing, so the base next-word metric is
exactly 0. A German bigram file built from the train data (150k pairs) changed `lm_nextword_top1` by
**0.0 pp** in a 200-case check (0.1835 → 0.1835), so the missing seeds are not a lever for the LM
metric; the ASCII/umlaut bias and the QWERTY/DE mismatch remain. Use the typing metric as relative
only; Glide top1 is the product metric.

### Medium

**M1 — `keep.kdce` is a duplicate of `keep.kd`.** `soft_mask.py:415-418` writes the same
`(flags & PIECE) == 0` array for both `kd` and `ce`. There is no independent CE gate; the planned
`keep.kdce` variant cannot test CE masking. The real CE/KD denominator mismatch remains: CE is averaged
over all non-PAD positions, KD over filled rows only. A genuine CE gate/denominator alignment is a
code change, not a data flag.

**M2 — G3 screens are underpowered and too early.** The 3k SE is ~0.014; the promotion bar is −0.02
(≈1.4 SE). V3 is −0.0021, V8-fix +0.0031, tail +0.0149, share1 +0.0208: none is promotion-level, but
the screen cannot exclude a small slow-burn effect that would appear at 30k/full data. The gate design
treats a 3k miss as a retirement and blocks G4. If a repair lever matters, confirm it at 30k under a
new pre-registered gate; do not re-run the same 3k with a new threshold.

**M3 — Glide decode sweep: top-4 only.** 2-fold split of the 2,588 valid swipes (A: n=1,285,
B: n=1,303; candidate G2 V9):

| setting | A top1 | B top1 | A top4 | B top4 |
|---|---:|---:|---:|---:|
| R=8, w=.5, c=5 (baseline) | .7907 | .7820 | .8506 | .8480 |
| R=16, w=.5, c=5 | .7907 | .7828 | **.8529** | **.8511** |
| R=32, w=.5, c=5 | .7907 | .7828 | .8529 | .8511 |
| R=16, w=.25 | .7829 | .7820 | .8537 | .8511 |
| R=16, w=.75 | .7821 | .7759 | .8506 | .8496 |
| R=16, w=1.0 | .7689 | .7690 | .8482 | .8496 |
| R=16, w=.5, c=2 | .7821 | .7759 | .8529 | .8526 |
| R=16, w=.5, c=10 | .7914 | .7820 | .8529 | .8511 |
| shipped 2M R=8 | .7883 | .7813 | .8514 | .8457 |
| shipped 2M R=16 | .7883 | .7813 | .8537 | .8496 |

R=16 buys ~0.25–0.31 pp top-4 for ~2× decode cost; R=32 adds nothing; the LM weight 0.5 and cap 5 are
already optimal. This is a product/latency decision, not a top-1 training lever.

**M4 — 2M soft file is PARTIAL and high-NLL.** 18 of 1,980,000 sentences are missing
(1,979,982 present; `.PARTIAL`; no `.DONE`); 729 sentences were accepted with mean NLL > 12. The missing
18 are 0.0009% and negligible; the high-NLL rows are 0.037% and are not marked in the soft file.
A high-NLL mask is possible from the shard logs, but the expected effect is tiny. The wrapper now warns
on `.PARTIAL`.

**M5 — `distill.py` and `distill_vllm.py` disagree.** `tools/wmlm/distill.py` maps only single-token
teacher words; the production vLLM path uses `multi=1` (multi-token product), which is what produced
`de_soft_2m.npz` (22,512/24,576 words mapped). Reproducing the artifact with `distill.py` would give
different targets. The plan's G8 "new target contract" is ambiguous: the vLLM path already has
word-space multi-token mapping; the current soft file still has **row 0 zeros** (no BOS target),
top-24 **renormalized** (9.4% tail discarded), and no `<unk>`/OTHER bucket. The true tail/BOS contract
needs a new teacher pass (G8), not `distill.py` alone.

**M6 — Typing `SEEDS`/German asset gap.** The repo has only `app/src/main/assets/dictionaries/en_bigrams.txt`;
no German seeds. The default path is cwd-dependent and wrong from the repo root. German seeds built from
the train data did not change `lm_nextword_top1`; the base metric remains invalid. This is an evaluation
hygiene issue, not a training lever.

**M7 — `de_swipes.jsonl` has 2,594 lines, the harness evaluates 2,588.** Six lines are dropped by the
`Record` parser (`map_while(Result::ok)`) without a count or warning. The plan's 2,588 is the evaluated
count; the 6 dropped records are undocumented. Add a filter count/warning.

**M8 — `moved` in the Glide summary is not "top-1 changed".** `glide_lm_blend_eval.rs:119-121` increments
`moved` when any candidate score shifts; `with prev 2294 moved 2294` means every contextual record had at
least one score shift, not that top-1 changed. The `blend_top1`/`blend_top4` metrics are correct; the
diagnostic label is misleading.

**M9 — Eval uses 8,000 of 20,000 heldout sentences.** `train.py:239` caps at `min(data.n, 8000)`.
The SE is ~0.014; all 20k would be ~0.0089 at 2.5× eval cost. For the 30k alpha confirm and G6, a 20k
eval is a cheap precision gain (code change in `evaluate`/a flag).

**M10 — Resume/extend LR semantics.** `resume` reconstructs the scheduler with the **new** `steps` and
replays it to the saved step. Resuming an interrupted 30k run as 30k is fine; resuming a finished 30k run
as 60k jumps the LR to the 60k schedule at step 30k (~0.5e-3 instead of 0). G6 should be fresh runs, not
extensions, unless a warm restart is intended and labeled.

**M11 — `de_soft_1m2.npz` is also PARTIAL** (1,199,989 sentences; `.PARTIAL`/`.BACKUP_OK`). The 1.2M
baseline model and the G0 2M-vs-1.2M comparison inherit this; 11 missing sentences are negligible, but
the artifact should be labeled.

**M12 — Export artifacts lack sha256.** `export.py` writes the `.wmlm` but no `.sha256`; the G2 candidates
have no sidecar. Add one for provenance; `DONE` has the checkpoint sha, not the exported file.

### Low

**L1 — `export.py` quantizes per output row** (int8, one f32 scale/row); no bug found; the shipped reader
matches. The candidate and shipped sizes are ~10.85MB; d288 is 12.8MB.

**L2 — `model.py`/`train.py` core is consistent**: pre-norm blocks, causal SDPA, tied embeddings, learned
positions, `tgt[:, :3] = PAD`, PAD ignore, clip 1.0, AdamW, cosine/warm 500. No correctness bug found in
the forward/loss/optimizer path.

**L3 — `run_gate.sh` was hardened (applied)**: step-mismatch guard, `.PARTIAL` warning, `flock`
one-trainer, `flags.json`, `device cuda` guard, `best_heldout_loss`/`best_step` in `DONE` and ledger.
The old G2 `DONE` predates these fields.

**L4 — `prep.py`/`de_2m_mix` dedup**: exact dedup by `common.tokenize` key with a global seen-set and a
pre-seeded heldout (manifest: 18,063 heldout drops from `de_all`, 558,441 from OpenSubtitles; 21.5M
duplicates). Exact overlap is handled; document-level near-duplicates are not, and the final heldout is
a random 20k from the deduped mix. Low risk.

## 3. Fixes: applied vs proposed

| Item | Status |
|---|---|
| `run_gate.sh`: step guard, `.PARTIAL` warning, `flock`, `flags.json`, cuda guard, best fields | **applied** (non-protected) |
| `soft_mask.py` fill: `probs[a].sum()` | verified on a copy; **proposed**, protected |
| `paired_eval.py`: keep `-1` rows, align, drop pairs, pair-count `dropped` | verified on a copy; **proposed**, protected |
| `typing_eval.rs`: ASCII/umlaut filter, QWERTY vs German layout, `primary_language`, `SEEDS` | **proposed**, native protected |
| `soft_mask.py`: real `keep.kdce` CE gate / CE-KD denominator alignment | **proposed**, protected |
| `train.py`: 20k eval option, `flags.json` (now wrapper), best fields (now wrapper) | **proposed** / wrapper-applied |
| `export.py`: `.wmlm.sha256` sidecar | **proposed** |
| `glide_lm_blend_eval.rs`: count/warn the 6 dropped records; rename `moved` | **proposed**, native protected |
| `de_swipes` 6 dropped records documented | **recorded** |

## 4. Live research (subagent, verified sources)

The highest-value literature signals for this 10M-param German student:

- **Tail-aware KD**: split KL into top-K and tail; renormalizing top-K silently asserts the tail is zero;
  a residual/OTHER bucket or beta-weighted tail is the standard fix. Gains in 0.5B–2B students, best
  K≈5–10; no material gain beyond K≈10. https://arxiv.org/abs/2602.20816 (2026); MaxText
  `kd_use_other_bucket` implementation https://github.com/zlab-princeton/llm-distillation-jax.
  Our constant `<unk>` tail was negative at 3k; the true per-row tail needs the teacher's tail ids/probs,
  which the current file does not store (G8).
- **KD/CE mix**: linear alpha blend; default 0.5. No strong public effect size at 10M; our 3k evidence says
  **alpha 0.3 > 0.5 > share 1.0** for this data. Temperature matters more for forward KL; a small
  temperature sweep (1.0/1.5/2.0) is a cheap follow-up. https://aclanthology.org/2026.emnlp-main.1191/.
- **Alignment**: cross-tokenizer alignment is essential; naive distribution matching is ineffective.
  Our V9 word-aware alignment is consistent with the literature and is the largest pre-audit gain.
  https://aclanthology.org/2025.findings-acl.419/.
- **Data**: dedup removes memorization/test leakage; 4 epochs of repeated data is near-equivalent to
  unique data, after which added compute decays. Our 30k×256×40 is already several epochs over ~36M
  unique words; 120k is repetition. https://arxiv.org/abs/2107.06499, https://arxiv.org/abs/2305.16264.
- **Swipe reranking**: FUTO's 2026 system uses a ~1.5M-param ContextLM purely to rerank candidates with a
  wide beam; our Glide sweep says the current weight/cap are already near-optimal and a wider beam buys
  top-4 only. https://swipe.futo.tech/, https://arxiv.org/abs/2606.25247.
- **Averaging/EMA**: small, low-risk; checkpoint averaging helps mainly across independently fine-tuned
  models; within-run EMA is the relevant variant. https://arxiv.org/abs/2203.05482.

## 5. Levers ranked

| Rank | Lever | Expected | Cost | Risk |
|---|---|---|---|---|
| 1 | **alpha 0.3 on V9, no mask** (G5′) | heldout −0.051 at 3k; 30k confirm needed | 6.6h + Glide | heldout→Glide gap; must measure Glide |
| 2 | **Step budget on the alpha recipe** (60k, then 90k if ≥0.01) | small; curve still falling at 30k | 13.2h / 19.8h | repetition plateau; 120k exceeds 72h |
| 3 | **Top-k truncation K≈10** (renormalized) | unknown; research says K=5–10 best for 0.5–2B | 40 min 3k | true word outside top-10; needs Glide |
| 4 | **True tail mass / BOS** (new teacher contract) | potentially the largest data gain | new teacher pass (G8; cloud/teacher forbidden here) | 15€ L40S; contract work |
| 5 | **Capacity d=288/320** (`de_context_d288.wmlm` exists, 12.8MB) | unknown; 18–50% more params | 8–10h 30k | product size/latency; not a data fix |
| 6 | **Glide `RESULTS=16`** | top-4 +0.25–0.31 pp; top-1 flat | inference only | latency; top-1 ship rule unaffected |
| 7 | **20k heldout eval** | SE 0.014 → 0.009 | near-zero | code change |
| 8 | **High-NLL filter (729 rows)** | tiny | data mask | 0.037% of rows |
| 9 | **Clean 2M mix without OpenSubtitles** | licence fix; data may shift | new corpus + teacher pass | 15.1% of the mix; legal blocker |
| 10 | **EMA / last-k averaging** | small (<0.05 nats) | wrapper snapshots + script | none material |
| 11 | **alpha 0.3 + share 0.25/0.75** | unknown; share 1.0 hurt | 40 min × 2 | over/under-KD |
| 12 | **`ctx` 64 / dropout / weight decay** | unproven | 40 min | capacity/latency |

Do not bother: `distill_share=1.0` (negative), constant `<unk>` tail (negative), V8 fill (no effect),
Piece mask/weight (no effect at 3k), Glide weight/cap sweep (already optimal), German bigram seeds
(no LM-metric change), `keep.kdce` as currently written (duplicate), 120k on the same 2M (repetition).
Uniform label smoothing is contraindicated for distillation (Müller 2019).

## 6. Recommended next gate (re-plan)

The original G4→G5→G6 chain is blocked because G3 promoted nothing. The audit gives a concrete,
pre-registered replacement:

**G5′ — alpha 0.3 confirm.**
- Entry: G2 passed; V9 word-aware alignment; `distill=$ART/de_soft_2m.npz`,
  `distill_align=$ART/de_soft_2m.masks.align.npz`, `distill_alpha=0.3`, `distill_share=0.5`,
  no mask/weight; 30k steps on `de_lm_2m`, batch 256, ctx 40, d 256, L6, H4, ff768, seed 0.
- Exit: heldout Δ ≤ −0.02 vs the G2 winner (best checkpoint 4.1686) **and** Glide `blend_top1`
  paired non-inferiority vs the G2 candidate (CI lower ≥ −0.5 pp). Add the paired Glide test to the
  alpha confirm; heldout alone is not the ship metric.
- Cost: ~6.6h + export/Glide; budget after the audit: 19.17h used, 52.83h left.
- If it passes: this is the final recipe for **G6′** (60k, then 90k if ≥0.01; stop at 120k because
  19.17 + 6.6 + 13.2 + 19.8 + 26.4 > 72h). Then G7 export + paired Glide vs 2M/150k with Holm.
- If it fails (heldout gain but Glide CI < −0.5 pp, or no heldout gain at 30k): keep the G2 winner,
  document the negative, and go to G6′ on alpha 0.5; do not re-run alpha with a new threshold.

Open decisions: (a) apply the fill/paired patches now (protected-file approval), (b) run G5′ before G6,
(c) decide the OpenSubtitles licence, (d) decide whether top-4 +0.3 pp is worth the R=16 latency,
(e) whether to spend the remaining budget on K=10/capacity or go straight to the step sweep.

## 7. Budget and artifacts

- GPU used: 15.85h (gates) + 5 × ~0.66h (AUDIT v8fix/tail/share1/alpha03/alpha03_nomask) = **19.17h / 72h**.
- Diagnostics: `artifacts/out/runs/AUDIT/{v8fix,tail,share1,alpha03,alpha03_nomask}/{run.log,DONE,flags.json}`.
- Fixed-copy artifacts: `artifacts/out/de_lm_2m_slice100k/soft_filled_fixed.npz`,
  `soft_tail0938.npz`; the original `soft_filled.npz` remains the no-op artifact.
- Evidence: `plans/gate-log.md` (append-only), `plans/gate-report.md`, this file.
- No gate state was changed by the audit; G0/G1/G2 passed, G3 failed, G4–G7 blocked. The audit recommends
  the G5′ re-plan above.

## 8. Post-audit update — G5′ measured and passed (2026-11-01)

The audit's G5′ recommendation was executed immediately.

- Run: `G5P/alpha03`, 30,000 steps, full `de_lm_2m`, `distill=de_soft_2m.npz`,
  `distill_align=de_soft_2m.masks.align.npz`, `distill_alpha=0.3`, no mask/weight, batch 256,
  ctx 40, d 256, L6, H4, ff768, seed 0. Resumed=0; wall 6.62h.
- Heldout: best **4.1177** at step 28,500; final 4.1183. G2 winner best 4.1686 → **−0.0509 nats**
  (final-eval Δ −0.0528). The 3k alpha effect persisted at 30k.
- Glide (2,588): **0.7871** vs G2-V9 0.7863 → **+0.08 pp**, CI [−0.43, +0.58], p=0.8804;
  non-inferiority passes (CI lower ≥ −0.5 pp). vs shipped 2M 0.7848 → +0.23 pp,
  CI [−0.31, +0.77], p=0.4709; non-inferior but **not ship** under the strict CI rule.
- Candidate: `artifacts/models/de_candidate_g5p_alpha03.wmlm`; evidence
  `eval_dumps/paired_g5p_vs_g2.json`, `paired_g5p_vs_2m.json`.
- Budget after G5′: **25.78 / 72 GPU-h** (46.22 left). Next: **G6′ 60k** on the alpha-0.3 recipe;
  90k only if 60k beats 30k by ≥0.01; 120k would exceed the 72h cap.
- The recipe is now V9 word-aware alignment + `distill_alpha=0.3` + `distill_share=0.5`, no Piece mask,
  no weight, no fill. The Piece mask/weight and the fill are retired for heldout at this scale; the
  constant `<unk>` tail and `share=1.0` are negative.

### G6′ 60k (2026-11-02)

- Run `G6P/60k`, same alpha-0.3 recipe, 60k steps, wall 13.29h, resumed=0.
- Heldout: best **4.0468** at step 57,500 (final 4.0481); vs 30k best 4.1177 → **−0.0709 nats**.
- The 60k leg beats the 30k by ≥0.01, so 90k is required; 120k is excluded by the 72 GPU-h cap
  (39.07 + 19.8 + 26.4 > 72).
- Budget after 60k: **39.07 / 72 GPU-h** (32.93 left). Next: G6′ 90k, then G7 export/Glide.
