# Research notes — teacher-free improvement of the German `.wmlm`

Stage: **research** (input to `teacher-free-plan.md`).
Compiled 2026-10-31 from two cited research passes (R1: knowledge
distillation, OOV targets, evaluation statistics; R2: training backends for
the RX 9060 XT). Sources were read on 2026-10-30/31. Claims marked
**MEASURED (repo)** come from this repository and are reproducible with the
commands in `artifacts/README.md`; everything else carries its URL.

Scope: no new teacher pass, no rented GPU. The question is what can still be
improved on the *existing* soft targets `de_soft_1m2.npz` / `de_soft_2m.npz`.

---

## 0. Repo measurements taken for this plan (MEASURED, 2026-10-31)

Read from `artifacts/out/` with `/opt/wmlm-venv/bin/python` (WSL Ubuntu 24.04):

| Fact | Value |
|---|---|
| `de_soft_2m.npz` arrays | `sentences` int32 [1 979 982], `starts` int64 [1 979 983], `ids` int16 [21 378 590, 24], `probs` float16 [21 378 590, 24] |
| `de_lm_2m/train.npz` | `tokens` int32 [40 556 654], `starts` int64 [1 980 001], monotone |
| Row mass (first 300k rows) | filled share 0.9061, `sum(probs)` max 1.0004 |
| Rows with <=3 positive candidates (filled rows) | 2.60 % (prompt/`audit_soft.json` says 2.54 %) |
| Empty rows | 9.38 % (`audit_soft.json`), 9.44 % in my 200k sample |
| Vocabulary | 24 576 = 16 specials + 480 `▁` start pieces + 1 568 `##` continuation pieces + 22 512 words |
| Token layout in `train.npz` | `[reg, field, lang, <s>, w0, w1, ..., </s>]`, prefix len 4 |
| Row r of a soft file | target token index `starts[s] + 4 + r` (from `train.py:69-74` and `distill.py:125-136`) |
| GPU stack that works | WSL Ubuntu 24.04, ROCm 7.2.1 + librocdxg 1.2.0, torch 2.9.1+rocm7.2.1, RX 9060 XT, `torch.cuda.is_available()=True` |
| GPU student throughput | 30 000 steps, batch 256, d256/6/768/ctx40 **with** distill: 22 708 s → **1.32 steps/s** (`~/wmlm-de/out/student.log`, 2026-10-28) |
| CPU student throughput | 100 steps, batch 64: 52 s → 0.52 steps/s (`wmlm-training-plan.md:108`) |
| CUDA/ROCm torch on Windows itself | not installed; only WSL |

Consequence: every "local cost" below is computable from 1.32 steps/s (GPU)
and 0.52 steps/s (CPU, batch 64).

---

## 1. Top-k distillation with a renormalised tail

**Established.** Truncating the teacher to its top-k and renormalising is not
a neutral approximation: cached top-K probabilities are "biased estimates of
teacher probability distribution ... resulting in suboptimal performance and
calibration" [paper, https://arxiv.org/abs/2503.16870, 2026-10-31].

