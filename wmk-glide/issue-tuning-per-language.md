# [FEAT]: Give glide typing a tuning profile per language (and the numbers that say why)

## Summary

- Glide typing has 67 settings (`GestureSettings`) and 50 rows in the UI, but the decoder
  also has a second layer nobody can reach: **26 scoring constants** in `Tuning`. Those
  were fitted on **English** swipes and are shipped unchanged for every language.
- I measured the shipped decoder on **2,588 real German swipes**: **71.4 % of swipes
  produce the right word**. On a second German corpus (10,908 swipes, different users and
  app) it is **22.0 %**, or **35.9 %** on the words that corpus can spell and the list
  holds — its targets are rare words, so the word list decides more than the hand. §3
  breaks that down.
- The exposed knobs are already at their optimum: error radii, `sigma` and the result cap
  gave **no gain and several losses**. Do not add more knobs.
- The unreachable constants are the lever. Lowering the **frequency weight** from 1.0 to
  0.5 (plus `gap_weight` 1.33 → 2.0) is worth **+2.9 points** on Wikipedia-like German and
  **+10.6** on the rare-word corpus — and it **costs English 1.1** for `freq 0.5` +
  `gap 2.0` (the older gap+shape+channel profile below cost **1.7**), so it has to be a
  **per-language profile**, not a new default.
- Additionally measured and worth doing: learned shapes (+2.6 / +2.8), compound handling
  where the stroke is decoded (+4.9 ceiling), and an index for the shape-seeding scan
  (5.5× faster). Each is a separate, small change; §5 has effort and evidence.

Everything below is reproducible with public data and the harness in this repo; §11 has
the exact commands, §12 the datasets, §13 every source with URLs.

## 1. The problem, in one paragraph

A glide decoder scores every dictionary word against the stroke: shape cost, frequency of
the word, and a few constants that decide how much each counts. Those constants are a
property of the **language and the word list**, not of the keyboard: German compounds are
rare in every list (median rank 20,714 in the list I measured), English words are not
(median 369). A setting fitted on English therefore under-weights shape and over-weights
frequency for German, and no user-facing knob can fix it — the knobs that exist are about
the stroke's geometry, not about the language model.

The fix is a small table: for each language, the constants the decoder should use. The app
already has per-language infrastructure everywhere else (word lists, layouts, capitalisation,
autocapitalise); the decoder is the one place where one set is used for 300 languages.

## 2. How the measurements were made

- **Decoder:** this repo's own, `native/wm-engine/src/glide/` — the Rust core that
  `GlideBeam` calls over JNI. Not FUTO's, not AOSP's.
- **Shipped tuning:** all 26 fields of Kotlin `GlideBeam.Tuning` equal the Rust
  `Tuning::default()` field by field, so the harness runs the app's values.
- **Metric:** **success per swipe** = a stroke counts if its top-1 word is the intended
  word; a stroke whose word is not in the list counts as a failure. Top-1-within-the-list
  is reported where useful, but it hides the words a list cannot spell.
- **Harness:** `native/wm-engine/examples/glide_beam_eval` with four small local patches
  (§11): column count from the layout, non-ASCII words allowed, a selectable result width,
  an `ALL` mode that scores every stroke, and a per-stroke dump.
- **Not in the harness:** hand model, n-gram rerank, personal lexicon, completion. Learned
  shapes were measured separately (§4.4). Every missing stage can only raise the numbers,
  so all figures are floors.

## 3. What the shipped decoder does

| Corpus | strokes | success per swipe | top-1 where in list |
|---|---|---|---|
| FUTO German (Wikipedia sentences) | 2,588 | 71.41 % | 77.81 % |
| HeliBoard German (frequency⁴ skew) | 10,908 | 21.95 % | 35.90 %* |
| English (FUTO test split, bundled 17 k list) | 2,129 | 81.49 % | — |

\* HeliBoard number restricted to words the a–z layout can spell and the list holds.

