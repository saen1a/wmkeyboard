# Teacher-free plan — best German `.wmlm` without a new teacher pass

Stage: **plan** (v2, after independent review; corrections listed in §10).
Input: `research-notes.md`, `NEXT-SESSION-TEACHER-FREE.md`,
`wmlm-training-plan.md` §1.3/§4/§7, `artifacts/README.md`,
`cloud/scaleway/README.md`, `cloud/scaleway/NEXT-SESSION-H100.md`, plus the
repo measurements in `research-notes.md` §0.

Hard constraints: no GPU rental, no teacher re-pass, no commit/push, no
unproven numbers.

**Path note.** `NEXT-SESSION-TEACHER-FREE.md` §C names
`wmk-glide/tools/wmlm/soft_mask.py`; the trainer it patches lives at
`tools/wmlm/train.py` (the same prompt cites `tools/wmlm/train.py:88`).
Code that imports the trainer therefore goes to `tools/wmlm/`;
standalone local runners go to `wmk-glide/cloud/local/`.

---

## 1. What is actually left on the table

The shipped model `artifacts/models/de_context_2m.wmlm` (10 856 364 B) is
trained on 2M soft targets with `alpha=0.5`, `share=0.5`, 90k steps. Measured
Glide/typing deltas against the 4B/150k model are inside noise
(`|z| < 1.2`), so the remaining levers are (a) repairs of known data defects
and (b) effects large enough to resolve with a paired test.

| Lever | Evidence | Expected size | Cost |
|---|---|---|---|
| **Soft rows are per word, but `train.py` places them per token: 54.4 % of KD targets land on the wrong logits position** | measured 2026-10-31 on 3000 sentences: 54.4 % of rows, 72.1 % of sentences affected; the word-aware grouping is the one that reproduces `audit_signal.json`'s 15.3 % piece share (the naive formula gives 34.1 %) | the largest available, unknown until measured | free (`distill_align=`) |
| 15.3 % of target rows are subword pieces; the teacher assigns them **0.0** top-24 recall, so the KD half of the loss on those rows is wrong | `audit_signal.json:11,17,31,37` (2M: `actual_is_piece 0.153`, `piece_top24 0.0`), recomputed word-aware 0.1517 | unknown; 15.2 % of KD rows | free (KD mask) |
| 9.38 % of rows are empty (first word): no soft signal at all | `audit_signal.json:4,24` | unknown; 9.4 % of rows | free (unigram fill) |
| Renormalised top-k frees the student's tail; CE is the only counterweight present | `research-notes.md` §1 (arXiv 2610.15589) | small | free (alpha sweep) |
| 2.5 % of rows have <=3 candidates and are currently weighted like a 24-candidate row | `audit_signal.json:8,29` (`share_le3 0.0254`) | small | free (KD weights) |
| 1.2M was undertrained (ppl 77.7 → 74.8 between 25k and 30k) | `NEXT-SESSION-TEACHER-FREE.md:69-71` | none — epoch-matched test only | GPU time |
| Checkpoint averaging over the last evals | not measured here; typical effect is an estimate, **UNVERIFIED** | small | free (post-hoc) |
| True tail bucket, word-space teacher targets, 32k vocab | `research-notes.md` §1/§2 | largest, but **needs a teacher re-pass** | out of scope (option only) |

Two classes of work follow: **defect repairs** that change what the loss sees
(V2, V3, V8) and **budget probes** that change how long/strong the same data
is used (V0, V4–V7).

---

## 2. Data preparation (complete specification)

### 2.1 Inputs (fixed, never modified)

| File | Bytes |
|---|---:|
| `artifacts/out/de_soft_2m.npz` | 1 077 027 763 |
| `artifacts/out/de_soft_1m2.npz` | 652 802 284 |
| `artifacts/out/de_soft_150k.npz` | 116 764 830 |
| `artifacts/out/de_lm_2m/train.npz` | 178 067 134 |
| `artifacts/out/de_lm_2m/heldout.npz` | 1 797 346 |
| `artifacts/out/de_lm_2m/heldout.tsv` | 1 607 666 |
| `artifacts/out/de_lm_2m/vocab.txt` | 239 434 |

