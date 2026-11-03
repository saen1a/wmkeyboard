# Ship candidate — `de_candidate_g6p_90k.wmlm`

Status: **HOLD under the strict ship rule (c)**; strong near-miss.
Gate: G7. Candidate: `wmk-glide/artifacts/models/de_candidate_g6p_90k.wmlm` (10,856,352 bytes; sha256 in the sidecar).
Checkpoint: `artifacts/out/runs/G6P/90k/best.pt`, step 88,000, heldout 4.0071 (final eval 4.0077).
Recipe: V9 word-aware alignment, `distill_alpha=0.3`, `distill_share=0.5`, no Piece mask, no weight, no fill,
90,000 steps on `de_lm_2m`, batch 256, ctx 40, d 256, L6, H4, ff768, seed 0.

## Heldout / ppl

| Model | heldout | step |
|---|---:|---:|
| **G6P 90k** | **4.0071** | 88,000 |
| shipped `de_context_2m` | 4.1913 | 76,000 |
| shipped `de_context_1m2` | 4.3150 | 30,000 |
| shipped `de_context_4b150k` | 4.3238 | 21,000 |

The candidate is **0.1842 nats better** than the shipped 2M. This is the largest heldout gain of the
session (G1 −0.164 → G2 −0.138 → G5′ −0.051 → G6′ 60k −0.071 → G6′ 90k −0.184 vs the shipped 2M).

## Paired Glide (n=2,588, `blend_top1`)

| Pair | acc A | acc B | Δ | 95% CI | exact p | Holm (6) |
|---|---:|---:|---:|---|---:|---|
| 90k vs 2M | 0.7875 | 0.7848 | **+0.27 pp** | [−0.27, +0.81] | 0.410103 | rank 5, no |
| 90k vs 1.2M | 0.7875 | 0.7794 | **+0.81 pp** | [+0.31, +1.35] | 0.003802 | rank 3, **reject** |
| 90k vs 150k | 0.7875 | 0.7848 | +0.27 pp | [−0.31, +0.85] | 0.427043 | rank 6, no |

## Paired typing (n=2,000, `lm_nextword_top1`)

| Pair | acc A | acc B | Δ | 95% CI | exact p | Holm (6) |
|---|---:|---:|---:|---|---:|---|
| 90k vs 2M | 0.1725 | 0.1565 | **+1.60 pp** | [+0.65, +2.55] | 0.001790 | rank 2, **reject** |
| 90k vs 1.2M | 0.1725 | 0.1525 | **+2.00 pp** | [+0.95, +3.10] | 0.000293 | rank 1, **reject** |
| 90k vs 150k | 0.1725 | 0.1600 | +1.25 pp | [+0.15, +2.35] | 0.031409 | rank 4, no |

Holm family = the 3 Glide + the 3 typing tests; the three rejections above are the only ones.

## Typing strip (n=2,000, `lm_strip_top1`)

| Pair | acc A | acc B | Δ | 95% CI | exact p |
|---|---:|---:|---:|---|---:|
| 90k vs 2M, full set | 0.6750 | 0.6665 | **+0.85 pp** | [+0.10, +1.60] | 0.039617 |

Per-register slices (candidate vs 2M, `lm_strip_top1`):

| Slice | 90k | 2M | Δ | exact p |
|---|---:|---:|---:|---:|
| chat (n=2,000) | 0.7325 | 0.7205 | **+1.20 pp** | 0.002670 |
| news (n=2,000) | 0.6620 | 0.6520 | **+1.00 pp** | 0.022463 |

The per-register mean is **+1.10 pp**; no slice is degraded. The full-set point is **+0.85 pp**,
0.15 pp below the strict 1.0 pp bar.

## Ship rule (plan §2, G7)

- (a) Glide CI lower > 0: **no** (CI lower −0.27 pp).
- (b) ppl better by ≥0.1 with Glide CI lower ≥ −0.5: **yes** (+0.1842 nats; CI lower −0.27 pp).
- (c) typing stripped mean ≥1 pp, strip top1 not lower by >0.5 pp, no per-register slice degraded >1 pp:
  - full-set strip +0.85 pp → **misses the 1.0 pp bar by 0.15 pp**;
  - per-register mean +1.10 pp, chat +1.20, news +1.00, no degradation → passes the mean/slice intent.

**Decision: HOLD.** The candidate is non-inferior on Glide, significantly better on typing next-word,
and 0.184 nats better on heldout; the only failed criterion is the strict full-set strip point,
by 0.15 pp, while the per-register mean clears the bar. The typing harness itself is biased:
8.68% of heldout word tokens (umlauts/ß) are never scored and the harness uses QWERTY/`en`
(`plans/student-quality-audit.md`, H5). Do not ship on a 0.15 pp miss of a biased secondary metric
without a decision from the operator; the candidate is the best local model and a re-test with a
German typing harness (or a 0.15 pp strip gain) is the clean path.

## Next

1. Fix the typing harness (ASCII/umlaut filter, German layout/seeds) and re-run G7's typing and
   per-register slices; if the strip delta holds ≥1 pp, the candidate ships under (b)+(c).
2. The prepared student-v2 90k (`train_v2.py`, kdweight 0.1 on Piece rows, EMA 0.999) was requested
   by the peer/operator but **not started**: the session budget is 58.36/72 GPU-h and v2 adds ~19.3 h
   (~77.7 h total), and peer approval is not direct user authorization. It needs the operator's
   explicit 78 h exception.
3. G8 (local 9B contract test) remains blocked until G7 ships or the operator accepts the hold.
4. Licence: the 2M mix includes 301,703 OpenSubtitles rows (15.1%) under CC BY-NC-style terms;
   resolve before any commercial ship.

Budget: **58.36 / 72 GPU-h**; 13.64 h left. G7 is CPU/typing only; no new GPU training was started.