### 3.1 Why the HeliBoard number is low (it is the corpus, not the stroke reading)

Isolating one cause at a time on the same strokes:

| Measurement (German) | FUTO | HeliBoard |
|---|---|---|
| targets with `ä ö ü ß` (unproducible on a–z) | 0 % | 16.2 % |
| targets in the 150 k list | 91.8 % | 72.1 % |
| median list rank of the targets | 369 | 20,714 |
| shape only, 1,400 target words, all frequencies 1 | **88.8 %** | **78.5 %** |
| shape only, all targets present, frequencies 1 | 88.8 % (1,400) | 68.0 % (9,723) |
| shape only over the 150 k list, frequencies 1 | 59.3 % | 30.7 % |
| the same list with its real frequencies | **71.4 %** | **21.9 %** |
| median point-to-ideal distance | 0.33 key widths | **0.15** |

Reading it:

- **The strokes are not worse — they are better** (0.15 against 0.33 key widths from the
  ideal path). Nothing here says the HeliBoard input is sloppy.
- At equal vocabulary size (1,400 words, shape only) it is 78.5 % against 88.8 %: some of
  the gap is word confusability, not decoding.
- The 150 k list costs FUTO **+12 points** over uniform frequencies and HeliBoard **−9**:
  the prior is fitted to a distribution FUTO's targets share and HeliBoard's do not.
- 16 % of HeliBoard's targets cannot be spelled on its a–z layout at all, and 28 % are
  outside the list. Those two alone cap the achievable number near 60 %.

Which is exactly why the German profile gains +10.6 there: halving the frequency weight
removes most of the misalignment. It is also why the check-up should fit the weight to the
user's vocabulary rather than printing one number for a language.

The HeliBoard figure is low for two measurable reasons, not because the decoder breaks:
16.2 % of its targets contain `ä ö ü ß`, which an a–z layout cannot produce at all, and
only 49 % of its targets are in the list's top 20 k. Its failures are shape-plausible
neighbours (`verdienten → verdorben`, `arbeitet → arbeiter`, `gebraut → gebaut`), i.e.
frequency wins over shape — the same thing the next section measures directly.

## 4. Findings

### 4.1 The exposed knobs are at their optimum — do not add more

Swept one axis at a time on the FUTO German set (2,375 strokes whose word is in the list, top-1 within the list):

| Axis | Values → result |
|---|---|
| `endRadius` | 1.4 → 76.42 · **2.0 (shipped) → 77.81** · 2.2 → 77.05 · 2.6 → 75.33 |
| `startRadius` | **1.6 (shipped) → 77.81** · 2.0 → 76.76 |
| `nearRadius` | **1.9 (shipped) → 77.81** · 1.9…2.0 → 77.81 (inert) |
| result cap `k = max(2·slots, 8)` | 4 → 77.81 · 8 → 77.89 · 16 → 77.89 · 32 → 77.89 |
| `sigma` | 0.35 → 76.76 · **0.42 (shipped) → 77.81** · 0.50 → 77.81 · 0.60 → 77.31 |

All three radii are within noise of the optimum and anything wider is worse; the result cap
is inert; `sigma` is the best value for random noise. A per-user "fit the radii" feature
would have nothing to win. (Docs note: the options table still lists `endRadius` 1.6; the
code ships 2.0.)

### 4.2 The unreachable constants are English constants

`gap_weight`, `shape_weight` and `shape_channel` are not exposed and were fitted on English
real swipes (`native/bench/futo-swipe/fit_glide.py`). On German:

| Change | FUTO de | HeliBoard de |
|---|---|---|
| shipped (`gap 1.33`, `shape 0.5`, `channel 6`) | 71.41 % | 21.95 % |
| `gap_weight` 2.0 | 73.30 (+1.9) | 25.96 (+4.0) |
| `shape_weight` 1.0 | 72.80 (+1.4) | 28.31 (+6.4) |
| `shape_channel` 12 | 73.18 (+1.8) | 24.32 (+2.4) |
| all three | **74.27 (+2.9)** | **32.51 (+10.6)** |
| English, same all-three profile (`gap 2.0`, `shape 1.0`, `channel 12`) | **79.80 (−1.7)** | — |

