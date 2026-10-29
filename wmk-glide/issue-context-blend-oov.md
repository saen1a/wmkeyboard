# [FEAT]: Score unlisted words in the context blend, and widen the glide pool only when ambiguous

> Draft for `wasi-master/wmkeyboard`, following
> `.github/ISSUE_TEMPLATE/feature_request.yml`. Not posted. The local branch
> carries a working patch; nothing is committed or pushed. Related: #966.

## Description

The glide context blend is silent for a word the model does not list. It asks
`ContextModel.scores` → `lmScores` → `logprob_listed`, so an unlisted German
compound gets `NaN`; when the decoder's leader is such a word, the whole blend
returns early. The same pattern exists in the typing path (Kotlin
`blendContextModel` and the Rust `Predictor`): the leader's score is the
reference, and an unlisted leader aborts the blend.

On 2,588 FUTO German swipes, simulating that lookup-only path against a
piece-spelling path at the same 0.5/5.0 blend changed top-1 from 76.04 to
**77.40** on the 150k list and from 77.51 to **78.48** with 441k observed
compounds; 512 and 601 of the 2,294 strokes with a previous word were
previously left unblended. The engine already has the spelling under
`Session::logprob` (list or piece product); the app just does not ask for it on
this path.

Two smaller, measured follow-ups belong to the same area: decoding 16 glide
candidates instead of 8 adds **+0.11 top-1 / +0.24 top-4** (150k) and
**+0.07 / +0.24** (compounds), at twice the decode and score cost; and the
blend constants are global even though they were fitted on German.

## Evidence

Glide, 2,588 FUTO German swipes, German profile (`COLS=11 FREQ=0.5 GAP=2.0`),
`WEIGHT=0.5 CAP=5`, 2,294 strokes with a previous word:

| Word list | lookup-only top-1/top-4 | piece-spelled top-1/top-4 | blended (of 2,294) |
|---|---:|---:|---:|
| 150k | 76.04 / 83.23 | **77.40 / 83.42** | 1,782 → 2,294 |
| 150k + 441k compounds | 77.51 / 84.66 | **78.48 / 84.85** | 1,693 → 2,294 |

Candidate pool (same strokes, only the decode depth changed):

| Pool | 150k top-1/top-4 | +441k top-1/top-4 |
|---:|---:|---:|
| 8 (today) | 77.40 / 83.42 | 78.48 / 84.85 |
| 12 | 77.43 / 83.54 | 78.52 / 84.93 |
| 16 | **77.51 / 83.66** | **78.55 / 85.09** |

Typing, 500 fast cases on German held-out, `LMBLEND=0.5 LMBCAP=5.0` (Rust
`Predictor`; the Kotlin app is the same shape):

| Variant | top-1 | top-3 | suggest (us) |
|---|---:|---:|---:|
| lookup-only (today) | 62.00 | 79.40 | 2,540 |
| leader spelled through pieces | 62.20 | 79.60 | 2,847 |
| top-4 OOV candidates spelled | 62.80 | 79.60 | 4,755 |
| every candidate spelled | **63.00** | **80.00** | 27,378 |

Spelling the leader is cheap; spelling every candidate is not. The typing
path should spend the piece cost on the leader and a small, bounded set of
candidates that can actually win.

Piece coverage is a separate, vocab-level limit: with the current
`pieces_of` (word-initial table only), **20.5 %** of the valid 150k words and
**19.6 %** of the 591k word list are unspellable even though every letter has
a `##` piece. `gib` has no `g`/`gi` word-initial piece, but `##g`, `##i`,
`##b` exist. A continuation-start fallback made 99.99 % spellable but changed
neither top-1 nor top-4 on FUTO; the clean fix is to seed a–z/äöüß as
word-initial pieces in `prep.py` (part of a 32k vocabulary run).

## Proposed change

1. **Expose a spelled score for small candidate sets.** Keep the current
   lookup `scores()` for the whole strip; add a spelled variant
   (`lmScoresSpelled` / `ContextModel.scoresSpelled` → `Session::logprob`) and
   use it only for the 8–16 glide candidates. Reference the **first finite**
   score; a candidate the model cannot read keeps its decoder score.
2. **Do the same in the typing path.** Spell the leader when it is unlisted
   (cheap, +0.20 top-1 in the prototype) and optionally the top-k unlisted
   candidates within a score margin (top-4 measured +0.60). Do not spell every
   candidate per keystroke.
3. **Widen the glide pool adaptively.** Keep 8 candidates normally; decode 16
   and re-blend only when the stroke is ambiguous (small top-1/top-2 gap, high
   model entropy, or the model disagreeing with the decoder). This captures
   most of the +0.11/+0.24 at the cost of 8.
4. **Move `GLIDE_LM_BLEND`/`GLIDE_LM_BLEND_CAP` into the per-language glide
   profile.** German wants 0.5/5.0; a global constant risks English and other
   languages.
5. **Seed single letters in the student vocabulary** so piece spelling covers
   the first letter of every word; keep the continuation fallback optional and
   measured, not a silent heuristic.
6. **Test it.** A tiny `.wmlm` with pieces, an unlisted leader, and a listed
   runner-up should assert that the blend still moves the runner-up; the
   current tiny model has no pieces, so this case is untested.

## Suggested split

If this is too broad for one issue, the natural PRs are:

1. spelled scoring + first-finite reference (glide and typing strategy);
2. adaptive 16-candidate glide pool;
3. per-language blend constants + tests;
4. `prep.py` alphabet seed / piece coverage.

## Additional Information

- A local patch exists on top of the glide context blend discussed in #966:
  `ContextModel.scoresSpelled`, `lmScoresSpelled`, and
  `SuggestionEngine.blendGlideContextModel` scoring the first 16 candidates.
  It is not committed or pushed.
- Data: FUTO German `swipe-5` (2,588 strokes, MIT), German held-out
  `heldout.tsv` (500 fast cases). The model is a 10.86 MB d256/6/768 German
  `.wmlm` trained with `tools/wmlm`; no API keys or user text are involved.
- Caveats: the Kotlin code was not compiled here (no Android SDK), the
  Android `.so` was not rebuilt (no NDK), and no phone latency was measured.
  The typing numbers are the Rust `Predictor`, not the Kotlin app; the
  direction should carry over, the absolute values need a device run.
- Reproduce:

```powershell
$e="native/wm-engine/target/release/examples/glide_lm_blend_eval"
$d="wmk-glide/artifacts"
$env:RESULTS="8"; $env:COLS="11"; $env:THREADS="8"; $env:FREQ="0.5"; $env:GAP="2.0"; $env:WEIGHT="0.5"; $env:CAP="5"
& $e "$d/data/de_swipes.jsonl" "$d/data/german.json" "$d/data/de_150k_comp3.txt" "$d/models/de_context.wmlm"
```

```powershell
$t="native/wm-engine/target/release/examples/typing_eval"
$env:CASES="500"; $env:SCATTER="fast"; $env:MODES="base,lm"; $env:SAVINGS="0"; $env:LMBLEND="0.5"; $env:LMBCAP="5.0"
& $t "$d/data/de_150k.txt" "$d/data/heldout.tsv" "$d/models/de_context.wmlm"
```
