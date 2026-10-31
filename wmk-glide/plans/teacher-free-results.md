# Teacher-free results — what was measured, what it means

Stage: **finalize**. Companion to `teacher-free-plan.md` (plan) and
`audit-findings.json` (audit round 1). All work local: no cloud spend, no
teacher re-pass, no commit, no push.

Branch `wmlm-de-research`, worktree `G:\C0ding\git\wmkeyboard-wmlm`.
Verification date 2026-10-31.

---

## 1. Status in one paragraph

The plan and its supporting artefacts exist and run. Building the masks
exposed a **structural defect in how the existing soft targets are fed to the
loss**: soft rows are per *word*, but `train.py` placed them per *token*, so
**54.4 % of KD targets were applied at the wrong position** in the shipped
2M model. That is now measurable, reproducible, and fixed behind an opt-in
flag (`distill_align=`), with the default path proven bit-identical. The new
item dump + `paired_eval.py` produced the project's first **paired** German
numbers, and the DirectML crash was not only reproduced but worked around
(`distill_impl=index`), with a full 2 000-step DirectML run.

---

## 2. The finding that changes the plan: row/token misalignment

**What is true.** `distill.py` writes one soft row per **word**
(`distill.py:95-106` merges continuation pieces back into words, `ends` is
per word). `train.py` places row `r` at logits position `3+r`
(`train.py:69-74`) — a **token** offset. Once a word is spelled in pieces,
token and word indices diverge for the rest of the sentence.

**Measured** (3000 sentences of `de_soft_2m.npz`, script in the transcript):

| quantity | value |
|---|---:|
| word-group count == soft row count | 3000 / 3000 sentences |
| rows whose naive target (`4+r`) differs from the word-aware target | **54.4 %** |
| sentences with at least one such row | **72.1 %** |
| PIECE share with the naive mapping | 34.1 % |
| PIECE share with the word-aware mapping | **15.3 %** (matches `audit_signal.json:11`) |
| whole-word top-24 recall, word-aware, filled rows | 96.3 % (matches `0.9643`) |

The naive mapping is therefore not a rounding detail: it simultaneously
corrupts the KD target and any per-row mask for more than half of all rows.
It also explains why the prompt's own audit numbers (15.3 % piece targets,
96.4 % recall) could not be reproduced from the formula the prompt implies.

**Fix.** `soft_mask.py build --emit-align` writes `pos[r]` = the
sentence-relative logits position that predicts word `r` (first token of the
word minus one); `train.py distill_align=<file>` scatters each row there. The
default (no `distill_align=`) keeps the historic `3+r` path and is proven
bit-identical against `git show HEAD:tools/wmlm/train.py` (two seeds, with
and without `distill=`) by `test_train_mask.BitEquality`.

**Consequence for the variant matrix.** The alignment fix (V9) is now the
first thing to measure, because V2/V3/V8 are meaningless while the rows they
mask are placed at the wrong position. V9 is a one-line CLI change on top of
the new artefacts.

---

## 3. First paired results (item dumps + McNemar + bootstrap)

New capability: both harnesses write per-item dumps (`ITEMS=`), and
`tools/wmlm/paired_eval.py` does the paired statistics. Dumps were produced
with the released harness settings (`RESULTS=8 COLS=11 THREADS=8 FREQ=0.5
GAP=2.0 WEIGHT=0.5 CAP=5`, compounds list) on 2 588 FUTO swipes, and with
`CASES=500 SCATTER=fast MODES=base,lm SAVINGS=0 LMBLEND=0.5 LMBCAP=5.0` on
500 typing cases.

**Reproduction check:** the 2M model reproduces the published harness numbers
exactly — `blend top1 0.7848 top4 0.8485`, raw `0.7570 / 0.8427`, `with prev
2294 moved 2294`. Runtime 35 s.

| comparison | metric | n | delta (A−B) | b / c | p_disc | McNemar exact | bootstrap 95 % CI |
|---|---|---:|---:|---:|---:|---:|---|
| 2M vs 1.2M | glide blend_top1 | 2588 | **+0.54 pp** | 27 / 13 | 1.6 % | **0.038** | **[+0.08, +1.00] pp** |
| 2M vs 150k | glide blend_top1 | 2588 | +0.00 pp | 29 / 29 | 2.2 % | 1.000 | [−0.58, +0.58] pp |
| 2M vs 150k | typing lm_nextword_top1 | 500 | −0.80 pp | 14 / 18 | 6.4 % | 0.597 | [−3.00, +1.40] pp |

Readings:

1. **2M beat 1.2M by 0.54 pp with a paired CI that excludes zero.** This is
   the first German claim in this project that survives a paired test; the
   marginal half-width (~1.6 pp) would have hidden it. It is consistent with
   the prompt's own diagnosis that 1.2M was undertrained.