Split-half on FUTO: first half +2.4, second half +3.3. So this is not one slice.

### 4.3 The actual cause: the frequency weight

`shape_weight` is a blunt way of changing the balance between shape and frequency. The
direct knob is the weight on `ln(1+frequency)`. Added as `freq_weight` (default 1.0, bounds
scaled with it so pruning stays sound) and swept alone:

| `freq_weight` | FUTO de | HeliBoard de | English |
|---|---|---|---|
| 1.0 (shipped) | 71.41 % | 21.95 % | **81.49 %** |
| 0.8 | 72.84 | 25.60 | 80.98 |
| 0.6 | 73.49 | 28.80 | 80.55 |
| **0.5** | **73.69** | 30.46 | 80.41 |
| 0.4 | 73.38 | 31.94 | 79.66 |
| 0.25 | 71.48 | **32.90** | — |
| 0.0 | 59.27 | — | — |

English is 81.49 shipped, 80.41 with `freq 0.5` (**−1.1**) and the same 80.41 with
`freq 0.5` + `gap 2.0`; the all-three profile in §4.2 (`gap 2.0`, `shape 1.0`,
`channel 12`) is 79.80 (**−1.7**). The two numbers are different profiles, not two
measurements of one.

One number reproduces almost the whole profile, and it is monotonically bad for English —
the signature of a **language** setting. Combined:

| | FUTO de | HeliBoard de |
|---|---|---|
| shipped | 71.41 | 21.95 |
| `freq 0.5` alone | 73.69 | 30.46 |
| `freq 0.5` + `gap 2.0` | **74.27** | **32.51** |
| `freq 0.4` + `gap 2.0` + `channel 12` | 72.99 | **34.38** |

German wants a lower frequency weight the rarer its targets are (0.5 for Wikipedia-like
text, 0.4 for a frequency⁴ corpus). That is exactly why the value should be per language
*and* fit to the user's own vocabulary — see §6.

### 4.4 Learned shapes work on real swipes

"Learn my swipe style" stores a few shapes per word and scores against them. Measured with
one shape per word taken from the word's first occurrence in the corpus (a stranger's hand,
not the user's — so this is a lower bound):

| | FUTO de | HeliBoard de |
|---|---|---|
| decoder only | 71.41 % | 21.95 % |
| + learned shapes | 73.96 % (+2.6) | 24.77 % (+2.8) |
| + language profile | 74.27 % (+2.9) | 32.51 % (+10.6) |
| **profile + shapes** | **76.55 % (+5.1)** | — |

### 4.5 Long words: the lexicon, not the decoder

Coverage of the targets in a 150 k German list, by word length:

| length | in the list | top-1 among those |
|---|---|---|
| ≤ 4 | 99.5 % | — |
| 5–7 | 95.4 % | 69.9 % |
| 8–10 | 87.8 % | 72.5 % |
| 11–14 | **70.2 %** | 65.8 % |
| 15+ | **36.4 %** | 57.1 % |

A word that is not in the trie can never be produced. Adding the 216 missing long words as
an oracle lifts success per swipe **71.4 % → 76.3 %** (+127 strokes, zero regressions).

Generating them into the list does **not** work, and that is worth knowing before trying it:

- A frequency-ranked generator produced 50 k words, **0.8 %** of them real, and recovered
  **0 / 216** missing targets; end-to-end it cost 18 strokes (junk compounds won them).
- A productivity-ranked generator over a 1.16 M corpus produced 583 k words, 1.7 % real,
  recovered **3 / 216**, net −11 strokes.
- Only 115 of the 216 can be split into two parts the 150 k list already contains; the
  other 101 are place names (`Ahlbeck`, `Barnim`), inflections (`Bayerns`) or three-part
  compounds. No decompounder invents `Bundackerweg`.

