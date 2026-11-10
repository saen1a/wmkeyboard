# Glide decoder experiment loop

Status of the remaining decoder work. Each card is a separate experiment; do not
retry a measured negative until the underlying index/model changes.

| Card | Status | Evidence |
|---|---|---|
| Host parity with the GNU DLL | **done** | `NativeGlideParityTest` 4/4 on the Windows GNU DLL after the platform-extension fix in `NativeEngine.hostLibrary()`; 338 s |
| Negative-results registry | **done** | `wmk-glide/experiments/negative.md` |
| Trie index A: follow-key mask | **negative** | mask builds correctly (431,586 nodes / 1.65 MiB / 52 ms) but the proposed `min follow remain` is not a lower bound; 4/5 paired losses, 287/2,588 pools changed; reverted. Sound variant must restrict the first next key inside `build_remain`. |
| Trie index B: subtree loop/pause mask | **deferred** | charge bound ≤ ~0.5 nat by design; no evidence of a material win |
| Trie index C: length-bucketed subtree max | **negative** | only 49 German / 2 English query-reachable nodes change; the shipped `n >= 48 > 32` makes the remaining-length bucket ask the same set; scalar `u16` 0.84 MiB (u32 1.65 MiB) is exact for the 32 cap; not worth implementing. |
| Sound A live bound | **negative** | instrumented 4.68% would-prune, but live top-1 0.7457→0.7419, top-8 0.8439→0.8400, 10/10 paired losses, 233/2,588 pools changed, CPU +10.8%, pops −0.34%; flag off and code reverted |
| Bound line | **exhausted** | A, sound A, C negative; B deferred; the measured gain is not in a tighter bound |
| New model/scoring path | **first slice measured — NO-GO as-is** | FUTO encoder/decoder + ExecuTorch 1.6 on 1,000 HeliBoard German a-z strokes; CTC 69.57/81.98 vs GlideBeam German profile 78.78/91.49 on the 999 in-list strokes; the toolchain/assets are unblocked, the gap is the English-trained model; card `wmk-glide/experiments/ctc-first-slice.md` |
| Multilingual audit | **done — English kept, fi/et/hu measured, five rejected** | `wmk-glide/experiments/multilingual-audit.md`: English small 17k +3.25 full / +4.9 hard slice; large listed-only +0.20 pp non-significant; FUTO swipe5 has zero fi/nl/sv/no/da/et/hu/tr strokes/layouts; bn_rom has model+list but no corpus/layout; safe defaults confirmed |
| Finnish profile | **GO — shipped, joins off** | HeliBoard `fi`, 1,000 single-finger a-z (seed 20261109, 12 geometries), `fi_aosp`: 0.75/2.0 reads 76.90/95.10 vs default 72.80/91.30; paired +4.10/+3.80 pp, CI [+2.70,+5.60]/[+2.70,+5.00]; a join run moved 0/1,000 and the app lexicon path is unmeasured, so joins stay off; card `wmk-glide/experiments/finnish-profile.md` |
| Estonian and Hungarian | **GO — shipped, joins off** | HeliBoard `et` (281 strokes, 2 geometries) and `hu` (436, 7), full alphabet, seed 20261109: Estonian 66.55/81.14 vs 57.30/72.95 (+9.25/+8.19, CI [+2.00,+10.82]); Hungarian 66.97/85.09 vs 62.39/81.42 (+4.59/+3.67, CI [+3.19,+8.11]); card `wmk-glide/experiments/estonian-hungarian-profile.md` |
| Danish, Dutch, Norwegian, Swedish, Turkish | **NO-GO — no row** | Same protocol: da -5.10 (CI [-7.62,0.00]); nl -0.50 (top-4 +0.20 only); nb -0.25; sv -1.10; tr +0.20 (CI crosses 0); do not copy a row |
| Android NDK CI / `.so` parity | **workflow added — unverified** | `.github/workflows/ci.yml` `native-engine`: host parity, NDK r29, three ABIs, APK/`.so` checksums; CI not run here |

### Model card decision

- Chosen path: **encoder-only CTC for German**, not a learned reranker or
  shape scorer. The English CTC is `.957` vs `.801` built-in; the FUTO encoder
  is layout-agnostic and needs no new training.
- First slice: 1,000 HeliBoard German a-z strokes, 76 geometries, seed
  20261109, `de_aosp`; FUTO encoder/decoder via `native/bench/futo-swipe/emit.py`
  and `ctc_glide_eval` bare, ExecuTorch 1.6.0+cpu.
- Result: CTC 69.57/81.98 against the GlideBeam German profile 78.78/91.49 on
  the 999 in-list strokes; **NO-GO as-is**. The toolchain and assets are
  unblocked; the next step is German training/fine-tuning, not a decoder swap.
- Leakage: the FUTO encoder was trained on FUTO's swipe dataset, so FUTO German
  `swipe-5` is not a clean test until its split is confirmed; HeliBoard was the
  independent first slice.
