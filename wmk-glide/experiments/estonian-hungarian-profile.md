# Estonian and Hungarian glide profiles

Observed 2026-11-10. Decision: **GO for both**, shipped as
`GlideLanguageProfiles.ESTONIAN` and `GlideLanguageProfiles.HUNGARIAN`. These
are the first full-alphabet compounding rows; Finnish stays the a-z-only row.

## Why these two and not the other five

The same protocol ran on every HeliBoard language the app has a list for. The
0.75/2.0 pair is the Finnish/German frequency-and-gap profile with joins off.
Only Estonian and Hungarian clear the rule "paired top-1 CI lower bound above
zero".

| Language | n | geometries | Default top-1 / top-4 | 0.75/2.0 top-1 / top-4 | Delta top-1 / top-4 | Wins / losses | McNemar p | Cluster CI top-1 / top-4 | Row |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Estonian | 281 | 2 | 57.30 / 72.95 | **66.55 / 81.14** | **+9.25 / +8.19** | 27 / 1 | 2.16e-07 | [+2.00, +10.82] / [+8.00, +8.23] | **yes** |
| Hungarian | 436 | 7 | 62.39 / 81.42 | **66.97 / 85.09** | **+4.59 / +3.67** | 26 / 6 | 5.35e-4 | [+3.19, +8.11] / [+1.37, +8.86] | **yes** |
| Danish | 1,000 | 4 | 71.60 / 90.50 | 66.50 / 88.90 | -5.10 / -1.60 | 4 / 55 | 1.7e-12 | [-7.62, 0.00] / [-2.54, 0.00] | no |
| Norwegian | 402 | 4 | 62.94 / 80.10 | 62.69 / 80.85 | -0.25 / +0.75 | 7 / 8 | 1.00 | [-3.21, +3.10] / [-3.57, +5.04] | no |
| Dutch | 1,000 | 37 | 80.30 / 91.10 | 79.80 / 91.30 | -0.50 / +0.20 | 9 / 14 | 0.405 | [-1.27, +0.14] / [-0.52, +0.90] | no |
| Swedish | 1,000 | 11 | 78.70 / 92.60 | 77.60 / 93.20 | -1.10 / +0.60 | 17 / 28 | 0.135 | [-2.15, +0.17] / [-0.21, +1.64] | no |
| Turkish | 1,000 | 19 | 72.80 / 88.10 | 73.00 / 88.30 | +0.20 / +0.20 | 23 / 21 | 0.88 | [-1.20, +1.59] / [-0.60, +1.31] | no |

Dutch moves top-4 only; its top-1 CI includes zero. Danish is a real regression,
not noise. Turkish is flat after the column count is fixed; the earlier
+1.30 pp reading was an artifact of counting distinct key centres instead of the
widest key row (19/31 "columns" instead of the real layout width).

## Data

| Item | Value |
|---|---|
| Strokes | HeliBoard gesture data, `et` and `hu`, CC BY-SA 4.0 (`codeberg.org/eclexic/heliboard-gesture-data`) |
| Estonian archive | `batch_2/et/et-1.gestures.json.zst` 214,428 B SHA-256 `435759c1…` |
| Hungarian archives | `batch_1` 220,567 B `09a21d34…`; `batch_2` 74,369 B `022c048e…`; `batch_3` 780,549 B `c603fbe8…` |
| Estonian list | `et_full.txt.gz` 4,084,505 B SHA-256 `6b85adb3…`; first 300,000 lines `et_full_300k.txt` 4,124,216 B `971c73be…` |
| Hungarian list | `hu_full.txt.gz` 13,176,302 B SHA-256 `439cc639…`; first 300,000 lines `hu_full_300k.txt` 4,562,784 B `347351ea…` |
| Slice | full alphabet, single pointer, seed 20261109; Estonian 281/281 eligible, 2 geometries; Hungarian 436/436, 7 geometries |
| Layout | HeliBoard `et` and `hu` QWERTY, 10 columns; `COLS` taken from the widest key row |
| Model | none; no Estonian or Hungarian `.wmlm` ships |

The 300,000-line cap is the app's LARGE list size; the full lists are 1.0M and
3.1M words. A user on a smaller size sees a smaller dictionary, so the absolute
numbers are a large-list measurement, not a promise for every size.

## Protocol

- `wmk-glide/experiments/heliboard_slice.py` parses the records, keeps every
  single-pointer alphabetic target whose letters exist in its own keyboard
  geometry, samples with seed 20261109, and writes one records/layout pair per
  geometry.
- `wmk-glide/experiments/heliboard_run.py` decodes each geometry twice with
  `DUMP` on: the shipped default (`freq_weight=1.0 gap_weight=1.33`) and the
  measured profile (`freq_weight=0.75 gap_weight=2.0`). It pairs the hit flags
  stroke by stroke, sums top-1/top-4, runs an exact McNemar test, and cluster
  bootstraps over geometries (10,000 resamples).
- `RESULTS=4`; the harness prints `top{RESULTS}` and counts a hit anywhere in
  the returned candidates, so this is top-4.
- Joins are off in both runs.

## Caveats

- Estonian has only 281 eligible strokes in two geometries. The effect is large
  and the CI excludes zero, but the estimate is wide; the row ships with that
  caveat rather than waiting for a corpus that does not exist.
- Hungarian has 436 strokes across seven geometries; weaker than the 1,000-stroke
  Finnish slice but monotone across groups.
- Full alphabet (unlike Finnish's a-z-only slice); diacritics are part of the
  measurement.
- Community corpus; written word lists, not counted corpora.
- No on-device latency re-measure. The row moves frequency and gap only and
  activates no join or lexicon path.
- The Turkish result is flat, not the earlier positive reading; the columns bug
  is the reason the first pass was wrong, and the corrected run is the record.

## Decision

Add `ESTONIAN` and `HUNGARIAN` with `freqWeight` 0.75, `gapWeight` 2.0, the
`DEFAULT` join fields (off), and no glide blend. Do not add rows for Danish,
Dutch, Norwegian, Swedish or Turkish. Re-run any of them only with more strokes
or a different list, not by copying these weights.

## Reproduction

```sh
cd native/wm-engine
cargo build --release --example glide_beam_eval
cd ../..
python3 wmk-glide/experiments/heliboard_slice.py --lang et --alphabet full \
  --out /tmp/slices/et --list /tmp/wordlists/et_full.txt /tmp/helio/et/2/records.json
python3 wmk-glide/experiments/heliboard_run.py --lang et --slice /tmp/slices/et \
  --list /tmp/wordlists/et_full_300k.txt \
  --harness native/wm-engine/target/release/examples/glide_beam_eval \
  --out /tmp/results/et.json
# Hungarian: the same two commands with lang hu and batches 1..3.
```

The harness path in this session was
`/home/saenta/wm-glide-target/release/examples/glide_beam_eval`.