So compounding has to happen **where the stroke is decoded** (§5.2), not in the list.

The decoder's own limits for long strokes: `SAMPLE_POINTS = 64` regardless of length,
`MAX_IDEAL_POINTS = 32` for the ideal path, `MAX_WORD_LENGTH = 24`
(`Qualitätsmanagementsystem`, 26 letters, cannot be decoded at all), and no length term in
the score.

### 4.6 Shape seeding is the one slow path

`GlideShapeStore.LayoutShapes.wordsNear` scans **every stored shape** on every decode,
previews included, with a `sqrt` per point. On a real 0.6.3 store (3,131 shapes) that is
65.7 µs; at the store's ceiling (`MAX_WORDS = 10000` × up to 20 shapes) it is **2.6 ms per
decode**, 15–45 % of the decoder's own 5.8–17.7 ms.

| Variant | µs/query | factor |
|---|---|---|
| shipped | 65.7 | 1.0× |
| exact squared lower bound (identical results) | 54.4 | 1.2× |
| + bucket by start cell, 1 key, 3×3 | **12.0** | **5.5×** |

100 % top-1 agreement on 3,131 real queries; 9.4 % of shapes scanned.

## 5. Proposal

Five changes, each small and independently shippable. The first is the one this issue is
mostly about.

### 5.1 A tuning profile per language (main request)

Add a per-language table of decoder constants, defaulting to today's values:

| Constant | English | German |
|---|---|---|
| `freq_weight` | 1.0 | **0.5** |
| `gap_weight` | 1.33 | **2.0** |
| everything else | unchanged | unchanged |

- **Why:** +2.9 on Wikipedia-like German, +10.6 on rare-word German, −1.1 if applied to
  English. Measured on two independent German corpora (§4.2, §4.3).
- **Where:** `Tuning` already carries all three; the decode call selects the profile by
  `language.id` next to where the word list is chosen. No new setting, no UI.
- **Scope:** start with German. Languages with rich compounding (Finnish, Dutch, Swedish,
  Norwegian) are the next candidates; the measurement is one harness run away.
- **Follow-up:** let the check-up (§5.5) fit `freq_weight` from the user's own strokes,
  because the optimum moves with what a person writes (0.5 → 0.4 in §4.3).

### 5.2 Compound handling in the decoder

At a word node with stroke left to cover, continue into children and emit the joined
spelling with a damped frequency, instead of ending the word. Bounded by the stroke rather
than by the dictionary, so it handles compounds nobody has written into a list. A
morphological analyzer (`hunspell-jni` is already vendored, and German compounding is one
of its jobs) is the heavier alternative.

**Evidence:** §4.5 (the oracle's +4.9 is the ceiling; list generation captures none of it).

### 5.3 Length-aware resolution

Scale `SAMPLE_POINTS` and `MAX_IDEAL_POINTS` with the word length (e.g. `48 + 2·len`,
ideal `3·len`), and raise `MAX_WORD_LENGTH` to 32. Small, isolated, measured on the same
strokes. A second pass with a minimum length derived from the stroke's arc length (the arc
predicts the letter count with r = 0.93) is the cheap variant.

### 5.4 An index for shape seeding

The exact squared lower bound can go in alone (provably identical). The start-cell bucket
is approximate in theory, so it wants a 5×5 neighbourhood or a full-scan fallback when a
bucket comes back empty. Moving `wordsNear` into the Rust side would also drop the
per-candidate `toTypedArray()` allocation.

### 5.5 A glide check-up (the user-facing feature)

Everything above is a number someone has to choose. The check-up chooses it from the
user's own strokes, reusing what exists:

1. **Profile** — fit the five distortion axes `SwipeCorpus` models (corner cutting, offset,
   scale, early lift, start drift) from the kept paths and show them.
2. **Replay** — re-decode under candidate values, score success per swipe on a held-out
   split. The measured list says: **word list and vocabulary cap** first, then compound
   support, then `freq_weight`; the geometric knobs only if the user's own strokes show a
   gain (§4.1 says they will not).
