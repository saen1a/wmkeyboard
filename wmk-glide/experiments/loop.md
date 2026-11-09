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
| New model/scoring path | **design done — encoder-only CTC for German** | FUTO `honorable_sturgeon` encoder only; generalize `ctc.rs` from 27 classes to `key_count + 1`; first slice 1,000 HeliBoard a-z strokes; built-in baseline 21.95 %; go signal ≥30 %; FUTO training-data leakage keeps the first slice off FUTO German |
| Android NDK CI / `.so` parity | **workflow added — unverified** | `.github/workflows/ci.yml` `native-engine`: host parity, NDK r29, three ABIs, APK/`.so` checksums; CI not run here |

### Model card decision

- Chosen path: **encoder-only CTC for German**, not a learned reranker or
  shape scorer. The English CTC is `.957` vs `.801` built-in; the FUTO encoder
  is layout-agnostic and needs no new training.
- First slice: 1,000 HeliBoard German a-z strokes, generic 26-key CTC beam
  (`ctc.rs` currently hardcodes 27 classes), `de_150k`; baseline built-in
  21.95 % on the full HeliBoard set; go at ≥30 % with CI lower > 0.
- The first slice is **not implemented**; the encoder-only scripts and the
  generic-class example do not exist yet.
- Leakage: the FUTO encoder was trained on FUTO's swipe dataset, so FUTO German
  `swipe-5` is not a clean test until its split is confirmed; HeliBoard is the
  independent first slice.
- **German `.wmlm` release identity:** canonical in `state.md` §2.7 and the
  upstream `data/de/de_context.md`. The published file is the G6P 90k
  (`4fe6…`, G7 PASS +0.73 vs 2M); the local `10,856,432` `e921…` is Phase 1;
  the local `plans/ship-candidate.md` **HOLD/+0.27** is the earlier strict rule
  (c) on the `10,856,352` source candidate. The operator decision is to ship
  the published G6P; do not mix the +0.27 and +0.73 harnesses. The CC BY-NC
  notice is in the app About data pack.
- Fallback card: compound-aware German WMLM scorer (observed compounds + WMLM
  pieces) — lower ceiling, no new runtime, first slice 118 oracle compound
  misses.

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
  0.5/5.0 listed-only large; default/mixed off.
- No research flags in the production tree: no `outlier_clamp`,
  `shape_floor_margin`, or `same_node` instrumentation.

## Open environment issues

- Android `.so` and the JVM parity inside the NDK build need a Linux CI runner
  with the NDK. Local Windows has no NDK and no MSVC `link.exe`; the GNU host
  DLL is the local parity path.
- The `.so` handshake is tested on the host; the Android ABI matrix is not.