- **German `.wmlm` release identity:** canonical in `state.md` §2.7 and the
  upstream `data/de/de_context.md`. The published file is the G6P 90k
  (`4fe6…`, G7 PASS +0.73 vs 2M); the local `10,856,432` `e921…` is Phase 1;
  the local `plans/ship-candidate.md` **HOLD/+0.27** is the earlier strict rule
  (c) on the `10,856,352` source candidate. The operator decision is to ship
  the published G6P; do not mix the +0.27 and +0.73 harnesses. The CC BY-NC
  notice is in the app About data pack.
- **Context-aware German profile: implemented.** 0.75 without the model, 0.5
  with it; sentence-disjoint out-of-fold fixed 0.5 vs 0.75 is +1.20 pp top-1
  (42/11, p = 2.25e-5, cluster CI [+0.65,+1.78]); top-4 flat; English/mixed
  unchanged. The fair split is the first loop's decided card.
- Fallback card: compound-aware German WMLM scorer (observed compounds + WMLM
  pieces) — lower ceiling, no new runtime, first slice 118 oracle compound
  misses.

### Compounding profile cards

- `GlideLanguageProfiles.FINNISH`: 0.75 / 2.0, joins off (DEFAULT), no context
  model (glide blend 0.0, `freqWeightWithContext` inherits 0.75).
- `GlideLanguageProfiles.ESTONIAN` and `HUNGARIAN`: the same weights and join
  fields, no model; full alphabets, `et_full`/`hu_full` capped to 300,000 words.
- Measured on HeliBoard's gesture data (CC BY-SA 4.0), not copied from German;
  Finnish is 1,000 a-z strokes, Estonian 281 and Hungarian 436 full-alphabet
  strokes.
- A join run at 8 / 4 / 0.1 moved 0/1,000 on Finnish; the app's join path uses
  a different downloaded lexicon (`fi_full`), so joins stay off.
- Danish, Dutch, Norwegian, Swedish and Turkish measured no row: Danish
  regresses, Dutch moves top-4 only, the rest do not clear the paired top-1 CI.
  Do not copy a row.

### Upstream sync card

- Merged `github/main` `7b4f13a87` (151 commits) into the worktree without a
  merge commit. Conflicts were the launcher rows, voice strings, Arabic/Hebrew
  `release()`, `EmulatedWindows`, `WMKeyboardService` constant rename, docs
  package files, and the three `.so` binaries.
- Upstream glide changes now in the tree: `GlideOutcomes` corrections, a word
  learned from an apostrophe over a wrong glide, and Khipro's own spellings.
  `SuggestionEngine.kt` auto-merged with the context-aware German profile.
- Rebuilt `libwm_engine_jni.so` for arm64-v8a, armeabi-v7a and x86_64 from the
  merged source; all three export `glideTuningVersion` and `punctPredict`.

### CI card

- The `native-engine` job builds the host JNI for `NativeGlideParityTest`,
  builds the Android `.so` for `arm64-v8a` / `armeabi-v7a` / `x86_64` with NDK
  r29, verifies the ABI and `glideTuningVersion` export, assembles the APK, and
  uploads the APK/`.so` with `SHA256SUMS`.
- Not run here; the YAML/bash parse is green, the CI is unverified. The local
  host parity is green with the GNU DLL.

## Loop rule

`design → implement behind a flag (default off) → exactness/property tests →
measure on the fixed corpora → paired review → decide → record`.

Acceptance for a bound index: **identical top-k** and fewer pops/CPU. Acceptance
for a model: a held-out win, a fallback, a model size/licence, and on-device
latency.

## Fixed corpora

- German FUTO: 2,588 strokes; `de_swipes.jsonl`, `german.json`, `de_150k.txt`
  (and the AOSP/counted lists where relevant); **experiment baseline**
  `freq_weight=0.5 gap_weight=2.0` (the recorded negative-results baseline);
  the shipped German profile is 0.75/2.0, so rerun the baseline before
  comparing across tunings. Join 8/4/0.1; context `de_context.wmlm`.
- English FUTO: 26,523 strokes; `en_swipes.jsonl`, `qwerty.json`,
  `en_aosp_counts.txt`; default profile; `en_context.wmlm`.
- HeliBoard rare-word set: 10,908 strokes.
- Parity: `NativeGlideParityTest` against the Kotlin reference on the host
  library.

## Current production defaults

- Lift: 4,000 pops / 12,288 states. Preview: 2,000 / 8,192.
- Versioned JNI tuning envelope (`glideTuningVersion` 2; old 30/32 arrays
  accepted).
- Glide context blend: German 0.5/5.0 with pieces; English 0.7/3.0 small-list,
  0.5/5.0 listed-only large; Finnish off; default/mixed off.
- Profile rows: German (0.75/2.0, 0.5 with a model), English (shipped weights),
  Finnish, Estonian and Hungarian (0.75/2.0, joins off, no model); every other
  id uses `DEFAULT`.
- No research flags in the production tree: no `outlier_clamp`,
  `shape_floor_margin`, or `same_node` instrumentation.

## Open environment issues

- Android `.so` and the JVM parity inside the NDK build need a Linux CI runner
  with the NDK. Local Windows has no NDK and no MSVC `link.exe`; the GNU host
  DLL is the local parity path.
- The `.so` handshake is tested on the host; the Android ABI matrix is not.