3. **Propose** — one card, one change, its expected effect on the user's own strokes,
   Apply / Not now, Undo while the setting still holds. Reuse `AssistantProposal` (#788)
   and the sandbox ladder's "measure, then offer" contract (`GlideSandbox`).
4. **Confirm** — after a window, compare the correction rate and offer to revert.

No cloud, no raw stroke storage beyond what exists today (`GlideReadings.STROKE_CAPACITY =
24`), and no proposal without 30 strokes of evidence.

## 6. Why per language, and not one better default

The same numbers, side by side:

| | English | German |
|---|---|---|
| shipped `freq_weight` 1.0 | **81.49 %** | 71.41 % / 21.95 % |
| German value (`freq 0.5` + `gap 2.0`) | 80.41 % (−1.1) | **74.27 % / 32.51 %** |

There is no single value that wins both: German needs shape to outweigh frequency because
its useful words are rare in the list; English does not. The same will be true of other
compounding languages. Keeping one global set means choosing which language to be worse
at — which is the current state.

## 7. What does not work (so nobody spends a week on it)

| Attempt | Result |
|---|---|
| Wider error radii | Neutral to −2.5 points on real German swipes |
| Larger result cap `k` | +0.08 points (inert); FUTO's beam sweep does not transfer, it is about CTC beams |
| Higher `sigma` for sloppy hands | Helps only a *systematic* offset, which `KeyOffsets` already learns; random noise prefers 0.42 |
| A plain length prior (`−β·len`) | 70.87 / 69.59 % at β = 0.1 / 0.3 |
| An arc-length length prior | +0.46 points — real but too small to justify a knob |
| Generating compounds into the list | 0.8–1.7 % real words, 0–3 of 216 targets, net −11 to −18 strokes |
| Bigger word list instead | 1.16 M words: 72.41 % vs 71.41 % at 150 k — depth helps a little, not to the oracle's 76.31 % |
| Per-user `sigma` | Flat to negative unless the hand model is absent |

## 8. How to validate a change

1. **Corpus test** — same strokes, same word list, success per swipe, plus a regression
   set: strokes that were right before and wrong after. That set is the price of a change.
2. **Two corpora** — FUTO's (Wikipedia sentences, common words) and HeliBoard's
   (frequency⁴, rare words). A change that only helps one of them is suspicious.
3. **Language check** — sweep English with the German profile. It must not improve; if it
   does, the constant is not language-specific and belongs in the default.
4. **Project gates** — `GestureEvalBaseline` floors unchanged, `SwipeNoiseSweepTest`
   unaffected when the cost model is untouched.

## 9. Acceptance criteria

- A German profile exists and is selected by language; English output is bit-identical to
  today on the same input (same top-1 on the English harness set).
- German success per swipe improves by ≥ 2 points on both corpora, with no regression set
  larger than 0.5 points.
- No new setting and no new UI for the profile itself.
- The check-up proposes nothing below 30 strokes, states the expected effect, and is
  undoable; a proposal whose setting moved is refused.
- The seeding index returns the same top-1 as today on the stored shapes.

## 10. Out of scope

- Replacing the decoder (a different engine, a different issue).
- New shipped defaults for every language at once; only the German profile is proposed
  here, with the mechanism to add more.
- Replacing the hand model or the shape store; the check-up reads them.

## 11. Reproducing the numbers

```sh
# 1. data: FUTO swipe-5 (MIT) and HeliBoard gesture data (CC BY-SA), see §12/§13
# 2. word lists: FrequencyWords German (§13)
# 3. harness (this repo):
cd native/wm-engine
cargo run --release --example glide_beam_eval -- \
    /tmp/de_swipes.jsonl /tmp/german.json /tmp/de_150k.txt
```

The example needs five small patches to measure a non-English layout. None of them touch
the decoder:

| Patch | Why |
|---|---|
| `COLS` env → `key_width = width / COLS` | the example hard-codes 10 columns; German QWERTZ has 11 |
| allow non-ASCII letters in the word filter | `is_ascii_lowercase` drops every umlaut |
| `RESULTS` env → result width | the example returns 4 candidates; the app shows 6 |
| `ALL=1` → score every stroke | otherwise OOV strokes vanish and the denominator changes per lexicon |
| `DUMP=path` → one line per stroke | needed for a regression set |

## 12. Datasets used (short)

| Dataset | What it is | Size used | Licence |
|---|---|---|---|
| **FUTO `swipe.futo.org`** | real swipes collected by FUTO's web app; `swipe-5` adds other layouts and languages | German: 2,594 single-finger swipes on the 11-column German layout | MIT |
| **HeliBoard Gesture Data Project** | real swipes donated by HeliBoard users, each with the exact key geometry | German: 19,249 records, of which 10,908 single-finger on the a–z QWERTZ | CC BY-SA 4.0 |
| **FrequencyWords (German)** | word lists with raw counts | `de_50k.txt`, `de_150k` (top 150 k of `de_full.txt`, 1,157,685 lines) | MIT (repo) |
| **FUTO English test split** | real English swipes, for the language check | 2,129 strokes with the bundled 17 k list | MIT |

Why these: FUTO's German set is the only public German swipe corpus with a realistic
word-frequency mix (targets at median list rank 369); HeliBoard's balances it with a
rare-word-heavy mix (median rank 20,714) and a different population. The word lists matter
as much as the strokes — a change should be judged on both mixes.

**Attached:** `wmk-glide-de-data.zip` (5 MB) holds the exact slice used here —
`de_swipes.jsonl`, the two layouts, the 150 k word list, and both patches — with a README
that names the licences and the command to reproduce the tables. The HeliBoard set is not
included (93 MB); §13 links it.

## 13. Sources

**Data**

- FUTO swipe corpus (MIT, 1,043,789 swipes in swipe-1; swipe-5 has the other layouts):
  https://huggingface.co/datasets/futo-org/swipe.futo.org
  - file: `swipe-5/swipe5.jsonl` (327,143,325 bytes)
  - layout: `swipe-5/layouts/german.json` (5,807 bytes), `swipe-5/layouts/qwerty.json`
  - collection site: https://swipe.futo.org
- HeliBoard gesture data (CC BY-SA 4.0):
  https://codeberg.org/eclexic/heliboard-gesture-data
  - German files: `compressed/batch_1/de/de-1.gestures.json.zst` (7.9 MB) and `de-2…` (7.3 MB)
  - each record: `targetWord`, `gesture` (x, y, millis, pointer id), `keyboardInfo`
    (width, height, every key's pixel box), `suggestions`, `dictionaries`, `application`
  - API listing: `https://codeberg.org/api/v1/repos/eclexic/heliboard-gesture-data/contents/compressed/batch_1/de`
- FrequencyWords German: https://github.com/hermitdave/FrequencyWords
  - `content/2018/de/de_50k.txt` (662,497 bytes)
  - `content/2018/de/de_full.txt` (17,479,451 bytes, 1,157,685 lines)
- HeliBoard's own gesture project (background, NLnet):
  https://nlnet.nl/project/GestureTyping

**Fetch, verbatim**

```sh
# FUTO swipe corpus (MIT) — German swipes and the layout they were drawn on
curl -L -o swipe5.jsonl https://huggingface.co/datasets/futo-org/swipe.futo.org/resolve/main/swipe-5/swipe5.jsonl
curl -L -o german.json  https://huggingface.co/datasets/futo-org/swipe.futo.org/resolve/main/swipe-5/layouts/german.json
curl -L -o qwerty.json  https://huggingface.co/datasets/futo-org/swipe.futo.org/resolve/main/swipe-5/layouts/qwerty.json

# HeliBoard gesture data (CC BY-SA 4.0), zstd-compressed JSON
curl -L -o de-1.gestures.json.zst \
  https://codeberg.org/eclexic/heliboard-gesture-data/raw/branch/main/compressed/batch_1/de/de-1.gestures.json.zst
curl -L -o de-2.gestures.json.zst \
  https://codeberg.org/eclexic/heliboard-gesture-data/raw/branch/main/compressed/batch_1/de/de-2.gestures.json.zst

# FrequencyWords German
curl -L -o de_50k.txt  https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_50k.txt
curl -L -o de_full.txt https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_full.txt
head -n 150000 de_full.txt > de_150k.txt
```

**Papers and measurements**

- Miller & Kostarevas, *FUTO Swipe: Layout-Agnostic Neural Swipe Decoding*, arXiv:2606.25247
  (2026): https://arxiv.org/abs/2606.25247 — SHARK2 80.05 % vs their encoder 92.94 % on real
  QWERTY swipes; beam 10 → 100 = 88.7 → 92.9 %; per-language scoring tune.
- FUTO Swipe models and model card: https://huggingface.co/futo-org/futo-swipe
- Sivek & Riley, *Spatial model personalization in Gboard*, MobileHCI 2022,
  arXiv:2209.11311 — per-user key offsets for taps; gesture adaptation left as future work.
- Zhang et al., *Neural Search Space in Gboard Decoder*, EMNLP 2024 Industry,
  https://aclanthology.org/2024.emnlp-industry.93/ and arXiv:2410.15575.
- Kristensson & Zhai, *SHARK2*, UIST 2004, https://dl.acm.org/doi/10.1145/1029632.1029640;
  Kristensson, PhD thesis, Linköping 2007.
- Leiva et al., *How We Swipe: A Large-scale Shape-writing Dataset*, MobileHCI 2021,
  https://dl.acm.org/doi/10.1145/3447526.3472059 — test app: https://github.com/luileito/swipetest
- Findlater & Wobbrock, *Personalized input*, CHI 2012,
  https://faculty.washington.edu/wobbrock/pubs/chi-12.03.pdf — simulation gains, no
  user-study gain: the cautionary result for the check-up.
- Smith, Bi & Zhai, *Optimizing Touchscreen Keyboards for Gesture Typing*, CHI 2015,
  https://www.cs.columbia.edu/~brian/projects/optimizing_keyboards.html
- A third-party German evaluation of shipped engines (FUTO 69.7 %, an MIT model 64.7 % on
  HeliBoard's sets): https://huggingface.co/youcoded/swipe-typing (+ `METHODS.md` there)
- FUTO issue on decoder drift over time: https://github.com/futo-org/android-keyboard/issues/332

**This repo**

- Decoder and tuning: `native/wm-engine/src/glide/mod.rs` (`Tuning`, `search_one`,
  `look_ahead`), `core/prediction/.../gesture/GlideBeam.kt` (Kotlin mirror)
- Learning stores: `gesture/KeyOffsets.kt`, `gesture/GlideShapeStore.kt`,
  `prediction/GlideOutcomes.kt`, `prediction/GlideReadings.kt` (`STROKE_CAPACITY = 24`)
- Measure-and-offer and proposals: `prediction/GlideSandbox.kt`,
  `app/assistant/AssistantSettings.kt` (#788)
- Harness: `native/wm-engine/examples/glide_beam_eval.rs`,
  `app/src/test/.../gesture/eval/` (`SwipeCorpus`, `GlideTuningSweepTest`,
  `GlideRealSwipeEval`, `GlideStartDriftLadderTest`)
- Word lists: **FrequencyWords** (§12/§13) — the app's own downloaded lists are not in
  this repository and are not used here. A number measured against the app's German list
  would move in absolute terms; the ordering of the constants does not depend on it.
- Issues referenced: #52 (hand model, shapes), #222 (radii exposed), #262 (correction
  learning), #326 (shapes per word), #213 (start drift), #788 (settings assistant),
  #135/#905 (kept strokes), #28 (vocabulary cap)