2. **2M and 150k are indistinguishable on the swipe set** (b = c = 29,
   p = 1.0). The earlier "78.48 vs 77.40" readings are within noise; the
   difference in the 150k-vs-2M column of the prompt was not a real effect.
3. The typing set cannot resolve anything below ~4 pp (MDE at p_disc 10 %,
   n = 500: 3.95 pp). The −0.8 pp result is not evidence of a regression.
4. `paired_eval.py --mde 2588` reproduces the plan's table exactly
   (1.23 / 1.74 / 2.46 / 3.01 pp for p_disc 5/10/20/30 %).

**Known definitional gap (must be fixed before the next claims).** The
typing dump writes `0` for cases without a previous word, while the console
summary excludes them: dump `lm_nextword_top1 = 15.0 %` vs summary
`17.18 %` on the same run (75/436 = 17.2 %, so 64 of 500 cases are
context-less). Paired *comparisons* are unaffected (same convention on both
sides), but absolute dump values must not be quoted. Fix: have
`typing_eval.rs` write `-1` for context-less cases; `paired_eval.py` already
drops `-1`.

---

## 4. Artefacts produced

All under `wmk-glide/artifacts/out/` (git-ignored); every file has a
`.sha256` and the masks have a `masks.json` with counts and a stable hash.

| file | bytes | content |
|---|---:|---|
| `de_soft_2m.masks.masks.npz` | 152 033 063 | flags/weight/target/pos for 21 378 590 rows, sha256 `2202ebab…` |
| `de_soft_2m.masks.align.npz` | 87 896 807 | `pos` uint8 + `target` int16, sha256 `d32b0cdd…` |
| `de_soft_2m.masks.keep.kd.npz` | 21 378 848 | `kd` = 1 where not PIECE |
| `de_soft_2m.masks.keep.kdce.npz` | 42 757 674 | `kd` + `ce` |
| `de_soft_1m2.masks.*` | 92 MB / 53 MB / 13 MB / 26 MB | same for 12 956 013 rows |
| `de_lm_2m_slice10k/` | 4.2 MB | 10 009 train rows / 490 sentences / 5 291 soft rows |
| `de_lm_2m_slice100k/` | 130 MB | 100 000 sentences / 2 043 890 train rows / 1 076 068 soft rows |
| `eval_dumps/glide_{2m,1m2,150k}.tsv` | 32 KB each | 2 588 rows + header |
| `eval_dumps/typing_{2m,150k}.tsv` | 20 KB each | 500 rows + header |

Flag shares, recomputed on the full 2M file (not copied from the prompt):

| flag | count | share | prompt/`audit_signal` |
|---|---:|---:|---|
| EMPTY | 2 004 299 | **9.375 %** | 9.38 % |
| PIECE | 3 242 201 | **15.166 %** | 15.3 % |
| LE3 | 491 321 | **2.298 %** | 2.54 % |
| rows | 21 378 590 | — | — |

LE3 differs from `audit_signal.json` because that file's cut is not stated;
the recomputed definition (`0 < count(probs>0) <= 3` over all rows) is in
`soft_mask.py` and in the plan.

Weight quantiles (candidate-count proxy, `--weight cand`): 4.2 % / 54.2 % /
75.0 % / 92.0 % / 100 % at 0/25/50/75/100 %.

---

## 5. Backend results on the RX 9060 XT

| E | What | Result |
|---|---|---|
| E1 | GPU precondition | `torch.cuda.is_available() == True`, `AMD Radeon RX 9060 XT`, ROCm 7.2.1 + torch 2.9.1, WSL Ubuntu 24.04 |
| E2 | ROCm, 2 000 steps, batch 256, slice10k, mask+align+weight | **1.03 steps/s** (1 948 s), loss 8.560 → 1.206, no NaN — see §6 |
| E3 | DirectML gather backward | **crash reproduced**: `DirectML scatter doesn't allow partially modified dimensions. Please update the dimension so that the indices and input only differ in the provided dimension.` (torch 2.4.1+cpu, torch-directml 0.2.5.dev240914) |
| E4 | DirectML alternatives | `gather` FAIL, `onehot` FAIL (`aten::eye` unsupported → CPU fallback → error), **`flat_index` PASS**, **`take_along_dim` PASS** |
| E5 | DirectML full run, `distill_impl=index`, 2 000 steps batch 64 | **1.04 steps/s** (1 926 s), loss 8.626 → 1.143, **identical to the CPU curve at every printed step** — see §6 |
| E6 | CPU `torch 2.14.1+cpu`, 2 000 steps batch 64 | **0.66 steps/s** (3 028 s), loss 8.626 → 1.143 — see §6 |
| — | Docker `rocm/pytorch` | not attempted: Docker is not installed in either WSL distro, and the working host stack already covers the requirement. Recorded as skipped, not as a claim. |
| — | ONNX Runtime DirectML training | not attempted; docs say the DML EP is inference-only and the training build has CPU/CUDA kernels only. |