Schemas (MEASURED, `research-notes.md` §0):

- soft: `sentences` int32[n_sent] strictly increasing, `starts` int64[n_sent+1]
  from 0 to `rows`, `ids` int16[rows,24], `probs` float16[rows,24], row mass
  <= 1.0004.
- 2M: `rows = 21 378 590`, `n_sent = 1 979 982` of the 1 980 000 train
  sentences — **18 train sentences have no soft entry**, so a soft sentence
  index is *not* a train sentence index.
- train: `tokens` int32[40 556 654], `starts` int64[1 980 001].
- Sentence layout `[reg, field, lang, <s>, w0 … wL-1, </s>]`, prefix 4, so
  onehd soft row `r` of soft sentence `s` predicts
  `train.tokens[train.starts[soft.sentences[s]] + 4 + r]`
  (`tools/wmlm/train.py:69-74`, `tools/wmlm/distill.py:120-136`).
- vocabulary 24 576 = 16 specials + 480 `▁` start pieces + 1 568 `##`
  continuation pieces + 22 512 whole words.

### 2.2 Output artifacts

| Output | Schema | Size (est.) | Determinism |
|---|---|---:|---|
| `artifacts/out/de_soft_2m.masks.npz` | `flags` uint8[rows] (1 EMPTY, 2 PIECE, 4 LE3), `weight` float16[rows] in [0,1], `target` int16[rows] (-1 = none), `pos` uint8[rows] (255 = none), `sentences` int32, `starts` int64, `version` uint8 | measured **152 MB** (np.savez, uncompressed) | pure function of the npz + `--weight` |
| `artifacts/out/de_soft_2m.masks.align.npz` | `pos` uint8, `target` int16, `sentences`, `starts`, `version` | measured **88 MB** | same pass |
| `artifacts/out/de_soft_2m.masks.keep.kd.npz` / `.keep.kdce.npz` | `kd` uint8[rows]; kdce adds `ce` uint8[rows] | measured 21 MB / 43 MB | derived from `flags` |
| `artifacts/out/de_soft_2m.masks.json` | counts and shares per flag, weight quantiles, `sha256` of the npz, params, git rev; **`sha256_stable`** over a canonical dict that excludes `elapsed`/`git_rev` | few KB | two runs → identical `sha256_stable` |
| `artifacts/out/de_soft_1m2.masks.npz` + `.json` | same | ≈ 40–55 MB | same |
| `artifacts/out/de_unigram_2m.npz` | `p_first` float32[vocab] (sums to 1.0 over the 2M corpus' sentence-initial words), `counts` int32[vocab], `n_first` int64, `vocab_sha256` bytes | 200 KB | sort-free, exact integer counts |
| `artifacts/out/de_soft_2m_filled.npz` | copy of the 2M soft file where **row 0 of every sentence** with zero mass is replaced by `p_first` top-24 (ids descending by p, probs renormalised over those 24) | ≈ 1.1 GB (copy) | derived, seeded-free |
| `artifacts/out/de_lm_2m_slice10k/` | `train.npz` (10 000 **rows**, ≈ 933 sentences), `vocab.txt`/`heldout.npz`/`heldout.tsv` byte copies, `slice.json` (source sentence indices, row count, sha256) | ≈ 1.5 MB | seed 0, sorted indices |
| `artifacts/out/de_lm_2m_slice100k/` | same, 100 000 **sentences** (≈ 1.07M rows) for the L1 screen | ≈ 12 MB + 2 MB copies | seed 0, sorted indices |
| `artifacts/out/de_soft_2m_slice10k.npz` (+ `.masks.npz`) | parent schema, `sentences` re-indexed into the slice | ≈ 1.2 MB | derived |
| `artifacts/out/de_soft_2m_slice100k.npz` (+ `.masks.npz`) | same, ≈ 1.07M rows | ≈ 26 MB | derived |
| `artifacts/out/eval_dumps/<model>/<harness>.tsv` | `item_id\tsrc\t<metric columns>` | KB–MB | source order |

Rule: derived files never overwrite inputs; every writer writes `<path>.tmp`,
`os.replace`s it, then drops `<path>.sha256`. Everything above lives under
`artifacts/out/`, which `artifacts/.gitignore` already excludes — masks
(<=130 MB) and checkpoints (81 MB/run) must never be staged.

### 2.3 Flag and weight definitions (exact)

For soft row `i` in `[0, rows)`, with `s = searchsorted(starts, i, 'right') - 1`,
`r = i - starts[s]`, `ss = int(sentences[s])`, `t0 = train.starts[ss]`:

**Rows are per word, positions are per token.** Group the sentence body
`train.tokens[t0+4 : train.starts[ss+1]-1]` into words by joining every token
whose vocab entry starts with `##` onto the previous group. Group `r` is soft
row `r`; the group count must equal the soft row count (2M: verified on 3000
sentences, 3000/3000). Then:

- `target[i]` = the **first** token id of group `r` (what CE predicts at that
  position), int16; `-1` if the group does not exist.
- `pos[i]` = (first token index of group `r`, sentence-relative) **- 1**,
  uint8; `255` = unavailable. This is the logits position that predicts word
  `r`. The old formula `4+r` is wrong: it equals the word-aware position only
  while no earlier word was spelled in pieces (34.1 % vs 15.3 % piece share,
  see §1).
- `PIECE` iff the **last** token of group `r` starts with `▁` or `##`
  (equivalently: the word is OOV-spelled). Recomputed on 2M: **0.1517**.
- `EMPTY` iff `probs[i].sum() == 0` (MEASURED 0.0938). These are **not** all
  `r == 0`: in a 20 000-sentence sample, 248 sentences (1.24 %) have their
  empty row later, because `distill.py:118` also skips a position whose
  teacher word-end has no offset match. Read `EMPTY` from `probs`, never from
  position.
- `LE3` iff `0 < (probs[i] > 0).sum() <= 3` (recomputed on 2M: **0.0230** of
  all rows; `audit_signal.json`'s 0.0254 is a different cut and is treated as
  stale).
- `weight[i] = (probs[i] > 0).sum() / 24` (`--weight=cand`), `1.0`
  (`--weight=none`); `EMPTY` rows get `0.0`.
- `HIGH_NLL`: **not modelled.** The 729 rows were selected with the teacher's
  own NLL, which the stored file no longer carries; they are covered by `LE3`
  discounting. Recorded as a known gap, not silently dropped.

Whole-word recall, over **filled** rows only (denominator matters):
`plain_top24 = 0.9643` (recomputed 0.9634; over all rows it is 0.8727),
`all_top24 = 0.8167`, `piece_top24 = 0.0` (`audit_signal.json:12-18`).

### 2.4 Leak and split rules

1. `heldout.npz`/`heldout.tsv` stay byte-identical and are only copied.
2. Every slice/mask derives from `train.npz` + the soft file.
3. Slice selection = sorted uniform sample of **sentence indices** with
   `numpy.random.default_rng(0)`, without replacement. `slice10k` then keeps
   sentences until 10 000 **rows** are covered (the last one may overshoot by
   <40 rows; the exact count is written to `slice.json`); `slice100k` keeps
   100 000 sentences.
4. A soft subset copies `ids`/`probs` bit-for-bit and rewrites only
   `sentences` through the index map; the test hashes both and compares.
5. `de_soft_1m2 ⊂ de_soft_2m` (one seeded permutation). Any 1.2M-vs-2M
   statement says so; it is not a corpus-size experiment (§6 R5).
6. No build step reads `artifacts/data/de_swipes.jsonl`.

### 2.5 Invariants (unit tests, `tools/wmlm/tests/test_soft_mask.py`)

| # | Invariant |
|---|---|
| I1 | `len(flags) == len(weight) == len(target) == rows`; `starts[0]==0`, `starts[-1]==rows`, `diff(starts)>=0` |
| I2 | `sentences` strictly increasing and `< len(train.starts)-1` |
| I3 | `PIECE` count within 0.145–0.160 of rows; every `PIECE` row's target is a piece token, and no non-`PIECE` row has bit 2 |
| I4 | `EMPTY` rows are exactly `probs.sum()==0` on a 50k random sample and on all rows of the 10k slice |
| I5 | Recompute `target` independently from `train.npz` for **all** rows of the 10k slice and 200k random rows of 2M: equality holds, including after the `sentences` indirection (this is the test that would have caught the off-by-N) |
| I6 | `LE3` rows have 1–3 positive entries; `EMPTY` ⇒ weight 0; `LE3` ⇒ weight <= 3/24 |
| I7 | `de_unigram_2m.npz`: `p_first.sum() == 1.0 ± 1e-6`, `n_first == sum(starts[1:]-starts[:-1]) of first-word counts`, and the top-5 words equal a hand-computed top-5 |
| I8 | Rebuild twice → identical `sha256_stable` for masks, identical npz bytes for the slice |
| I9 | Slice: `ids`/`probs` hash equality against the parent rows; `sentences` maps back through `src_index` |
| I10 | `masks.json["counts"]` equals the number of rows with each flag bit set (regression: counting with `.sum()` on the masked bit doubled PIECE and quadrupled LE3) |
| I11 | Word-group count per sentence equals that sentence's soft row count; a mismatch raises with the sentence index |

`masks.json` also prints the exact denominators used by each variant:
rows in KD, rows with CE, rows in both, rows in neither.

---

## 3. Variant matrix

Reference **V1/R**: full 2M, `alpha=0.5`, `share=0.5`, no mask/weight, batch
256, ctx 40, d256/6/4/768, 90k steps — the shipped model.

Throughput (MEASURED): **GPU 1.32 steps/s** at batch 256 incl. distill
(`~/wmlm-de/out/student.log`), **1.03 steps/s** with mask+align and two other
trainers sharing the box (2026-10-31); **CPU 1.52 s/step** at batch 64
(0.66 steps/s, 2026-10-31; the older 0.52 s/step figure in
`wmlm-training-plan.md:108` was a single-run measurement).

**Two-stage evaluation, because that is the only way the thresholds can fire.**

- **Screen metric = heldout loss** (`de_lm_2m/heldout.npz`, 8 000 sentences ≈
  86k positions, `train.py:115-131`). Per-position loss sd ≈ 4 nats ⇒ marginal
  SE ≈ 0.014 nats; a pre-registered **0.05 nats** screen threshold is ~3.5 SE
  and means ~5 % relative ppl. Screens compare variants at **equal steps**, so
  absolute ppl is not compared against the 90k reference.
- **Confirmation metric = paired Glide** (`blend_top1`) with item dumps,
  McNemar + bootstrap (§4). Effects below the MDE in §4.1 need confirmation on
  the larger set, not a bigger claim.

| ID | One change vs R | Hypothesis | Screen metric | Abort (screen) | Local runtime |
|---|---|---|---|---|---|
| **V9** | `distill_align=` (word-aware row→position map from `--emit-align`) | the current placement is wrong for 54.4 % of rows (§1); a correct placement should be the single largest teacher-free gain | heldout loss @30k, then paired Glide | revert if loss >= V1-at-30k + 0.02 nats | 38 min screen / 6.3 h @30k |
| **V0** | `distill=` empty (CE only), same 30k-step budget | KD is what produces the +2–3 pp; without it Glide should fall to baseline | heldout loss @30k | abort if V0 loss is **lower** than R-30k by >= 0.05 nats (would mean soft targets are net harmful) | 6.3 h (30k) |
| **V1** | — (reference; already trained at 90k) | KD beats CE-only | — | — | 0 (exists) |
| **V2** | `distill_mask=` with the `PIECE` bit, applied to the **KD term only**; CE keeps its true token | the KD half on those rows is aimed at a distribution the teacher never gives to that token; removing it should not hurt CE's spelling signal | heldout loss @30k | revert if loss >= R+0.05 nats at equal steps | 38 min screen / 6.3 h @30k |
| **V2b** | same mask applied to **KD and CE** | the piece target is a spelling artefact; removing it everywhere may free word capacity — but it also removes legitimate rare-word spelling supervision, so this is a separate, pre-registered bet | heldout loss @30k | revert if loss >= V2 + 0.05 nats | same run length as V2 |
| **V3** | V2 + `distill_weight=cand` (KD term only) | <=3-candidate rows are renormalisation noise; down-weighting them lowers gradient variance | heldout loss @30k | revert if no improvement >= 0.02 nats vs V2 | +0 min |
| **V4** | 1.2M data at **epoch-matched** 55k steps (R = 90k×256/1.98M ≈ 11.6 epochs; 11.6×1.2M/256 ≈ 54.4k) | the earlier "1.2M is worse" reading confounded steps with data; at equal epochs the gap should shrink or invert | heldout loss @55k | abort if loss worse than R-55k by >0.10 nats | 11.6 h |
| **V5a** | `alpha=0.3` (share 0.5) | more CE pulls the freed tail back (`research-notes.md` §1) | heldout loss @30k | revert if >= R+0.05 nats | 6.3 h |
| **V5b** | `alpha=0.7` (share 0.5) | more KD sharpens word choices, may cost calibration | heldout loss @30k | revert if >= R+0.05 nats | 6.3 h |
| **V5c** | `share=0.7` (alpha 0.5) | more teacher-batch exposure at equal steps | heldout loss @30k | revert if >= R+0.05 nats | 6.3 h |
| **V6** | 2M at 60k and at 120k (two legs) | the ppl optimum was 85k; the curve may still be rising at 90k | ppl vs step, two consecutive evals | stop a leg if ppl rises in two consecutive evals | 12.6 h + 25.2 h |
| **V7** | checkpoint averaging of `last.pt` at 80k/85k/90k (post-hoc, no training) | the LR tail is noise; averaging is free | heldout loss of the average | discard if worse than `best.pt` | 0 |
| **V8** | use `de_soft_2m_filled.npz` (row-0 unigram fill) | 9.4 % of positions carry no soft signal; `P(w|<s>)` is a real distribution | heldout loss @30k; then typing next-word per register | abort if typing `nextword_top1` drops >0.5 pp | 38 min screen / 6.3 h @30k |

V5 is four single-change legs, not one alpha/share sweep: changing both at
once confounds tail-drift control with teacher exposure. V6's cosine schedule
is parameterised by `steps` (`train.py:152`), so schedule co-varies with the
step budget **by construction** — that is what a step-budget experiment is,
and it is stated instead of pretended away. V7 is checkpoint averaging only;
optimiser-state EMA would be a training change and is deferred.

Ordering: screen everything on `slice100k` at 3 000 steps, batch 256
(≈38 min each, GPU). Promote only variants with a >=0.05-nat screen win or a
paired Glide CI that excludes 0. At most two promotions per session.

---

## 4. Evaluation plan

### 4.1 Resolving power

Paired comparison of two models on the same items; McNemar sample size
`N = (1.96·√p_d + 0.8416·√(p_d − d²))² / d²` (80 % power, alpha 0.05,
`research-notes.md` §4; computed here):

| n | p_d=5 % | 10 % | 20 % | 30 % |
|---|---:|---:|---:|---:|
| 2 588 (Glide swipes) | 1.23 pp | 1.74 pp | 2.46 pp | 3.01 pp |
| 500 (typing cases) | 2.79 pp | 3.95 pp | 5.59 pp | 6.85 pp |

These are **minimum detectable differences**, not confidence intervals. The
prompt's ±1.2 pp / ±3.1 pp are not standard marginal half-widths either
(those would be 1.62 pp and 4.25 pp at the observed accuracies of 77 % and
62 %); neither number is a paired test, so the plan uses the table above and
reports the *measured* `p_disc` with every p-value.

Consequence: the 500-item typing set cannot resolve anything below ~2.8 pp;
every claim below that must come from the 2 588-item Glide set with an
explicit `p_disc` (i.e. from item dumps), or from heldout loss as a
continuous screen — never from a raw accuracy delta.

### 4.2 Item dumps in the harness

`ITEMS=<path>` env var in both harnesses, additive and off by default; the
normal stdout line must be byte-identical with and without `ITEMS`:

- `glide_lm_blend_eval.rs`: `item_id` + `blend_top1`, `blend_top4`,
  `raw_top1`, `raw_top4`. `item_id` = index in the filtered record vector
  (`glide_lm_blend_eval.rs:48-56`); the filter depends only on the swipe word,
  so ids align across models. Rows are returned from the worker threads and
  written sorted by id, so the file does not depend on `THREADS`.
- `typing_eval.rs`: `item_id` + `<mode>_nextword_top1`, `<mode>_nextword_top3`,
  `<mode>_strip_top1` per mode, so `base` and `lm` are diffable per case.

### 4.3 `tools/wmlm/paired_eval.py`

Input: two dumps with identical `item_id` sets and one metric column.
Output (JSON + table): `n`, `acc_a`, `acc_b`, `delta`, `b`, `c`,
`p_disc`, McNemar **exact** two-sided binomial p (plus chi-square with
continuity correction when `b+c >= 25`, for compatibility), paired bootstrap
95 % CI over items (10 000 resamples, percentile, fixed seed printed), Holm
across a supplied family of p-values, `--mde` (n, p_disc → d) and `--power`
(p_disc, d → n). Refuses id-set mismatch and non-0/1 columns.

### 4.4 Metrics and the domain-distant test

Primary: `blend_top1` on 2 588 FUTO swipes — domain-distant by construction
(real user swipes, corpus not in training). Secondary: `nextword_top1` on
`heldout.tsv` (in-domain).

Free extra split, because `heldout.tsv` carries the labels
(`prep.py:125-127` writes `reg\tfield\tlang\ttext`): typing cases split by
`field=1` (chat) vs `field=0` (news/other), reported per register. This is the
guard for the trap that `chat↔casual` and `news↔formal` are 1:1 in the corpus
— a news-only gain must not be sold as a general one.

---

## 5. 9060 XT validation plan

`research-notes.md` §5: the card is `gfx1200` (AMD's supported-GPU table;
`gfx1201` is the RX 9070 family, so the prompt's "gfx1201" is a naming error,
not a target to chase). ROCm 7.2.1 + torch 2.9.1 is the documented and
already-working combination. torch-directml's newest artifact is
0.2.5.dev240914 (torch 2.4.1) and gather/scatter backward is unsupported and
closed as not planned (DirectML #420), so the recorded crash is a platform
limit, not our bug.

| E | Question | Run | Success | Abort |
|---|---|---|---|---|
| E1 | Is the GPU up? | `rocminfo \| grep -m1 gfx`; `python -c "import torch;print(torch.cuda.is_available(),torch.cuda.get_device_name(0))"` | prints `gfx1200` and `True` | GPU work off; CPU path only |
| E2 | Does the masked loss keep ROCm throughput? | **2 000 steps**, batch 256, `slice10k`, `distill_mask=` | finite loss, >=1.05 steps/s (0.8× 1.32) | if <0.5 steps/s, fix indexing before any long run |
| E3 | Is the DirectML claim reproducible? | throwaway venv with `torch-directml==0.2.5.dev240914` + `torch==2.4.1`, then the 3-line gather-backward repro from `research-notes.md` §5 | either 2 000 steps run, or the exact error captured | time-box 20 min install + 5 min test, max two attempts |
| E4 | Does a scatter-free distill loss work on DirectML? | `WMLM_DISTILL_IMPL=onehot` 2 000 steps | finite loss, >=1 step/s, <4 GB VRAM | record and stop |
| E5 | Docker `rocm/pytorch` as an alternative? | `docker run --rm --device=/dev/kfd --device=/dev/dri rocm/pytorch:rocm7.2.1_... python -c "import torch;print(torch.cuda.is_available())"` | `True` | if Docker is absent in WSL or the pull exceeds 10 min, skip and record |
| E6 | CPU baseline | 100 steps, batch 64, `slice10k` | steps/s reported | — |

Decision rule: **ROCm/WSL trains; CPU verifies (mandatory 2 000-step gate);
DirectML is documented as forward/inference-only** whichever way E3/E4 go. No
variant ever runs on DirectML. E3/E4 replace the prompt's "DirectML
workaround" deliverable with either a working scatter-free path or a
reproducible error string plus the upstream links — which is what gate 6
allows.

---

## 6. Risk and failure catalog

| # | Risk | Effect | Mitigation |
|---|---|---|---|
| R1 | Row→target mapping uses the soft index as the train index | every target after the first missing sentence is wrong; masks silently cut wrong rows | `soft.sentences[s]` indirection in §2.3; I5 recomputes `target` for all 10k-slice rows and 200k random 2M rows |
| R2 | `EMPTY` derived from position instead of `probs` | 1.2 % of sentences lose a different row | §2.3; test I4 |
| R3 | Mask applied to KD but weight applied to CE (or vice versa) | two effects in one variant | both live in the KD term only; test asserts the same index set for KD mask and KD weight |
| R4 | Default path silently changes | "improvement" is a loss change | bit-equality test: `git show HEAD:tools/wmlm/train.py > tools/wmlm/_ref_train.py`, run both on CPU with `PYTHONPATH=tools/wmlm`, same seed, 20 steps, with and without `distill=`; loss sequence and parameters must match exactly; temp file removed in `finally` |
| R5 | 1.2M ⊂ 2M read as a size experiment | wrong conclusion | V4 is epoch-matched and labelled as a subset test |
| R6 | Register/field 1:1 (chat↔casual, news↔formal) | `field` looks like a source | §4.4 per-register split |
| R7 | OpenSubtitles not separable from chat | chat is not a clean domain test | state it; Glide swipes remain the domain-distant test |
| R8 | Eval word list domain-near | inflated Glide numbers | raw (no-blend) column in every dump |
| R9 | ppl compared across corpora | false progress | only `de_lm_2m/heldout.npz`; the 150k ppl is marked n. v. |
| R10 | Piece targets read as "normal" | 15.3 % of the KD loss is unexplained | V2; `audit_signal.json:17` |
| R11 | Small-n noise sold as effect | false claims | §4.1 table, paired tests, Holm, `p_disc` in every report |
| R12 | Long GPU run dies (WSL idle, reboot) | lost hours; `resume=` resets AdamW moments (`train.py:154-160`), so the loss has a visible step | `resume=last.pt`, `eval_every=1000`, `vmIdleTimeout=-1`; note the moment reset in the results log |
| R13 | Disk | 8 variants × 81 MB + 130 MB masks | `best.pt` only after a dump exists; checkpoints under `artifacts/out/<variant>/` |
| R14 | torch-directml install breaks the ROCm venv | dead GPU | separate venv only; never touch `/opt/wmlm-venv` |
| R15 | Teacher-free conclusion over-claimed | plan promises what data cannot show | abort criteria per variant; results doc separates measured from recommended |
| R16 | >5 MB binaries staged | repo hygiene / gate 7 | `.gitignore` already covers `artifacts/`; before finalize, `git status --porcelain` must show only text files under `wmk-glide/plans`, `tools/wmlm`, `wmk-glide/cloud/local`, `native/wm-engine/examples` |

### Decisions the user must make (not guessed here)

1. Whether a future teacher re-pass (true tail bucket, word-space targets, 32k
   vocab) is worth ≈13 € H100 after the local screens — this is the only path
   to the largest levers.
2. Whether OpenSubtitles (CC BY-NC) may remain in a *shippable* 2M model.
3. Whether the shipping budget stays <=13 MB (rules out d320/8/1024).
4. Whether a checkpoint may be selected on the Glide harness, or only on
   heldout ppl. **Recommendation: ppl only**, to keep the test set honest.
5. Whether a 4–6 h GPU run may start unattended in this session or only after
   the screens are reviewed.

---

## 7. Cost and time (local; cloud only as an option)

| Item | Time | Cost |
|---|---:|---:|
| L0 mandatory CPU gate (`slice10k`, 2 000 steps, batch 64) | **50 min** measured 2026-10-31 (0.66 steps/s) | ~0.05 € |
| Mask + unigram + fills (2M, 1.2M, slices; memmap pass) | 20–35 min | — |
| L1 screen per variant (100k sentences, 3 000 steps, GPU) | 38–49 min measured (1.03–1.32 steps/s) | ~0.05 € |
| L1 screens, 7 promoted legs (V0,V2,V2b,V3,V5a/b/c,V8) | ~4.4 h | ~0.55 € |
| L2 confirmation per variant @30k | 6.3 h | ~0.8 € |
| V4 @55k / V6 @60k / V6 @120k | 11.6 h / 12.6 h / 25.2 h | 1.5 / 1.6 / 3.1 € |
| Export + Glide + typing + paired eval per model | 15 min | — |
| **This session (L0 + L1 + item dumps + docs)** | **≈5–6 h wall** | **≈1 €** |

Optional cloud, priced and not executed: one H100 run ≈2.89 €/h, ~4.5 h
≈13 € buys the three things local work cannot (true tail, word-space targets,
32k vocab), per `NEXT-SESSION-H100.md` §5.

---

## 8. Gates (mapping to the prompt's acceptance criteria)

| Prompt gate | How this plan meets it |
|---|---|
| 1. Every variant: hypothesis, one change, metric, abort, runtime | §3: nine rows, five fields each; V5 split into four single-change legs; V6's schedule co-variance stated |
| 2. Every derivation: schema + hash + invariant test | §2.2/2.5, `masks.json` `sha256_stable` |
| 3. Loss default bit-identical | R4 test against `git show HEAD:` copy, CPU, with and without `distill=` |
| 4. Audit without open high-confidence findings | audit stage, findings JSON, fixed before finalize |
| 5. 2 000-step local run converges | L0: running training loss finite, strictly lower at 2 000 than at 100, no NaN. Note measured 2026-10-31: on that 10k-row slice the model memorises, so **heldout ppl rises** by design; the gate is the training loss, and the heldout curve is reported as a diagnostic, not a gate. |
| 6. 9060 XT reproduced or documented as not reproducible | §5 E1–E6; DirectML gets an error string + issue links |
| 7. No cloud spend, no push | no `scw`, no commit/push; R16 staging check |

---

## 9. Audit note

Audit verdict and applied corrections: `plans/audit-findings.json` (round 1,
15 findings: 13 auditor items + 2 found during verification), and the summary
in `teacher-free-results.md` §"Audit". The plan above already contains the
corrections; nothing below supersedes any section.

---

## 10. Corrections applied after audit round 1

1. **§2.3 rewritten**: rows are per word, not per token. The `4+r` mapping was
   wrong (54.4 % of rows misplaced, measured). `target` is now the first token
   of the word, `pos` is the sentence-relative logits position, and `PIECE`
   is derived from the last token of the group.
2. **§1 gained the alignment lever** as the first row, and **§3 gained V9**.
3. **§2.2 gained `masks.align.npz`, `keep.kd.npz`, `keep.kdce.npz`** and the
   measured sizes (152 MB / 88 MB / 21 MB / 43 MB) replacing the estimate.
4. **§2.5 gained I10 and I11** (flag counts vs rows; group count vs rows).
5. **Piece/LE3 shares** are now the recomputed values (0.1517 / 0.0230), not
   `audit_signal.json`'s (0.153 / 0.0254), and the recall denominator is
   stated (filled rows).
6. **CE gate** is vectorised (`masked_fill_`), the offset sentinel is `-1`,
   and `paired_eval.py` reports `p_chi2_cc` (a probability) next to
   `chi2_stat`.
7. `slice_data.py rows=N` fills to N in rounds; `paired_eval.py` drops `-1`
   sentinel rows (required for `typing_eval.rs` dumps).
