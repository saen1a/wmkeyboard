# Patches against wasi-master/wmkeyboard 22d5020b

Four app patches, in this order. The first is measurement-only (the eval
harness); the rest are the change. They apply cleanly to `22d5020b`. A fifth,
optional layout patch lives in `experiments/german-umlaut-keys.patch`; it is
**not recommended** as a recognition lever (+1.36 synthetic, see the layout
section). `0005-distill-multitoken` is outside the app series: it patches the
training tool `tools/wmlm/distill.py` (see "Training tools" below).

```sh
git clone https://github.com/wasi-master/wmkeyboard
cd wmkeyboard && git checkout 22d5020b
for p in 0000-eval-harness 0001-glide-context-blend 0002-compound-join-guard \
         0004-tests-ci; do
  git apply /path/to/wmk-glide/patches/$p.patch
done
# optional, not recommended:
# git apply /path/to/wmk-glide/experiments/german-umlaut-keys.patch
```

| Patch | Files | What it does |
|---|---|---|
| `0000-eval-harness` | `examples/glide_beam_eval.rs` | `join_min_part=` / `join_part_penalty=` on the tuning line, and a pool dump with each candidate's score (`word:score|...`) for the blend sweep |
| `0001-glide-context-blend` | `SuggestionEngine.kt`, `ContextModel.kt`, `PredictionNative.kt`, JNI `lm.rs` | `blendGlideContextModel` in `finishGlide`, before `rerankGlide`: scores the 8–16 glide candidates through `scoresSpelled` (piece product for OOV compounds), references the first finite score, `GLIDE_LM_BLEND = 0.5`, `GLIDE_LM_BLEND_CAP = 5.0` |
| `0002-compound-join-guard` | Rust `glide/mod.rs`, `workspace.rs`, JNI `glide.rs`, Kotlin `GlideBeam.kt`, `GlideLanguageProfiles.kt`, `NativeGlide.kt`, its test | `joinMinPart` + `joinPartPenalty` in `Tuning`; the German profile becomes 8 nats, four-letter parts, 0.1 per `ln(1+f)`; JNI array 28 -> 30 |
| `0004-tests-ci` | `glide_freq_weight.rs`, `glide_join.rs`, `ci.yml` | the two red tests fixed and `cargo test` added to CI |

## Training tools

| Patch | Files | What it does |
|---|---|---|
| `0005-distill-multitoken` | `tools/wmlm/distill.py` | maps a student word the teacher spells in several tokens to the product of its conditional token probabilities, instead of dropping it. `multi=0` restores the old one-token rule; `dtype=` selects float16/bfloat16/float32; `trust=1` passes `trust_remote_code=True` for custom-code models (Soofi); the softmax stays in the model dtype (fp16) instead of a float32 copy, which otherwise thrashes a 16 GB card at `batch=32`. `--self-test` checks the product against a scalar reference. |

Measured on the prepared Tatoeba German vocabulary (22,045 real words):
Qwen2.5 maps **2,279 (10.3 %)** whole, Gemma 3 4B **4,413 (20.0 %)**; the
multi-token rule reaches **22,045 (100 %)** for both. On a ten-sentence test,
the words after "ich gehe jetzt nach" are `haus` (0.29) with the old rule and
`hause` (0.95, renormalised) with the new one. On the full Tatoeba+Leipzig
vocabulary (22,512 words) Qwen2.5 maps 12.8 % whole, Qwen3.5 23.6 %; both
reach 100 % multi-token. Teacher comparison and throughput: `wmlm-training-plan.md`.

For overnight runs the patch also adds `start=`/`count=` chunking, an atomic
write (`*.tmp.npz` → `os.replace`), a `torch.isfinite(probs)` guard, an
`int16`/`int32` id dtype selected by vocabulary size, and `del`/`empty_cache`
after each batch. `merge_soft.py` validates and stitches chunks;
`check_soft.py` is the pre-training gate.

Optional experiment, not part of the four: `experiments/german-umlaut-keys.patch`
(QWERTZ 11 columns with `ü ö ä ß` as keys, long-press entries removed). It is not
recommended: the measured gain is +1.36 synthetic, and the app keeps the long-press.

## Numbers (FUTO German, n = 2,588 swipes, `ALL=1 RESULTS=4 COLS=11`)

