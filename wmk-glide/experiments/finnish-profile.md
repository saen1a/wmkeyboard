# Finnish glide profile

Observed 2026-11-09. Decision: **GO, shipped as `GlideLanguageProfiles.FINNISH`**.
The first compounding profile measured on its own strokes rather than copied
from German. All numbers are single-finger a-z success per swipe.

## Data

| Item | Value |
|---|---|
| Strokes | HeliBoard gesture data, `fi`, CC BY-SA 4.0 (`codeberg.org/eclexic/heliboard-gesture-data`) |
| Archives | `batch_1` `fi-1.gestures.json.zst` 566,713 B SHA-256 `b2f38eed…`; `batch_2` 142,970 B SHA-256 `00f1eaf6…`; `batch_3` 1,182,232 B SHA-256 `b74a7e49…` |
| Word list | AOSP Finnish `fi_aosp.txt.gz`, 1,093,376 B SHA-256 `94cc5802…` (the list the app downloads) |
| Slice | 1,000 single-finger a-z target words, seed 20261109, 12 keyboard geometries |
| Layout | HeliBoard `fi` (11 columns: q…p å, a…ä, z…m), `COLS=11` |
| Model | none; no Finnish `.wmlm` ships |

The HeliBoard records carry their own `keyboardInfo`; the slice converts each
record's `gesture` points and canvas to the harness's record/layout JSON and
keeps targets matching `^[a-z]+$` with one pointer id. The raw archives and the
derived slice stayed in the session temp tree; the hashes above identify the
source.

## Result

Harness: `native/wm-engine/examples/glide_beam_eval`, `STATS=1 ALL=1 RESULTS=4
COLS=11 THREADS=8`. Two tunings on the same 1,000 strokes:

| Tuning | Top-1 | Top-4 |
|---|---:|---:|
| Built-in default (1.0 / 1.33, joins off) | 72.80 | 91.30 |
| Finnish profile (0.75 / 2.0, joins off) | **76.90** | **95.10** |
| Paired delta | **+4.10 pp** | **+3.80 pp** |

A German-style join run (8 / 4 / 0.1) read the same 76.90 / 95.10: joins moved
0 of 1,000 outcomes. Cluster CI: top-1 [+2.70, +5.60], top-4 [+2.70, +5.00].
The counted `fi` list agrees with the a-z slice.

### Ablations and references

- Join guard: 0 of 1,000 outcomes moved between joins off and 8 / 4 / 0.1.
  The app resolves joins through a separate downloaded compound lexicon
  (`fi_full`), which this slice did not exercise, so the shipped row leaves
  joins off and does not trigger that download.
- Cross-check 2026-11-10 with `heliboard_slice.py` / `heliboard_run.py`: a
  fresh 1,000-stroke a-z slice (1,766 eligible, 9 geometries) read 76.00 / 94.80
  with joins off and 76.00 / 94.80 with joins on; 0 wins, 0 losses. The app
  filter cannot change a top-1 that joins never moved.
- Context blend: not applicable; no Finnish model. `glideLmBlend = 0.0`,
  `freqWeightWithContext` inherits 0.75.
- HeliBoard's own recogniser reports 86.5 % top-1 on its corpus (external
  reference; different scorer, not the app path, not re-run on this slice).

## Caveats

- a-z only: no `ä`, `ö`, `å`, no punctuation, no dual-finger strokes.
- 1,000 strokes from a community corpus, not a frequency-matched sample.
- The word list is written standard Finnish, not a counted corpus.
- Joins are off in the shipped row, so the downloaded compound-lexicon path
  remains unmeasured for Finnish.
- On-device latency is unchanged by construction: the row only moves
  `freqWeight` and `gapWeight`, and no join or lexicon path is activated. It
  was not re-measured on a phone.

## Decision

Add `FINNISH` to `GlideLanguageProfiles` with `freqWeight` 0.75 and
`gapWeight` 2.0; leave the `DEFAULT` join fields (off) and the glide blend at
0.0. Do **not** copy the row to Dutch, Swedish or Norwegian: each needs its
own 1,000-stroke run and a paired CI lower bound above zero.

## Reproduction

```sh
cd native/wm-engine
printf 'freq_weight=1.0 gap_weight=1.33\nfreq_weight=0.75 gap_weight=2.0\n' \
  | COLS=11 STATS=1 ALL=1 RESULTS=4 THREADS=8 \
    cargo run --release --example glide_beam_eval -- \
    /path/to/fi-records.jsonl /path/to/fi-layout.json /path/to/fi_aosp.txt
```

`RESULTS=4` is what makes the second column top-4; the harness prints
`top{RESULTS}` and counts a hit anywhere in the returned candidates. The
derived `fi-records.jsonl` and `fi-layout.json` are the session-local
conversion; the source archives above are identified by hash.