This **contradicts the research note's expectation** that no DirectML
workaround exists ("`take_along_dim` compiles to the same gather/scatter pair
— no fix (likely)"). Measured: `take_along_dim` and flattened advanced
indexing both pass backward on DirectML 0.2.5.dev240914, and a real 2 000-step
distillation run completes. The lesson for the file: mark the research note's
workaround assessment as **refuted by measurement** (it was flagged
"likely"/"unverified" there, which is why it was testable).

Practical consequence: DirectML is now a usable *second* training backend on
this machine (no WSL/ROCm needed), about 1 step/s at batch 64 — good enough
for screens, not for full 90k runs.

---

## 6. Gate results (the mandatory 2 000-step runs)

All three ran with the full new stack: `distill=`, `distill_align=`,
`distill_mask=<keep.kd>`, `distill_weight=<masks>`, on
`de_lm_2m_slice10k` (490 sentences, 5 291 soft rows), seed 0, eval every 200.
They ran **concurrently on one machine**, so the throughput numbers are
lower bounds, not clean benchmarks.

| backend | batch | steps | wall | steps/s | loss step 100 → 2000 | heldout ppl (step 200 → 2000) | NaN/Inf |
|---|---:|---:|---:|---:|---|---|---|
| ROCm 7.2.1 / torch 2.9.1 (GPU) | 256 | 2000 | 1 948 s | **1.03** | 8.560 → **1.206** | 2011 → 26107 | none |
| torch-directml 0.2.5.dev240914, `impl=index` | 64 | 2000 | 1 926 s | **1.04** | 8.626 → **1.143** | 1935 → 17842 | none |
| torch 2.14.1+cpu | 64 | 2000 | 3 028 s | **0.66** | 8.626 → **1.143** | 1935 → 17480 | none |

Readings:

- **Gate 5 passes**: the training loss is finite and falls in all three runs
  (8.6 → 1.1–1.2). Heldout ppl *rises* because the model memorises 490
  sentences within ~12 epochs; that is expected on the slice and is why the
  plan's gate is the training loss (corrected during this session).
- **DirectML and CPU track each other**: the training-loss lines agree to
  three decimals at every printed step (8.626 / 6.498 / 4.718 / 1.143). Their
  heldout ppl at step 2000 differs by 2 % (17 480 vs 17 842) — float
  divergence, amplified by memorising the same 490 sentences. The indexing
  workaround is numerically sound, not just non-crashing.
- **DirectML is ~1.6× faster than the CPU at the same batch**, and its
  per-step cost equals ROCm's *at 4× the batch* — i.e. ROCm still carries
  ~4× the tokens/s. For screens, DirectML is usable without WSL; for full
  runs, ROCm stays the backend.
- The 1.03 steps/s GPU figure is below the earlier 1.32 steps/s single-run
  baseline because two other trainers shared the box. It says the mask/align
  path adds no crash and no order-of-magnitude cost; it does not establish the
  single-run throughput of the masked loss.

---

## 7. Audit

`plans/audit-findings.json`: 13 auditor findings + 2 found during
verification. Adjudication:

- **Fixed (10):** bitmask flag counts (masks.json was 2x/4x too large and
  every real build assert-failed); the plan's row→token formula and the
  resulting `distill_align` change; chi-square statistic reported as a
  p-value; `paired_eval.py` refusing the `-1` sentinels that `typing_eval.rs`
  writes; `slice_data.py rows=N` under-filling; the per-element CE-gate loop;
  the unigram default path; the `0` sentinel; the inconsistent PIECE window
  in tests; the missing end-to-end align test.
- **The same bitmask bug was repeated inside the new test** (`(flags & 2).sum()`
  instead of `((flags & 2) != 0).sum()`) and only surfaced when the real-data
  smoke test was finally enabled; it now counts rows and the smoke test runs
  for real. Fixing a defect once does not prove it is gone from its copies.
- **Rejected with evidence (2):** "plain_top24 not reproducible" (the auditor
  divided by all rows; over filled rows it is 0.9634 ≈ 0.9643); "`torch.rand`
  sync" (pre-existing, out of scope, moving it would break bit-equality).
- **Accepted as documented limitation (1):** the bit-equality test depends on
  WSL git plumbing for the worktree `.git` pointer; it passes, and the
  limitation is stated rather than hidden.

Two defects were found by my own verification and are the most important of
the round: the 54.4 % misalignment (§2) and the `np.where(..., out=...)`
crash in the first `distill_align` implementation (the unit tests never
entered `main()`, so a new end-to-end test now covers it).

**Review round (post-finalize, `/review uncommitted`).** Six independent
tracks over the same diff produced 16 verified findings; all are fixed:
overwrite guards in `soft_mask.py fill` and `slice_data.py`; the CPU gate's
NaN scan, which had been deleting the very lines it was meant to inspect;
`run_rocm.sh` argument parsing (the documented `MODE=…` form was silently a
benchmark); three broken runbook commands; the `dml_env.ps1` interpreter
path; the misaligned bit-equality loop in `slice_data.py`; `bench_steps.py`
now imports `train.distill_loss`/`teacher_row_offsets`/`gates_for_batch`
instead of re-implementing them (its `--mask`/`--weight` were inert); the
per-element store loop in `Soft.batch` is vectorised; the bootstrap is
O(1) per replicate instead of O(n); `masks.json` is written atomically;
`--limit` is honoured. After the refactor the masked+align training path
still reproduces the recorded step-100 loss exactly (8.560, batch 256,
seed 0), and all 38 tests pass.

---

## 8. Recommended next runs (prioritised)

Costs use measured throughput. Screens: `slice100k`, 3 000 steps, batch 256.

| # | Run | Why first | Cost | Decision rule |
|---|---|---|---:|---|
| 1 | **V9 alignment** (2M, 30k steps, `distill_align=`) vs V1@30k | 54.4 % of targets move to the right place; this is the only lever with a defect behind it | 38 min screen, then 2 × 6.3 h | promote if heldout loss beats V1@30k by ≥0.02 nats; then full 90k and paired Glide |
| 2 | **V2 mask PIECE from KD** on top of V9 | 15.2 % of KD rows point at a distribution the teacher gives 0.0 mass to | +0 min on the same run length | promote if ≥0.02 nats over V9 |
| 3 | **V3 candidate-count weight** on top of V2 | 2.3 % of rows are renormalisation noise; weights are already built | +0 min | promote if ≥0.02 nats over V2 |
| 4 | V0 CE-only, V5a alpha 0.3, V8 unigram fill | controls and the two cheaper repairs | 38 min each | as in the plan's matrix |
| 5 | V4 (1.2M epoch-matched) and V6 (60k/120k) | budget questions, not defect questions | 11.6 h / 12.6 h / 25.2 h | only after 1–3 |

**Optional cloud, priced and not executed:** one H100 run (~4.5 h, ≈13 €,
`NEXT-SESSION-H100.md` §5) is the only way to get the three levers local work
cannot reach: a true tail bucket (needs the teacher's discarded mass —
`research-notes.md` §1), word-space teacher targets (needs the raw
distribution), and a 32k vocabulary with compounds (needs new soft targets).
It is worth doing only after the V9/V2/V3 screens show that the current data
still has headroom.

---

## 9. Open decisions for the user (max 5)

1. **Is the alignment fix allowed to change the shipped model?** V9 changes
   what the loss sees for 54 % of rows; the model that ships must be retrained
   (6.3 h at 30k, ~19 h at 90k) even though it is a bug fix, not a new idea.
2. **Teacher re-pass or not?** Only a re-pass unlocks the tail bucket,
   word-space targets and a 32k vocabulary (≈13 € H100). Otherwise the
   teacher-free ceiling is V9 + V2 + V3 + V0/V5/V8.
3. **OpenSubtitles licence:** may a CC BY-NC corpus stay in a *shippable* 2M
   model? If not, the 2M data must be rebuilt without it.
4. **Shipping budget:** is ≤13 MB fixed? If 12.9 MB were acceptable, a 32k
   vocabulary becomes possible in the re-pass option; today it is excluded.
5. **Test-set discipline:** may `best.pt` be selected on Glide, or only on
   heldout ppl? Recommendation: ppl only; the item dumps now make an honest
   single evaluation possible.

---

## 10. Limitations — what these numbers do NOT show

- **No variant has been trained yet.** This session delivered the plan, the
  data derivations, the loss hooks and the measurement machinery; §6 is a
  convergence gate on a 10k-row slice, not a quality result.
- The 2M-vs-1.2M +0.54 pp is **one comparison on one test set**; Holm across
  the family of comparisons has not been applied because the family is still
  being defined. Treat it as "worth confirming", not as "proven".
- The slice screens overfit by design; heldout ppl on `slice100k` is a
  *sample-efficiency* signal, not a shipping estimate.
- DirectML numbers come from a 490-sentence slice at batch 64; they do not
  transfer to batch 256 on the full corpus without remeasurement.
- `research-notes.md` §5's "no documented workaround" for DirectML is now
  known to be wrong for `take_along_dim`/advanced indexing; the note keeps the
  original citation and this document records the refutation.