| Run | top-1 | top-4 |
|---|---|---|
| shipped tuning | 71.45 | 82.30 |
| German profile (`freq 0.5 gap 2.0`) | 74.15 | 82.81 |
| German profile + bare `join_cost=3` | 70.63 | 79.60 |
| German profile + guard (`8 / 4 / 0.1`) | **74.61** | **83.31** |

The join oracle (target absent from the list, splits into two listed words of
three letters or more) is 118/2,588 = **4.56 %**, so the guard captures about a
tenth of it. The rest needs a compound language model, not a constant.

**The bigger German lever is a data change, not a patch:** append the real
compounds from FrequencyWords `de_full` (441,470 observed words absent from the
150k list that split into two 150k words) to the dictionary. German profile:
74.15 -> **75.70** top-1 / 82.81 -> **84.23** top-4; with the guard
**75.77 / 84.47**. Builder: `tools/build_compound_list.py`. The full 1.16M list
is 75.46 / 84.39, so the curated list is better on top-1.

## Reranker (n = 2,294 with a previous word)

`blendGlideContextModel` at 0.7/3.0: **70.84 -> 80.82**. Cap sweep: 1 nat
75.37, 1.5 77.03, 2 78.47, 2.5 79.86, 3 80.82, 4 81.73, uncapped 82.39
(weight 0.7); the uncapped best is 83.13 at weight 1.5. The language model in
this measurement is a corpus bigram, the same stand-in as `rerank_eval.py`.
**In-sample caveat:** a 20 % sentence split with the LM on the other 80 %
gives 68.97 -> 69.17 (+0.20); the corpus LM is small, and the real `.wmlm`
still has to confirm the device gain. See `experiments-followup.md` §0.

With the trained German `.wmlm` (`state.md` §2.7) on 2,588 FUTO swipes and the
German profile, **0.5/5.0** gives 74.15 -> **77.40 / 83.42** on the 150k list
and 75.70 -> **78.48 / 84.85** with the 441k observed compounds. The patch
scores only the first 8–16 candidates with `scoresSpelled`, so an OOV compound
gets its piece product instead of NaN, and references the first finite score;
the strip's per-keystroke `scores` stays lookup-only. This supersedes the
0.7/3.0 corpus-bigram point above. Simulating the old lookup-only path on the
same strokes gives 76.04 / 83.23 (150k) and 77.51 / 84.66 (compounds), with
1,782 / 1,693 of 2,294 strokes blended instead of all 2,294 — the app gap was
**+1.36 / +0.97** top-1.

**German `.wmlm`:** trained and measured (`state.md` §2.7), not yet published
or in `ContextModelCatalog`. Until the catalog entry and the rebuilt Android
`.so` are in, the blend is a no-op on a German device. The German pack's
rank-unit rerank (the `NgramReranker` path already in the app) is +0.45; the
pack as a score blend is negative. See `experiments-followup.md` §0b.

## Layout (1,324 synthetic words, German profile, noise 0.05)

| Grid | top-1 | top-4 |
|---|---|---|
| long-press, umlaut at the base key (what the app builds today) | 96.37 | 100.00 |
| only a-z in the key map (old 77 %-style lower bound) | 85.57 | 87.46 |
| dedicated `ü ö ä ß` keys (optional patch) | **97.73** | **100.00** |

The gain is +1.36 points at noise 0.05, +1.28 at 0.10, +1.43 at 0.15 and +1.06
at 0.20; the synthetic strokes have no real pauses or loops, so treat the
absolute numbers as optimistic and the difference as the signal. **Conclusion:
not adopted**; the long-press is close enough, and the layout patch is kept only
as an optional experiment. On FUTO's
real German strokes, adding the `ß` key to the recorded grid changes nothing
(71.45 -> 71.45): those 34 `ß` targets were not drawn on a `ß` key. FUTO's grid
already has `ü ö ä` as keys, so real strokes cannot measure long-press against
dedicated keys; the synthetic run is the comparison.

## Build note

The JNI `tuning()` now requires 30 values. An old 28-value Kotlin build against
the new library returns no candidates instead of silently dropping
`joinMinPart`/`joinPartPenalty`; rebuild the `.so` in
`core/language/src/main/jniLibs` before release (the same open item as
`state.md` section 4.2). `cargo test --release --manifest-path
native/wm-engine/Cargo.toml` is green: 496 + 3 + 5 + 4 tests.
