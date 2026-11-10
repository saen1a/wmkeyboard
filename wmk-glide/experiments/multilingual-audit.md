# Multilingual profile audit

Observed 2026-11-09. Harness: `/home/saenta/wm-glide-target/release/examples/glide_lm_blend_eval`.
All data/hashes and raw commands are in the session record; this card keeps the
decision.

## English

Bundled `app/dictionaries-src/en.txt` is **17,306 words** (below the 50k
threshold), so it takes the small path 0.7/3.0 with pieces. The AOSP 160,668
list takes the large listed-only path 0.5/5.0.

| Condition | Top-1 | Top-4 |
|---|---:|---:|
| Small 17,306, no blend | 73.86 | 81.85 |
| Small 17,306, 0.7/3.0 pieces | **77.10** | **82.29** |
| Large 160,668, no blend | 80.55 | 88.50 |
| Large 160,668, 0.5/5.0 listed-only | **80.74** | **88.50** |
| Large 160,668, 0.5/5.0 pieces | 79.69 | 87.72 |

- Small blend is a clear win: +3.25 pp top-1, 1,329/468 paired, p = 2.8e-95;
  the original 2,129/1,824 hard slice reproduces +4.77.
- Large listed-only is **non-negative, not proven**: +0.20 pp, CI [-0.05,
  +0.44], p = 0.121; the bundled-known subset is +0.41, CI [+0.15, +0.66],
  p = 0.0022. Do not present +0.20 as a gain.
- Harness/app BOS: both blend on empty context, so the English numbers above
  already include first-word strokes. 2,650/26,523 (10.0%) have `word_idx=0`.
  On that subset, the 160,668 large list loses **0.72 pp** (p = 0.020), the
  17,306 small list is neutral, and German gains **2.11 pp** (p = 0.07,
  CI [+0.35, +4.23]) on its 2,588 strokes.
- The gap claim came from the old research copy
  `wmk-glide/experiments/glide_lm_blend_eval.rs`; it now blends on empty context
  like the maintained harness
  (`native/wm-engine/examples/glide_lm_blend_eval.rs`) and the app.

**Decision:** keep both English rows; document the large one as non-negative.
Keep the BOS blend: a global empty-context guard would cost German more than it
recovers in English. If the English large first word is worth polishing later,
scope it to that profile row rather than guarding globally.

## Compounding languages

FUTO `swipe5.jsonl` is the upstream file (327,143,325 B, SHA-256
`08F1A805…`). Full histogram: en 47,364, de 5,207, fr 3,124, es 2,029,
pl 1,019, tok 450, lt 52, shaw 2. **fi/nl/sv/no/da/et/hu/tr have zero
strokes**, and `swipe-5/layouts` has no layout for any of them.

Word lists exist in `DictionaryCatalog` (fi 223k, nl 178k, sv 197k, nb 171k,
da 178k, et 1.0M, hu 3.1M, tr 181k), but no strokes and no layout means no
profile row. The German-style weights cannot be measured and must not be
copied.

**Alternative:** HeliBoard gesture data has `fi`, `hu`, `et`, `nl`, `sv`, `da`,
`nb`, `tr` directories, e.g. `fi-1.gestures.json.zst` 566,713 B, CC BY-SA 4.0.
This is the only real-stroke source for those languages and needs its own
protocol per language.

**Finnish measured:** 1,000 single-finger a-z strokes (seed 20261109, 12
geometries) over the app-preferred `fi_aosp` list, `COLS=11`. The German-style
0.75/2.0 pair reads 76.90 / 95.10 against 72.80 / 91.30 at the built-in
default: paired **+4.10 / +3.80 pp**, CI [+2.70, +5.60] / [+2.70, +5.00]. A
join run at 8 / 4 / 0.1 moved 0 of 1,000 outcomes; the app join path uses a
different downloaded compound lexicon (`fi_full`) this slice did not exercise,
so the row ships with joins off. No Finnish model ships. Card:
`wmk-glide/experiments/finnish-profile.md`.

**HeliBoard sweep (2026-11-10):** seven languages, the same two tunings
(`freq_weight=1.0 gap_weight=1.33` against `0.75 / 2.0`), joins off, seed
20261109. Finnish is the a-z slice; the rest are full alphabet. Estonian and
Hungarian clear the paired top-1 CI lower > 0; the other five do not.

