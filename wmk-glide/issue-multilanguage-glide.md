# [FEAT]: Per-language glide context profiles and a measured blend for every list

> Prepared draft only. Do not open the GitHub issue until the prototype branch is
> pushed and the open questions below have an owner. The upstream issue template
> this follows is
> [feature_request.yml](https://github.com/wasi-master/wmkeyboard/blob/main/.github/ISSUE_TEMPLATE/feature_request.yml).

## Description

The glide context blend is now opt-in per **language and list size**, and the
prototype on the local `glide-engine` branch carries the measurements behind it.
Three things still need a per-language decision before the policy can be called
finished for every language:

1. **German frequency weight with the downloaded WMLM.** The decoder alone
   prefers 0.75 (81.22 % top-1 over the AOSP list); with the German context
   model, 0.5 reads 82.77 % (gate 5). The two are measured on the same 2,588
   FUTO strokes but 0.5 was fitted on that corpus, so a held-out split is
   required before the weight becomes context-dependent.
2. **Compounding and long-word languages have no profile.** Finnish, Dutch,
   Swedish, Norwegian, Danish, Estonian, Hungarian and Turkish still decode
   with the English-fitted defaults (`freqWeight` 1.0, `gapWeight` 1.33, joins
   off). They need one harness run each, then a row only if it wins.
3. **Banglish (`bn_rom`) has a published model but no profile.** The default
   glide blend is now off, so its model currently helps typing only. It needs
   a glide measurement to decide whether it should have a row.

The current policy and the data behind it:

- **German**: `freqWeight` 0.75, `gapWeight` 2.0, join 8.0 / 4 letters / 0.1;
  glide blend 0.5 / 5.0 with unlisted candidates spelled, on both AOSP and
  counted lists.
- **English**: decoder defaults; glide blend 0.7 / 3.0 with pieces on the small
  bundled list, and 0.5 / 5.0 on listed candidates only above
  `GLIDE_LM_BLEND_LIST_LIMIT` (50,000 words).
- **Default / unmeasured / mixed fields**: glide blend 0.0. The typing blend is
  unchanged.
- `WordSource.wordCount` selects the size class; `CompositeWordSource` sums its
  members, `PackedTrie` counts once, `MappedTrie` reads the file header.

## Additional Information

### Measurements

German, 2,588 FUTO strokes, German profile, German `de_context.wmlm`, WMLM
0.5 / 5.0, gate 5, 4,000 pops / 12,288 states:

| List | Weight | No blend (top-1 / top-4) | Blend (top-1 / top-4) | Spelled | Notes |
|---|---:|---:|---:|---:|---|
| AOSP 205,931 | 0.75 | 81.22 / 87.60 | **81.68 / 87.56** | 2,571 | shipped profile |
| AOSP 205,931 | 0.5 | 80.64 / 87.21 | **82.77 / 87.71** | 3,979 | context-model candidate |
| counted 1.15M | 0.75 | 75.97 / 85.90 | 78.63 / 86.13 | 4,640 | large-list path |
| counted 1.15M | 0.5 | 79.40 / 86.17 | 79.40 / 86.13 | 5,887 | decoder already ahead; blend neutral |

The gate (spell an unlisted candidate only within the blend cap of the leader)
cut AOSP German spelling from 10,260 to 2,571 (−75 %) with top-1 unchanged.
The 0.5-with-model gain is **AOSP-specific**: on the counted list the 0.5 decoder
already reads 79.40 % and the blend neither lifts nor drops it.

English, 26,523 FUTO English strokes, 160k AOSP list, default profile, English
`en_context.wmlm`:

| Blend | Top-1 | Top-4 | Spelled |
|---|---:|---:|---:|
| none | **80.55** | **88.50** | 0 |
| 0.7 / 3.0, pieces | 79.57 | 87.83 | 10,252 |
| 0.5 / 5.0, pieces | 79.69 | 87.72 | 10,252 |
| **0.5 / 5.0, listed only** | **80.74** | **88.50** | **0** |

The large-list English regression came from spelling unlisted candidates;
scoring listed candidates alone is positive and costs no piece pass.

Budget effect (no context model), 4,000 pops / 12,288 states against the old
2,000 / 8,192:

| List | Top-1 | Top-64 |
|---|---|---:|
| AOSP German | 81.07 → 81.22 | 88.60 → 88.91 |
| counted German | 75.46 → 76.31 | 86.36 → 87.75 |
| English (AOSP) | not measured | not measured |

Per-context LM score cache, German model, 16 OOV words: 83.48 ms cold,
9.12 µs on the second ask; a 10-frame sliding pool 52.33 ms against 809.44 ms
with a fresh context per frame (15.5×).

Reproduce with the example in this repo; the AOSP lists are the downloaded
`.txt` converted through `AospScores.listCount`:

```sh
# German, AOSP list, shipped 0.75 profile plus the WMLM
COLS=11 THREADS=8 RESULTS=8 FREQ=0.75 GAP=2.0 \
  JOIN_COST=8 JOIN_MIN_PART=4 JOIN_PART_PENALTY=0.1 VOCAB_RANK=0 \
  WEIGHT=0.5 CAP=5 GATE=5 \
  glide_lm_blend_eval de_swipes.jsonl german.json de_aosp_counts.txt de_context.wmlm

# English, AOSP list, listed-only large-list blend
COLS=10 THREADS=8 RESULTS=8 FREQ=1.0 GAP=1.33 VOCAB_RANK=0 \
  WEIGHT=0.5 CAP=5 GATE=0 SPELL=0 \
  glide_lm_blend_eval en_swipes.jsonl qwerty.json en_aosp_counts.txt en_context.wmlm
```

### Code the issue would touch

Upstream main at `69e87afa4` (the prototype is on the local `glide-engine`
branch, commits `f813ad8d0`, `735e0bb7a`, `429985bab`, `5328c6d8c`; not pushed):

- [GlideLanguageProfiles.kt](https://github.com/wasi-master/wmkeyboard/blob/main/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/gesture/GlideLanguageProfiles.kt)
  — profile rows and the glide blend fields.
- [SuggestionEngine.kt](https://github.com/wasi-master/wmkeyboard/blob/main/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/SuggestionEngine.kt)
  — `blendGlideContextModel`, the listed-only path and the size selection.
- [Trie.kt](https://github.com/wasi-master/wmkeyboard/blob/main/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/Trie.kt),
  [PackedTrie.kt](https://github.com/wasi-master/wmkeyboard/blob/main/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/PackedTrie.kt),
  [CompositeWordSource.kt](https://github.com/wasi-master/wmkeyboard/blob/main/core/prediction/src/main/java/com/wasimaster/wmkeyboard/core/prediction/CompositeWordSource.kt)
  — the word-count size class.
- [glide_lm_blend_eval.rs](https://github.com/wasi-master/wmkeyboard/blob/main/native/wm-engine/examples/glide_lm_blend_eval.rs)
  — `GATE`, `SPELL=0`, `VOCAB_RANK`, `JOIN_*`, and the per-item dump.
- [GlideLanguageProfilesTest.kt](https://github.com/wasi-master/wmkeyboard/blob/main/core/prediction/src/test/java/com/wasimaster/wmkeyboard/core/gesture/GlideLanguageProfilesTest.kt)
  — the prototype's policy test (the file is new on the local branch).

### Open questions / proposed checklist

- [ ] **German held-out weight.** Split FUTO by sentence, fit 0.75 / 0.5 / 0.4
      with and without the WMLM, then decide whether the profile selects a
      context weight. Expected in-sample gain: +1.09 top-1 on AOSP.
- [ ] **Compounding languages.** Run the harness for `fi`, `nl`, `sv`, `no`,
      `da`, `et`, `hu`, `tr` with their AOSP/counted lists and FUTO layouts;
      add a row only if the same protocol wins. Do not copy German's numbers.
- [ ] **Banglish.** Measure `bn_rom` against its model; add a row or keep the
      safe default.
- [ ] **English small list.** Re-run the 17k bundled list against
      `en_context.wmlm` at 0.7 / 3.0; the +4.9 top-1 is the research result,
      not re-run in the prototype.
- [ ] **Budgets on a second language.** Measure 4,000 / 12,288 on English and
      one compounding language; the German gain is not a universal number.
- [ ] **Per-source vocabulary cap.** The 300k setting is global; AOSP German is
      205k, so the cap is inert there, while the counted list and English still
      move. Decide whether the cap should be per language/source.
- [ ] **Native library and parity.** Rebuild the Android `.so` and run
      `NativeGlideParityTest`; the prototype's Rust cache and budget constants
      are not in the checked-in library yet.
- [ ] **Word-count wrappers.** `WordSource` reports 0 for a source that cannot
      say; confirm every active dictionary path is `PackedTrie`,
      `MappedTrie` or `CompositeWordSource`.

### Why this is a feature request rather than a bug

The prototype removes the measured English regression and keeps the German
gain, but the remaining items are per-language weight decisions that need
datasets and a held-out protocol. Shipping any of them without that evidence
would repeat the earlier mistake of applying a German fit to every language.
