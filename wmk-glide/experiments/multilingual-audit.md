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

**Decision: GO for Finnish only, row shipped with joins off. The other seven
remain NO-GO until each has its own 1,000-stroke run with a paired CI lower
bound above zero.**

## Banglish

Assets verified: `bn_rom_v2.txt.gz` 439,995 B / 130,934 words / SHA-256
`32450FF4…`; `bn_rom_context.wmlm` 10,801,084 B / SHA-256 `2A43D0DC…`; the
model loads as `["en","bn_rom"]` and matches the catalog. There is **no
`bn_rom` stroke corpus and no `bn_rom` layout** in the temp tree, FUTO, or the
data repo. Synthetic strokes could exercise the pairing but would not validate
a profile.

**Decision: keep the glide blend off; no row. Missing data, not a policy gap.**

## Safe defaults

Confirmed: `de`, `en` and `fi` have rows; every other id resolves to `DEFAULT`
(freq 1.0, gap 1.33, joins off, glide blend 0.0/0.0); a zero blend returns the
decoder order; no German/English number is copied to another language. `fi`
moves frequency and gap only and keeps joins off. `fr` is pinned to 0.0 in the
profile test; unknown/English decode with the shipped weights.

**Decision: GO / confirmed.**

## Next

1. **HeliBoard compounding protocol** — Finnish done (GO, +4.10 / +3.80 pp,
   joins off). Dutch, Swedish and Norwegian are next: verify each layout and
   its single-finger records, run the built-in default vs German-style profile
   on 1,000 strokes, and add a row only on a paired CI lower > 0. Do not enable
   joins from an a-z slice; the app's compound-lexicon path needs its own run.
2. **English BOS/empty-context** — measured and closed: both harness and app
   blend on BOS; keep it, no global guard; an English-large-only row flag is an
   optional later polish.
3. **CTC first slice** — still blocked on ExecuTorch, the encoder/HeliBoard
   assets, the two scripts, and a pinned baseline.