| Language | n | geometries | Default top-1 / top-4 | 0.75/2.0 top-1 / top-4 | Delta top-1 / top-4 | CI top-1 | Row |
|---|---:|---:|---:|---:|---:|---|---|
| Estonian | 281 | 2 | 57.30 / 72.95 | 66.55 / 81.14 | +9.25 / +8.19 | [+2.00, +10.82] | yes |
| Hungarian | 436 | 7 | 62.39 / 81.42 | 66.97 / 85.09 | +4.59 / +3.67 | [+3.19, +8.11] | yes |
| Danish | 1,000 | 4 | 71.60 / 90.50 | 66.50 / 88.90 | -5.10 / -1.60 | [-7.62, 0.00] | no |
| Norwegian | 402 | 4 | 62.94 / 80.10 | 62.69 / 80.85 | -0.25 / +0.75 | [-3.21, +3.10] | no |
| Dutch | 1,000 | 37 | 80.30 / 91.10 | 79.80 / 91.30 | -0.50 / +0.20 | [-1.27, +0.14] | no |
| Swedish | 1,000 | 11 | 78.70 / 92.60 | 77.60 / 93.20 | -1.10 / +0.60 | [-2.15, +0.17] | no |
| Turkish | 1,000 | 19 | 72.80 / 88.10 | 73.00 / 88.30 | +0.20 / +0.20 | [-1.20, +1.59] | no |

Card: `wmk-glide/experiments/estonian-hungarian-profile.md`. The Turkish first
pass read +1.30 pp because the runner counted distinct key centres as columns
(19/31); the corrected row width is 10, and the rerun is the record. Danish is
a real regression; Dutch moves top-4 only.

**Decision: GO for Finnish, Estonian and Hungarian, rows shipped with joins
off. Danish, Dutch, Norwegian, Swedish and Turkish stay on `DEFAULT`. Estonian
is the smallest sample (281 strokes, two geometries) and its row carries that
caveat; do not copy it.**

## Banglish

Assets verified: `bn_rom_v2.txt.gz` 439,995 B / 130,934 words / SHA-256
`32450FF4…`; `bn_rom_context.wmlm` 10,801,084 B / SHA-256 `2A43D0DC…`; the
model loads as `["en","bn_rom"]` and matches the catalog. There is **no
`bn_rom` stroke corpus and no `bn_rom` layout** in the temp tree, FUTO, or the
data repo. Synthetic strokes could exercise the pairing but would not validate
a profile.

**Decision: keep the glide blend off; no row. Missing data, not a policy gap.**

## Safe defaults

Confirmed: `de`, `en`, `fi`, `et` and `hu` have rows; every other id resolves
to `DEFAULT` (freq 1.0, gap 1.33, joins off, glide blend 0.0/0.0); a zero blend
returns the decoder order; no German/English number is copied to another
language. `fi`, `et` and `hu` move frequency and gap only and keep joins off.
`fr` is pinned to 0.0 in the profile test; unknown/English decode with the
shipped weights.

**Decision: GO / confirmed.**

## Next

1. **HeliBoard compounding protocol** — Finnish, Estonian and Hungarian done
   (GO, rows shipped with joins off). Danish, Dutch, Norwegian, Swedish and
   Turkish measured and rejected: Danish regresses, the others do not clear the
   paired top-1 CI lower > 0. Re-run any of them only with more strokes or a
   different list, not by copying a row. Do not enable joins from a stroke
   slice; the app's compound-lexicon path needs its own run.
2. **English BOS/empty-context** — measured and closed: both harness and app
   blend on BOS; keep it, no global guard; an English-large-only row flag is an
   optional later polish.
3. **CTC first slice** — ran: FUTO encoder/decoder plus ExecuTorch 1.6 on
   1,000 German HeliBoard a-z strokes. CTC 69.57 / 81.98 against the GlideBeam
   German profile 78.78 / 91.49 on the 999 in-list strokes: **NO-GO as-is**.
   The toolchain and assets are unblocked; the next step is a German-trained
   encoder or fine-tune. Card: `wmk-glide/experiments/ctc-first-slice.md`.
