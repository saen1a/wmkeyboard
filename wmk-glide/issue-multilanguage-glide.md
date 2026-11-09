# [FEAT]: Per-language glide profiles: context-aware German, English list-size split, and Finnish

> Draft prepared from the repository's
> [feature_request.yml](https://github.com/wasi-master/wmkeyboard/blob/main/.github/ISSUE_TEMPLATE/feature_request.yml).
> Prototype code and measurements are on the `glide-engine` branch of the
> [`saen1a/wmkeyboard` fork](https://github.com/saen1a/wmkeyboard/tree/glide-engine).
> This is a feature request, not a pull request: the remaining language rows
> need their own measured strokes before they should ship.

## Description

Glide decoding currently uses one set of weights for every language. That set
was fitted on English, and two of its weights are a property of the language and
its word list rather than of the hand: how much a word's frequency counts
against the stroke's shape (`freqWeight`) and how dearly a detour between two
keys is charged (`gapWeight`). German's useful words are rare in every list
(median rank 20,714 in a 150k list, against 369 for the English words people
swipe), so an English frequency weight outvotes the shape for German. No single
value wins both languages: on 2,129 English strokes the German-style profile
costs about one point (81.49 % → 80.41 %).

The prototype therefore makes the weights **per language**, makes the glide
context blend **per language and list size**, and adds the first compounding row
measured on its own strokes: **Finnish**. German becomes **context-aware**
(0.75 without a model, 0.5 with one); English keeps the decoder defaults but
uses a different blend for its small bundled list and its large AOSP list; every
unmeasured language and every mixed-language field keeps the shipped weights
and no blend. A profile only moves weights no setting reaches, so the user's
radii and marks stay theirs.

The request is to adopt the policy and the measured rows, and to run the same
protocol for the remaining compounding languages before adding rows for them.

## Additional Information

### Decisions and why we chose them

#### 1. Per-language profile, not a new global default

- **Chosen:** `GlideLanguageProfiles` rows for `de`, `en`, `fi`; `DEFAULT` for
  everything else.
- **Rejected:** changing `GlideBeam.Tuning` defaults. A German fit costs English
  about a point, and an English fit leaves the German compounds unfixed.
- **Rejected:** asking the user to tune by hand. The useful values are a
  property of the language, not of the user's hand.
- The profile touches `freqWeight`, `gapWeight`, the join fields and the blend
  fields only. It never changes `startRadius`, `endRadius`, `nearRadius`,
  `vocabularyRank` or the marks, so a profile switch does not undo a user's
  tuning.
- **Code:** [`GlideLanguageProfiles.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/gesture/GlideLanguageProfiles.kt),
  [`GlideLanguageProfilesTest.kt` (core)](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/test/java/com/wasimaster/wmkeyboard/core/gesture/GlideLanguageProfilesTest.kt),
  [`GlideLanguageProfilesTest.kt` (app)](https://github.com/saen1a/wmkeyboard/blob/glide-engine/app/src/test/java/com/wasimaster/wmkeyboard/core/gesture/GlideLanguageProfilesTest.kt).

#### 2. German is context-aware: 0.75 without the model, 0.5 with it

- **Measured:** 2,588 FUTO German strokes, AOSP German list, the published G6P
  90k `de_context.wmlm`, shipped join guard (8 nats / 4 letters / 0.1), blend
  0.5 / 5.0 with unlisted candidates spelled:

  | Weight | Decoder top-1 / top-4 | After blend top-1 / top-4 |
  |---:|---:|---:|
  | 0.75 | 81.34 / 87.60 | 81.68 / 87.56 |
  | 0.5 | 80.76 / 87.21 | **82.88 / 87.71** |

- **Held-out check:** a sentence-disjoint 5-fold split on the same strokes put
  fixed 0.5 over 0.75 by **+1.20 pp** top-1 (42/11 paired, p = 2.25e-5, cluster
  CI [+0.65, +1.78]); top-4 was flat.
- **Why context-aware rather than one fixed value:** the context model supplies
  a second signal for the words frequency was outvoting, so the stroke can lean
  further on shape. No-model users would lose if 0.5 were unconditional; a
  fixed 0.75 leaves the model-assisted gain on the table. The profile therefore
  selects `freqWeightWithContext` only when a model is actually reading the
  stroke.
- **Why the AOSP result is not copied to the counted list:** on the 1.15M
  counted list the 0.5 decoder already reads 79.40 % and the blend is neutral;
  the 0.5-with-model gain is AOSP-specific.
- **Code:** [`SuggestionEngine.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/SuggestionEngine.kt)
  (`contextModelField`, `retuneGlideForContext`, `blendGlideContextModel`),
  commit [`2d01546fa`](https://github.com/saen1a/wmkeyboard/commit/2d01546fa),
  fair-split record [`fafd6c19a`](https://github.com/saen1a/wmkeyboard/commit/fafd6c19a).

#### 3. English splits by list size

- **Small bundled list (17,306 words):** 0.7 / 3.0 with pieces. 77.10 / 82.29
  against 73.86 / 81.85 without the blend (+3.25 pp top-1; 1,329/468 paired,
  p = 2.8e-95). The original 2,129/1,824 hard slice reproduces +4.77.
- **Large AOSP list (160,668 words):** 0.5 / 5.0 on **listed candidates only**
  above `GLIDE_LM_BLEND_LIST_LIMIT = 50,000`. 80.74 / 88.50 against
  80.55 / 88.50 without it: paired +0.20 pp, CI [-0.05, +0.44], p = 0.121.
  This is **non-negative, not a proven gain**, at no piece pass.
- **Rejected:** pieces on the large list. It reads 79.69 / 87.72, a regression;
  spelling unlisted candidates reads 79.57 / 87.83. The large list is not the
  small list, and the two are not interchangeable.
- **Why the size class lives on the word source:** `WordSource.wordCount`
  selects the path; `PackedTrie` counts once, `MappedTrie` reads the file
  header, and `CompositeWordSource` sums its members. No per-stroke check.
- **Code:** [`SuggestionEngine.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/SuggestionEngine.kt),
  commit [`429985bab`](https://github.com/saen1a/wmkeyboard/commit/429985bab)
  (opt-in per language and size), [`5328c6d8c`](https://github.com/saen1a/wmkeyboard/commit/5328c6d8c)
  (listed-only), [`1ae980fa9`](https://github.com/saen1a/wmkeyboard/commit/1ae980fa9)
  (qualified result).

#### 4. Keep the BOS/empty-context blend; no global guard

- Both the maintained harness and the app blend on an empty context, so the
  measured English numbers already include first-word strokes. 2,650/26,523
  (10.0 %) are `word_idx=0`.
- On that subset, the 160,668 large list loses **0.72 pp** (p = 0.020), the
  17,306 small list is neutral, and German gains **2.11 pp** (p = 0.07, CI
  [+0.35, +4.23]) on its 2,588 strokes.
- **Decision:** keep the blend. A global empty-context guard would cost German
  more than it recovers in English. If the English large first word is worth
  polishing later, scope it to that profile row rather than guarding globally.
- **Correction:** the earlier claim that the harness skipped 10 % of strokes
  came from the old research copy
  [`wmk-glide/experiments/glide_lm_blend_eval.rs`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/wmk-glide/experiments/glide_lm_blend_eval.rs).
  It now blends on empty context like the maintained
  [`native/wm-engine/examples/glide_lm_blend_eval.rs`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/native/wm-engine/examples/glide_lm_blend_eval.rs).

#### 5. Finnish: the first compounding row, with joins off

- **Data:** HeliBoard Finnish gesture data, CC BY-SA 4.0; three archives
  (`batch_1` 566,713 B / SHA-256 `b2f38eed…`, `batch_2` 142,970 B /
  `00f1eaf6…`, `batch_3` 1,182,232 B / `b74a7e49…`). 1,000 single-finger a-z
  strokes, seed 20261109, 12 keyboard geometries, HeliBoard `fi` layout
  (`COLS=11`), app-preferred `fi_aosp` list (223,363 words / 1,093,376 B /
  SHA-256 `94cc5802…`). No Finnish context model.
- **Result:** default 72.80 / 91.30 → 0.75 / 2.0 reads **76.90 / 95.10**;
  paired **+4.10 / +3.80 pp**, cluster CI [+2.70, +5.60] / [+2.70, +5.00].
  The counted `fi` list agrees with the a-z slice.
- **Joins:** a German-style join run (8 nats / 4 letters / 0.1) moved
  **0 of 1,000** outcomes. The app resolves joins through a separate downloaded
  compound lexicon (`fi_full`, 2,488,573 words / 10,584,625 B), which this
  slice did not exercise. Enabling joins would also trigger that ~10.58 MB
  download for gesture users and run an unmeasured path.
- **Decision:** ship the Finnish row with **joins off** (`joinCost` stays
  infinite, `joinMinPart` 3, penalty 0.0). The measured gain comes from
  frequency and gap; the join evidence is neutral, not positive. Enabling
  joins needs a run against the app's `fi_full` lexicon, not the a-z slice.
- **Why not copy German:** the German joins are backed by 2,588 German strokes,
  including a rare-word set; Finnish's a-z slice cannot validate long compounds
  or the downloaded lexicon. The row is measured, the join setting is not.
- **No model:** `glideLmBlend = 0.0`; `freqWeightWithContext` inherits 0.75.
- **Regression guard:** `CompoundLexiconTest` now asserts
  `CompoundLexiconDownloads.supports("fi") == false`, so adding the row cannot
  silently start the 10.58 MB download.
- **Code:** [`GlideLanguageProfiles.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/gesture/GlideLanguageProfiles.kt),
  [`CompoundLexiconTest.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/app/src/test/java/com/wasimaster/wmkeyboard/core/dictionaries/CompoundLexiconTest.kt),
  measurement card [`wmk-glide/experiments/finnish-profile.md`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/wmk-glide/experiments/finnish-profile.md),
  commit [`52633aee8`](https://github.com/saen1a/wmkeyboard/commit/52633aee8).

#### 6. Default, mixed and unmeasured languages keep the safe path

- Every id without a row resolves to `DEFAULT` (freq 1.0, gap 1.33, joins off,
  glide blend 0.0). A zero blend returns the decoder order.
- Mixed-language lists use `DEFAULT`: the profiles were measured on one list
  alone, and halving frequency lets rare English words take German strokes
  (#1051).
- The typing blend is unchanged; this issue only changes the glide path.

#### 7. Budgets and the versioned JNI envelope

- Preview: 2,000 pops / 8,192 states. Lift/final: 4,000 / 12,288, including
  the single and duet preview paths. On German, 4,000 / 12,288 against
  2,000 / 8,192: AOSP 81.07 → 81.22 top-1 and 88.60 → 88.91 top-64; counted
  75.46 → 76.31 and 86.36 → 87.75.
- The JNI tuning envelope is `glideTuningVersion` 2 with 34 slots. Old 30/32
  arrays are still accepted; Kotlin sends the versioned 34 only when the
  symbol exists.
- **Why a handshake:** a stale `.so` must ignore new slots rather than
  misread them, and the per-decode budgets need the native side to agree. The
  committed `.so` for all three ABIs exports `glideTuningVersion`.
- **Code:** [`NativeGlide.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/NativeGlide.kt),
  [`NativeEngine.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/language/src/main/java/com/wasimaster/wmkeyboard/core/engine/NativeEngine.kt),
  commit [`753ee00f6`](https://github.com/saen1a/wmkeyboard/commit/753ee00f6),
  JNI rebuild [`c516b0e95`](https://github.com/saen1a/wmkeyboard/commit/c516b0e95),
  CI gate [`8c1debbb4`](https://github.com/saen1a/wmkeyboard/commit/8c1debbb4).

#### 8. Source and LM score caches

- `walkSources` is keyed by the source `generation` plus
  `userLexicon.mutationCount()`, so a multi-frame preview reuses the walk until
  a source or the user lexicon actually changes.
- The context LM score cache is per decode: 83.48 ms cold, 9.12 µs on the
  second ask; a 10-frame pool reads 52.33 ms against 809.44 ms with a fresh
  context per frame (15.5×).
- **Why:** preview frames repeat the same pool and context; caching them is
  pure work removal, not a scoring change.

#### 9. Measurement protocol and limits

- Harness: `native/wm-engine/examples/glide_beam_eval.rs` with `ALL=1`,
  `RESULTS=4` for top-4, `COLS` set to the layout, `STATS=1`; the blend
  harness is `glide_lm_blend_eval.rs`.
- `RESULTS=4` matters: the harness prints `top{RESULTS}` and counts a hit
  anywhere in the returned candidates. A `RESULTS=8` run prints top-8; it
  cannot produce the top-4 column. The Finnish card records the `RESULTS=4`
  command.
- German uses sentence-disjoint 5-fold splits; Finnish uses a fixed 1,000-stroke
  slice with a seed; both report paired or cluster CIs.
- **Limits:** Finnish is a-z only (no `ä`, `ö`, `å`, punctuation or
  dual-finger), a community corpus, and a written list rather than a counted
  corpus. The derived slice is session-local; the source archives are
  identified by hash in the card. On-device latency was not re-measured for
  Finnish; the row only moves frequency and gap and activates no join or
  lexicon path.

### Prototype status

- German context-aware profile: **implemented** and tested.
- English small/large split: **implemented**; the large result is documented as
  non-negative, not proven.
- BOS blend: **kept**; the stale harness claim is corrected.
- Finnish: **implemented** with joins off; the join path remains open.
- Default and mixed: **safe default**; no row and no blend.
- Budgets, versioned tuning, source cache, LM score cache: **implemented**.
- Android `.so`: rebuilt for `arm64-v8a`, `armeabi-v7a`, `x86_64` from the
  merged source; `glideTuningVersion` and the smart-punctuation exports are
  present.
- Upstream `github/main` `7b4f13a87` is merged into the branch (151 commits);
  the upstream glide fixes (`GlideOutcomes` corrections, apostrophe learning,
  Khipro spellings) are included. One upstream test needed a test-only
  adjustment: its `-2` hand adjustment predates the new 4-nat taught lift, so
  the test now uses `-5`. Production behavior is unchanged.

### Code links (fork, `glide-engine` branch)

- Branch: [`saen1a/wmkeyboard@glide-engine`](https://github.com/saen1a/wmkeyboard/tree/glide-engine)
- Merge commit: [`95a248b0f`](https://github.com/saen1a/wmkeyboard/commit/95a248b0f)
- Finnish/BOS commit: [`52633aee8`](https://github.com/saen1a/wmkeyboard/commit/52633aee8)
- Profile registry: [`GlideLanguageProfiles.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/gesture/GlideLanguageProfiles.kt)
- Engine blend and tuning: [`SuggestionEngine.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/SuggestionEngine.kt),
  [`NativeGlide.kt`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/NativeGlide.kt)
- Rust decoder: [`native/wm-engine/src/glide/`](https://github.com/saen1a/wmkeyboard/tree/glide-engine/native/wm-engine/src/glide)
- Harnesses: [`glide_beam_eval.rs`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/native/wm-engine/examples/glide_beam_eval.rs),
  [`glide_lm_blend_eval.rs`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/native/wm-engine/examples/glide_lm_blend_eval.rs)
- Measurements: [`finnish-profile.md`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/wmk-glide/experiments/finnish-profile.md),
  [`multilingual-audit.md`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/wmk-glide/experiments/multilingual-audit.md)
- Docs: [`languages-and-engines.mdx`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/docs/src/content/docs/development/glide-engine/languages-and-engines.mdx),
  [`decisions.mdx`](https://github.com/saen1a/wmkeyboard/blob/glide-engine/docs/src/content/docs/development/glide-engine/decisions.mdx)

### Verification already run

- Rust: `cargo test --release --locked` — 527 passed, 3 ignored (plus the
  harness suites 3 / 7 / 4).
- Kotlin: profile tests 9/9 (core), 7/7 (app), compound lexicon 3/3; upstream
  glide tests `GlideOutcomesTest` 12/12, `GlideSavedApostropheWordTest` 4/4,
  `GlideOutcomeRerankTest` 7/7.
- `:app:assembleIntlDebug` succeeds; the embedded arm64 `.so` SHA-256 matches
  the rebuilt source and exports `glideTuningVersion` and `punctPredict`.
- Docs: 318 pages, all internal links valid.

### Open questions / proposed checklist

- [ ] **Dutch, Swedish, Norwegian, Danish, Estonian, Hungarian, Turkish:** one
      1,000-stroke HeliBoard run each; add a row only on a paired CI lower
      bound above 0. Do not copy Finnish's row.
- [ ] **Finnish joins:** run against the app's `fi_full` compound lexicon before
      enabling `joinCost`; the a-z slice moved 0/1,000 and cannot decide it.
- [ ] **Banglish (`bn_rom`):** a published model but no stroke corpus or layout
      in FUTO or the HeliBoard data; keep the glide blend off until measured.
- [ ] **German CTC:** still blocked on ExecuTorch, the encoder/decoder assets,
      the HeliBoard German zst, the two conversion scripts and a pinned
      baseline.
- [ ] **Native CI and on-device latency:** the `native-engine` job and the
      Android ABI matrix have not run in this environment; the Finnish row was
      not re-measured on a phone.

### Why this is a feature request rather than a bug

The prototype fixes a measured English regression and keeps the German gain,
but the remaining language rows are per-language weight decisions that need
real strokes and a held-out protocol. Shipping any of them without that
evidence would repeat the earlier mistake of applying a German fit to every
language.
