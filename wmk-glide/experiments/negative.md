# Glide decoder negative results

Measured on the fixed corpora; commands in `loop.md`. Do not retry a card
unless the index/model it was testing changed. Environment: WSL Rust 1.96
GNU, release example; German FUTO 2,588 strokes, `COLS=11`, `ALL=1`,
`THREADS=8`, `RESULTS=8`, `STATS=1`, `de_150k.txt`, `german.json`,
`freq_weight=0.5 gap_weight=2.0 max_pops=4000 max_states=12288` unless noted.

## 1. Plain-word dominance — no gain

- Instrumented accepted pushes with a per-source node map.
- `same_node == 0` on all 2,588 strokes at both 2,000/8,192 and 4,000/12,288.
- A trie node is the word prefix; each state pushes each child once from a
  unique parent. There are no duplicate node states to dominate.
- Joined decodes do re-push the root (`same_node/pushes = 0.7627` with
  `join_cost=0.1 join_min_part=3`), but the same root is reached under
  different earlier parts; componentwise `cols + extra` is not sound without
  the concatenated prefix identity. Not implemented.
- Instrumentation removed; no production field.

## 2. Cheap bound tightening from existing data — none

- The column term `F(s)` is already the exact min over unconstrained
  continuations (`remain` is exact over the near-key set).
- `lmcap(P, M(child))` is the exact subtree frequency maximum; the join bound
  is exact for the new part.
- Dwell/loop charges are non-negative and omitted (safe). Start/end slack is
  already inside `point_cost`/`remain`; `terminal_cost` is only valid at emit.
- Admissibility holds for `shape_weight`, `freq_weight`, `join_cost`,
  `join_part_penalty >= 0`; the condition is not enforced in `Tuning`.
- The remaining exact ideas need new trie indexes: subtree key mask,
  loop/pause mask, length-bucketed subtree max.

## 3. 8,000-pop sweep — 4,000 is the knee

| Pops / states | Top-1 | Top-8 | Mean pops | Mean read | States | Saturated |
|---|---:|---:|---:|---:|---:|---:|
| 2,000 / 8,192 | 0.7415 | 0.8393 | 784 | 33.3 | 1,594 | 0 |
| 4,000 / 12,288 | 0.7457 | 0.8439 | 1,106 | 35.4 | 1,947 | 0 |
| 8,000 / 12,288 | 0.7465 | 0.8451 | 1,455 | 36.8 | 2,209 | **92** |

8,000 buys +0.08 top-1 / +0.12 top-8 for +32 % pops and starts saturating the
12,288-state frontier. Keep 4,000 / 12,288 for the lift, 2,000 / 8,192 for
preview.

## 4. Shape-aware floor margin — not worth it

The raw k-th floor is not sound for the shape-ranked final score; the shape
penalty can move a candidate by up to `2 * shape_channel` (12 nats at 6).
Measured margin:

| `shape_floor_margin` | Top-1 | Top-8 | Mean pops | Mean read | Paired top-1 | Paired top-8 |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 0.7457 | 0.8439 | 1,106 | 35.4 | — | — |
| 6 | 0.7457 | 0.8451 | 1,842 | 115.6 | 0 / 0 | +3 / 0 |
| 12 | 0.7457 | 0.8451 | 2,346 | 215.9 | — | — |
| 18 | 0.7457 | 0.8451 | 2,640 | 277.8 | — | — |

The concern is real but immaterial: 3 top-8 placements out of 2,588, no top-1,
+67 % pops, +227 % read. Keep the field off and out of production.

## 5. Outlier clamping — negative

Multiples of the median step, before `resample`:

| `outlier_clamp` | Top-1 | Top-8 | Paired top-1 | Paired top-8 |
|---|---:|---:|---:|---:|
| 0 | 0.7457 | 0.8439 | — | — |
| 2.5 | 0.7315 | 0.8308 | — | — |
| 3 | 0.7392 | 0.8373 | — | — |
| 4 | 0.7434 | 0.8408 | — | — |
| 5 | 0.7442 | 0.8416 | net −4 | net −6 |

Rejected; field removed.

## 6. DSP/pre-processing — only exact cleanup remains

- Exact: removing consecutive samples with identical `(x, y, t)`; zero-length
  segments contribute no arc and keep the timestamp. Cleanup, not accuracy.
- Needs a fit, no evidence: moving-average/Savitzky-Golay smoothing, adaptive
  or curvature-based resampling, duplicate `(x,y)` with different `t`
  (destroys dwell), curvature/velocity features, DTW-like shape terms.
- The current pipeline already applies a DSP-like stack: uniform arc-length
  resampling, Gaussian point costs, near-key masks, gap charge, dwell, loop
  collapse, shape normalisation and mean L2.
- SIMD/NEON: `band::min_arc` is a kernel; `build_costs`/`advance`/shape are
  branchy. The decoder is ~16.8 ms CPU/stroke while the context blend is
  ~20 ms; the ceiling is the search, not the arithmetic.

## 7. Production guard

- No `outlier_clamp`, `shape_floor_margin`, or `same_node` instrumentation is
  in the production tree.
- `GlideTuningBudgetTest` pins the 4,000/12,288 defaults and the 32-value
  tuning array.
- `NativeGlideParityTest` passes 4/4 on the GNU host DLL after
  `NativeEngine.hostLibrary()` prefers the platform extension.
- Any future loop that wants to revisit a card must first change the
  underlying index/model and update this file.

## 8. Trie index A: follow-key mask — negative (formula not admissible)

The design card proposed a per-node `follow` key mask and a bound term
`min_{k in follow} remain[j,k]`. The mask itself builds correctly, but the
formula is **not a lower bound** and fails exactness:

