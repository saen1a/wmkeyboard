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
- Harness/app gap: 2,650/26,523 strokes (10.0%) have `word_idx=0`; the harness
  skips the blend, the app would blend on BOS/unigram. Impact unverified.

**Decision:** keep both English rows; document the large one as non-negative.

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
Record counts, single/dual split and layout mapping are unverified; this is the
only real-stroke source and needs its own protocol.

**Decision: NO-GO for all eight; no row; built-in defaults.**

## Banglish

Assets verified: `bn_rom_v2.txt.gz` 439,995 B / 130,934 words / SHA-256
`32450FF4…`; `bn_rom_context.wmlm` 10,801,084 B / SHA-256 `2A43D0DC…`; the
model loads as `["en","bn_rom"]` and matches the catalog. There is **no
`bn_rom` stroke corpus and no `bn_rom` layout** in the temp tree, FUTO, or the
data repo. Synthetic strokes could exercise the pairing but would not validate
a profile.

**Decision: keep the glide blend off; no row. Missing data, not a policy gap.**

## Safe defaults

Confirmed: only `de`/`en` have rows; every other id resolves to `DEFAULT`
(freq 1.0, gap 1.33, joins off, glide blend 0.0/0.0); a zero blend returns the
decoder order; no German/English number is copied. `fr` is pinned to 0.0 in
the profile test; unknown/English decode with the shipped weights.

**Decision: GO / confirmed.**

## Next

1. **HeliBoard compounding protocol** — pick a language, verify its layout and
   single-finger records, run the built-in default vs German-style profile on
   the same strokes; add a row only on a paired CI lower > 0.
2. **English BOS/empty-context** — measure whether the app's BOS blend helps or
   hurts; the harness currently skips it for 10% of strokes.
3. **CTC first slice** — still blocked on ExecuTorch, the encoder/HeliBoard
   assets, the two scripts, and a pinned baseline.