**Established.** A renormalised top-k objective "depends only on log-odds
among the retained tokens", so "its gradient along the directions that
control tail mass is exactly zero"; the measured tail-gradient component on a
real teacher is 2–3e-15, and adding a cross-entropy term shrinks the resulting
tail-mass gap "about fourfold but [it] persists"
[paper, https://arxiv.org/abs/2610.15589, 2026-10-31]. Exact recovery of the
teacher distribution from the retained set needs `k >= d+1` for hidden size
`d`; "commonly cached sizes sit below it".

**Established.** The normalised top-k objective "discards the information
about tail probability" and optimisation "can steadily increase the student's
tail probability and entropy, empirically degrading downstream accuracy". One
explicit tail token carrying the teacher's tail mass repairs this; reported
gain "up to 8.05 points" Avg@8
[paper, https://arxiv.org/abs/2608.14728, 2026-10-31]. A decoupled
top-K/tail KL is only "competitive", not better
[paper, https://arxiv.org/abs/2602.20816, 2026-10-31].

**Established.** Temperature is the mechanism that exposes soft-target
structure, and soft targets carry more information per example than hard
labels [paper, https://arxiv.org/abs/1503.02531, 2026-10-31]. Word-level KD
is defined as a per-position KL, optionally mixed with the NLL term
[paper, https://arxiv.org/abs/1606.07947, 2026-10-31].

**Established, negative.** Label-smoothing the *teacher* makes distillation
"much less effective" because it destroys inter-class similarity information
[paper, https://arxiv.org/abs/1906.02629, 2026-10-31]. KD itself behaves like
a learned label-smoothing regulariser, so part of its gain is regularisation
[paper, https://arxiv.org/abs/1909.11723, 2026-10-31].

**UNVERIFIED.** No source measured an optimal temperature for a ~10M
word-level LM; T stays a tuned hyperparameter, not an evidence-backed value.

### What this means here — and the one thing we cannot do

The tail-token repair needs the teacher's discarded tail mass per row.
`distill.py:132-136` renormalises `top_p / top_p.sum()` and writes only
`ids`/`probs`, so **the dropped mass is not recoverable from the stored
files** (MEASURED: row mass is 1.0 by construction). Adding a true tail bucket
therefore requires a teacher re-pass, which this session forbids. The
teacher-free substitute the research supports is the CE+KD mix: CE is the term
that measurably pulls the student's tail back (2610.15589). Consequence for
the plan: treat `distill_alpha` as the tail-drift control, and test
**alpha 0.3** (more CE) as the research-motivated direction — not as a blind
sweep. A tail bucket stays a documented follow-up gated on a future teacher
pass.

---

## 2. OOV / subword targets

**Established.** When the student vocabulary is a subset of the teacher's,
exact teacher likelihoods on student tokens can be computed from the BPE
recursive structure in O(1) evaluations per token; the general mismatched case
needs a lossless recursion or a beam approximation
[paper, https://proceedings.iclr.cc/paper_files/paper/2026/file/40d50fe20d5e6922dbb52d7da6de03f1-Paper-Conference.pdf,
2026-10-31].

**Established.** Naive token-level mapping between tokenizers introduces
tokenizer bias and semantic distortion (their example maps "carrier"
`[car][rier]` to "car", giving "the flag car")
[paper, https://doi.org/10.1609/aaai.v40i39.40637, 2026-10-31].

**Established.** Masking mismatched subword positions is workable but
expensive: "match strategy ... mask[s] all mismatched subwords", losing
"from 75% ... to 96%" of subwords usable for distillation; for reduced
vocabularies, "distillation without KL divergence loss ... performs the best"
[paper, https://doi.org/10.28995/2075-7182-2022-21-295-310, 2026-10-31].

**UNVERIFIED.** Mapping pieces to `<unk>` and spelling correction as
target-repair steps: no supporting source found.

### What this means here

Our 15.3 % piece targets are a *construction* defect, not an inherent OOV
problem: parameter `pieces=2048` spends 2 048 of 24 576 slots on spelling
pieces, so corpus words outside the 22 512 word slots land as `▁ab` + `##cd`
and become the one-hot target. Those rows can never be hit by a teacher whose
mapping only assigns mass to whole student words. The principled repair
(convert teacher mass into student-word space before top-k) needs the raw
teacher distribution — i.e. a re-pass. Locally the only honest options are
**mask** those rows (V2) and **fix the vocabulary** in a future run (32k with
compounds, new soft targets). Masking costs 15.3 % of rows; the research
warns that masking can be costly, so the plan must measure it rather than
assume it helps.

---

## 3. Sentence-initial targets (the 9.38 % empty rows)

**Established.** A well-defined LM conditions the first word on a boundary
symbol, `P(w1 | BOS)`; without it "we can't define a probability for the first
word" [course notes, https://liu-nlp.ai/lang-tech/documents/l4-language-modelling.handout.pdf,
2026-10-31].

**Established.** Sparse contexts back off recursively to lower-order
estimates, terminating at the unigram distribution — the standard treatment
for uninformative contexts
[course notes, https://www.cs.jhu.edu/~jason/465/hw-lm/hw-lm.pdf, 2026-10-31].

### What this means here

The empty rows are exactly the first word of each sentence: `distill.py:120-124`
starts the loop at `k=1`, and row 0 stays all-zero; `train.py:84` skips those
rows in the KD term. That is a generator bug, and `P(w1 | <s>)` is a real
distribution that the student is currently never taught softly. Teacher-free
repair: estimate `P(w1 | <s>)` from the corpus (2M first words) and fill the
empty rows with that distribution (V8). It is a *substitute* distribution, not
the teacher's — the research calls that fallback unverified, so it is a
measured variant, not an assumed win.

---

## 4. Evaluation with small n

**Established.** Only discordant pairs carry information; under the null each
discordant item is a coin flip, so an exact binomial test on `b` given
`b + c` is preferred when discordant pairs are few (guidance: <25)
[course notes, https://shonas301.github.io/ml-evaluation/part-1-foundations/08-significance.html,
2026-10-31]. McNemar is the standard paired accuracy test
[paper, https://aclanthology.org/P19-1267/, 2026-10-31].

**Established.** Paired bootstrap resamples *items*, recomputes the delta on
the same resample and takes the 2.5/97.5 percentiles; comparing two systems on
different samples is "strictly worse", and overlapping marginal CIs are not a
valid test [blog, https://matrixcognition.com/posts/bootstrap-eval-deltas.html,
2026-10-31]. Their worked simulation: n=500, 72 % vs 76 %, error correlation
0.6 → +3.6 pp, paired-bootstrap 95 % CI [-1.4, +8.4] pp, McNemar p=0.168;
detecting 4 pp at 80 % power "needs on the order of 2,000 items, not 500".

**Established.** McNemar sample size depends on discordant proportions:
`N = (z·sqrt(p_disc) + z_pow·sqrt(p_disc − p_diff²))² / p_diff²`
[doc, https://www.stata.com/manuals14/psspowerpairedproportions.pdf, 2026-10-31].
Derived from it: at 10 % discordance, 80 % power, alpha 0.05 two-sided, a
**2 pp** target needs ~1 960 items, **4 pp** ~490 items; at 20 % discordance a
2 pp target needs ~3 900.

**Established.** Holm–Bonferroni controls FWER and is uniformly more powerful
than plain Bonferroni
[doc, https://en.wikipedia.org/wiki/Holm%E2%80%93Bonferroni_method, 2026-10-31].

### What this means here

The 1.2 pp / 3.1 pp figures in the prompt are *marginal* half-widths, not
paired-difference half-widths. With 2 588 swipes the *paired* delta CI can be
much tighter when both systems agree on most items, so `|z| < 1.2` is
"not detected", not "no effect". The harness therefore has to dump per-item
outcomes (item dumps), and the plan's acceptance rule must be a paired delta
with bootstrap CI plus McNemar, with Holm across variants.

---

## 5. Hardware: what the RX 9060 XT can and cannot do

**Established. The card is `gfx1200`.** AMD's supported-GPU table lists
"AMD Radeon RX 9060 XT | RDNA4 | gfx1200 | Supported"; `gfx1201` is the
RX 9070 / R9700 family
[official doc, https://rocm.docs.amd.com/projects/install-on-linux/en/latest/reference/system-requirements.html,
2026-10-31].

**Established.** The installed combination is the documented 7.2.1 set:
RDNA4 `gfx1200`, PyTorch 2.9.1, Ubuntu 24.04
[official doc, https://rocm.docs.amd.com/en/docs-7.2.1/compatibility/compatibility-matrix.html,
2026-10-31]. AMD's Radeon WSL guide additionally requires removing
`libhsa-runtime64.so*` from `torch/lib` and `numpy<2`
[official doc, https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/wsl/legacywsl/install-pytorch.html,
2026-10-31]. (Our venv has numpy 2.5.4 and trains — noted as a deviation, not
a claim.)

**Established.** The current line is ROCm 10.1.0 (2026-08-26) with
`torch[device-gfx1200]==2.14.0+rocm10.1.0`, and it requires Windows 11 25H2
with Adrenalin 26.10.41.05 and Ubuntu 24.04.5/26.04.1
[official doc, https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html,
2026-10-31; install: https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html].
`HSA_ENABLE_DXG_DETECTION=1` is only needed before ROCm 7.13
[GitHub, https://github.com/ROCm/librocdxg/releases, 2026-10-31].

**Established. torch-directml cannot train this loss.** Newest PyPI artifact
is `0.2.5.dev240914` (2024-09-15) pairing with `torch==2.4.1+cpu`
[registry, https://pypi.org/project/torch-directml/, 2026-10-31]. The operator
roadmap lists `aten::gather` and `aten::scatter` **forward** plus
`index_select`/`index_put`/`masked_scatter_`, but **no** `gather_backward`,
`scatter_backward`, `take_along_dim` or `one_hot`
[wiki, https://github.com/microsoft/DirectML/wiki/PyTorch-DirectML-Operator-Roadmap,
2026-10-31]. DirectML's scatter contract requires indices to match input in
every dimension except the scatter axis
[official doc, https://learn.microsoft.com/en-us/windows/win32/api/directml/ns-directml-dml_scatter_operator_desc,
2026-10-31]; the binding's "DirectML scatter doesn't allow partially modified
dimensions" error is reproducible on `F.one_hot` and was closed **not planned**
[issue, https://github.com/microsoft/DirectML/issues/420, 2026-10-31]. A
search for the error string returns that single issue — **no documented
workaround** [issue search, https://github.com/microsoft/DirectML/issues?q=%22partially+modified+dimensions%22,
2026-10-31]. `torch.compile` has no documented DirectML backend
[official doc, https://docs.pytorch.org/docs/2.14/user_guide/torch_compiler/torch.compiler.html,
2026-10-31]. Separately, issue #740 reports `cross_entropy(reduction='none')`
plus manual weighting returning silent zero gradients on that version
[issue, https://github.com/microsoft/DirectML/issues/740, 2026-10-31] — which
is exactly the shape of a masked/weighted distill loss.

**Established. ONNX Runtime DirectML is inference-only.** The DML EP
"accelerat[es] inference of ONNX models" (DirectML 1.15.2, opset <= 20, no
memory pattern / parallel execution); the training build exposes kernels only
for CPU and CUDA
[official doc, https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html;
https://onnxruntime.ai/docs/build/training.html, 2026-10-31].

**Established (partial). CPU levers.** CPU Inductor is supported on Windows
from PyTorch 2.5 (needs MSVC or clang-cl/icx-cl)
[official tutorial, https://docs.pytorch.org/tutorials/unstable/inductor_windows.html,
2026-10-31]; a tutorial reports ~2.36x for Inductor CPU inference, training
gains are smaller [https://docs.pytorch.org/tutorials/intermediate/inductor_debug_cpu.html].
The 3900X is Zen 2: AVX2 only, **no AVX-512, no AMX**, so bf16 must be
emulated [vendor page, https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-3000-series/amd-ryzen-9-3900x.html,
2026-10-31]. **UNVERIFIED:** expected 1.2–1.6x training gain; no source
benchmarks this model shape.

### What this means here

> **Update 2026-10-31 (MEASURED — refutes the "likely no workaround" above).**
> `torch-directml==0.2.5.dev240914` + `torch==2.4.1+cpu` was installed on this
> machine and the gather-backward repro **does** fail with the historical
> message. On the same device, however, **flattened advanced indexing
> (`logits.reshape(-1,V)[row, id]`) and `torch.take_along_dim` both pass the
> backward**, and a full 2 000-step distillation run completes with
> `distill_impl=index` at about 1 step/s, tracking the CPU **training-loss** curve
> step-for-step (heldout ppl diverges by 2 % after 2 000 steps). `one_hot` still fails (`aten::eye` is unsupported on DML).
> The research pass flagged this workaround as "likely no fix"; that
> assessment is wrong. See `teacher-free-results.md` §5.

The prompt's premise ("DirectML getestet, Crash im Backward von `gather`")
is **confirmed as a platform limit** for the default loss, not a bug in our
loss: the backward form of partial-index gather/scatter is unsupported and
closed as not planned. Therefore:

- **Training backend = ROCm/WSL on the 9060 XT** (already working, 1.32
  steps/s measured with the real distill loss), and **DirectML is a usable
  second backend** with `distill_impl=index` (measured, §5 of the results).
- Do not use `distill_impl=gather` on DirectML; do not use `one_hot`.
- **CPU is the verification backend** (prompt requirement), GPU is the
  throughput backend.

---

## 6. Open items this research could not settle

1. Optimal KD temperature for this model — **UNVERIFIED**; test only if a
   variant is cheap.
2. Whether masking 15.3 % piece rows helps or hurts here — the literature
   warns masking can lose a lot; must be measured (V2).
3. Whether a corpus-unigram fill for the 9.38 % first-word rows beats leaving
   them out (V8).
4. Whether ROCm 10.1 raises throughput for this shape — no public benchmark;
   not worth re-validating inside a no-new-GPU session.
5. `k >= d+1` recovery condition for the teacher: teacher hidden size not
   checked here (irrelevant for teacher-free work, relevant if a re-pass is
   ever priced).