- `remain[j,k]` is the cost of the suffix **after** key `k` is placed at sample
  `j`, not the cost of consuming `k` as the next letter after the current key.
  Minimising it over the child's followers can exceed the true continuation,
  so the bound over-prunes.
- The mask build is sound (layout-dependent, one `u32`/node; no `.wmdict`
  change): German 150k 431,586 nodes, 1,726,344 B, 52.379 ms build
  (69.408 ms single-thread).
- The full read changed: 287 of 2,588 pools differ, with 35 top-1 changes.

Measured German FUTO 2,588, 4,000/12,288, `freq_weight=0.5 gap_weight=2.0`:

| | MASK_BOUND=0 | MASK_BOUND=1 |
|---|---:|---:|
| Top-1 | 0.7457 | 0.7442 |
| Top-8 | 0.8439 | 0.8420 |
| Mean / max pops | 1,105.5 / 4,000 | 1,130.7 / 4,000 |
| Mean / max read | 35.4 / 108 | 39.5 / 144 |
| Mean states | 1,947.0 | 2,047.2 |
| Saturated | 0 | 1 |
| Paired top-1 | — | 0 wins / 4 losses |
| Paired top-8 | — | 0 wins / 5 losses |
| Pool equality | — | 2,301 / 2,588 |

The mask build is 4 B/node; 1.65 MiB German / 159 KiB English; the layout
dependence is real (29 German keys, 26 English keys). Lifting the state cap to
100,000 removes saturation but top-1 stays 0.7442, so the loss is the formula,
not the cap. The prototype was reverted; no production flag, no `.wmdict`
change.

Sound variant (not yet designed): restrict the **first next key** inside the
`build_remain` transition min (or store per-first-key remainders), which is a
different, more expensive bound. The mask index can be reused; the formula
cannot. Next candidate is the length-bucketed subtree max (index C), which is
layout-independent and has a simpler admissibility proof.

## 9. Trie index C: length-bucketed subtree max — negative

The sound index is nearly empty on the shipped lists. With
`MAX_WORD_LENGTH = 32` and `SHORT_SAMPLES = 48`, the sample count `n` is always
≥48, so the only binding length constraint is the absolute 32-letter cap (and
the 2-letter floor). The remaining-length bucket therefore asks the same set
at every node, and the exact answer is one scalar per node, not a bucket array.

Measured from the fixed lists with joiner-aware walk length:

| List | Nodes | Query-reachable nodes where `V != max_subtree` | Where | Max bound drop |
|---|---:|---:|---|---:|
| German 150k | 431,586 | **49** | 23 depth-1 one-letter/punctuation heads; 26 on the 34-letter `supercalifragilisticexpialigetisch` branch (freq 13) | 1.84 nats |
| English bundled | 40,737 | **2** | `a`, `i` depth-1 | 0.017 / 0.035 nats |

- The two German nodes at depth 33/34 are never queried (`length >= 32` stops).
- One scalar `u16` is 0.84 MiB German / 80 KiB English; the six-bucket form is
  4.94 MiB / 477 KiB. The `u32` scalar is 1.65 MiB German.
- The frequency term is not the dominant loose term; the column/shape term is.
- No implementation slice was written. Do not implement index C unless a
  cheap confirmation run shows a surprising pop delta; the static bound is
  confined to 0.011% of German nodes and 2 English nodes.

Next: instrument the **sound A variant** (first-next-key restriction inside
`build_remain`) and count the states/pops it would prune before implementing
it. If that count is not material, the bound line is exhausted and the next
levers are the data/model work and the Android `.so`/NDK parity.

## 10. Sound A (first-next-key `remain`) live bound — negative

The instrumentation looked material: 216,346 would-prune pushes (4.68% of
pushes, ~7.56% of pops), prune-drop mean 3.0872 nats. The live search behind
`SOUND_A=1` did **not** reproduce a win:

| Metric | `SOUND_A=0` | `SOUND_A=1` |
|---|---:|---:|
| Top-1 | 0.7457 | 0.7419 |
| Top-8 | 0.8439 | 0.8400 |
| Mean / max pops | 1,105.5 / 4,000 | 1,101.7 / 4,000 |
| Mean / max read | 35.4 / 108 | 38.6 / 116 |
| Mean states | 1,947.0 | 1,980.7 |
| Paired top-1 | — | 0 wins / 10 losses |
| Paired top-8 | — | 0 wins / 10 losses |
| Pool equality | — | 2,355 / 2,588 |
| Single-thread CPU | 29.43 s | 32.60 s (+10.8%) |

- The "would-prune" count was misleading: the all-push bound-drop mean was
  **−1.6963** nats, i.e. the sound bound is on average looser than `min_col`,
  while it still prunes a tail. The `first[j,to]`/`remain[j,key]` derivation is
  not consistently below `min_col`; the zero-rest `can_emit || can_end` option
  and the open-tail look-ahead merge also changed output.
- Pops fell only 0.34%, CPU rose 10.8%; the mask build is 42–44 ms and
  1.65 MiB per German source. Not shippable.
- Flag left off; the research mask/first code was reverted; no production
  `Dict`/`PackedTrie` mask index is recommended on this evidence.
- The bound line is now exhausted:
  - follow-key mask: negative (non-admissible formula);
  - sound first-next-key mask: negative (live);
  - length-bucketed subtree max: negative (49/2 nodes);
  - loop/pause mask: deferred; the charge bound is ≤ ~0.5 nat by design, so
    there is no evidence for a material win.

Next levers: the data/LM/model path and the Android `.so`/NDK parity, not
another bound index on the current state.


