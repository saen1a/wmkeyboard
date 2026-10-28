Follow-up on the open items from my earlier comment. I re-ran everything on
`22d5020b`, implemented the engine changes locally, and measured them. The work is in a
private checkout, not a public branch you can look at, so this report is self-contained:
every constant, call site, score term and test is below, including the harness additions
and the measurement scripts, so it can be rebuilt without any file from me.

Numbers are success per swipe on FUTO German (2,588 strokes, `ALL=1 RESULTS=4 COLS=11`),
decoder only. All rows in a table come from one run; my profile baseline is 74.15 % here
vs 74.27 % in the issue text, from `RESULTS`/revision, not a new finding.

## 0. Result in one table

| Run (FUTO German, 2,588) | top-1 | top-4 |
|---|---|---|
| shipped tuning | 71.45 | 82.30 |
| German profile (`freq 0.5 gap 2.0`) | 74.15 | 82.81 |
| German profile + bare `join_cost 3.0` | 70.63 | 79.60 |
| German profile + guard (`8 / 4 / 0.1`) | **74.61** | **83.31** |

And on the 2,294 strokes that have a previous word (the rerank subset): **70.84 -> 80.82**
with the capped context blend at `0.7 / 3.0`.

**Bottom line for German:** the largest lever measured today is a **real compound list**
(150k + 441k observed compounds: **75.70 / 84.23**, §2.6), not the blend. The blend needs
a German `.wmlm`; the catalog has none, so it is inert on a German device until one is
trained and published (§2.5).

## 1. Reproduce the basis

```sh
git clone https://github.com/wasi-master/wmkeyboard && cd wmkeyboard
git checkout 22d5020b
cd native/wm-engine
cargo build --release --example glide_beam_eval
```

Data: FUTO swipe-5, German strokes and the layout they were drawn on (MIT), plus the
FrequencyWords German list (MIT). The issue body has the URLs. The measurement set is
`swipe-5/swipe5.jsonl` filtered to `language == "de"`, `layout == "german"`,
`dual_finger == 0` (2,594 records; the harness then drops six short/non-letter targets,
hence n = 2,588); `swipe-5/layouts/german.json` as the layout; and the first 150,000 lines
of `content/2018/de/de_full.txt` as `de_150k.txt`. Keep `word`, `canvas_width`,
`canvas_height` and the normalised `data` points when filtering. The harness takes the
records, the layout and the word list as its three arguments.

The harness at `22d5020b` already has `COLS`, `ALL`, `RESULTS`, `DUMP` and `THREADS`. Two
additions are needed for this work:

1. The two new tuning keys, in `set()` in `examples/glide_beam_eval.rs`:

```rust
"join_min_part" => t.join_min_part = value as i32,
"join_part_penalty" => t.join_part_penalty = value,
```

2. `DUMP` must write every candidate's score, not only the top word. Replace the dump
   line in the same file with:

```rust
if dump_on {
    let top = words.first().map(String::as_str).unwrap_or("-");
    let pool = out
        .iter()
        .map(|c| format!("{}:{:.6}", String::from_utf16_lossy(&c.word).to_lowercase(), c.score))
        .collect::<Vec<_>>()
        .join("|");
    lines.push(format!("{}\t{top}\t{}\t{}\t{}", r.word, hit as u8, known.contains(&r.word) as u8, pool));
}
```

A dump line is then `target \t top \t hit \t in_list \t word:score|word:score|...` in the
decoder's order (best first).

Baseline and guard:

```sh
# shipped
COLS=11 ALL=1 THREADS=8 RESULTS=4 ./target/release/examples/glide_beam_eval \
    de_swipes.jsonl german.json de_150k.txt

# German profile, then the guarded join
printf 'freq_weight=0.5 gap_weight=2.0\nfreq_weight=0.5 gap_weight=2.0 join_cost=8 join_min_part=4 join_part_penalty=0.1\n' \
  | COLS=11 ALL=1 THREADS=8 RESULTS=4 ./target/release/examples/glide_beam_eval \
    de_swipes.jsonl german.json de_150k.txt
```

## 2. Context blend in the glide path

### 2.1 The change

`SuggestionEngine.finishGlide` currently goes `filtered -> rerankGlide -> shiftGlideScores`.
Insert the score-space blend **before** the rank-unit rerank, as the typing path does:

```kotlin
val filtered = words.filterNot { suppressed(it.word) }
if (filtered.isEmpty()) return filtered
val blended = blendGlideContextModel(filtered)
val reranked = rerankGlide(blended, previousWord, previousWord2, previousWord3, recentWords)
return shiftGlideScores(reranked)
```

The function is new and private in `SuggestionEngine`:

```kotlin
private fun blendGlideContextModel(decoded: List<GlideBeam.Candidate>): List<GlideBeam.Candidate> {
    val model = contextModel ?: return decoded
    if (decoded.size < 2) return decoded
    val words = decoded.map { it.word }
    val scores = model.scores(words)
    val reference = scores.firstOrNull() ?: return decoded
    if (reference.isNaN()) return decoded
    var moved = false
    val shifted = decoded.mapIndexed { i, candidate ->
        val lp = scores.getOrNull(i) ?: return@mapIndexed candidate
        if (lp.isNaN()) return@mapIndexed candidate
        val shift = (GLIDE_LM_BLEND * (lp - reference)).coerceIn(-GLIDE_LM_BLEND_CAP, GLIDE_LM_BLEND_CAP)
        if (shift == 0.0) {
            candidate
        } else {
            moved = true
            GlideBeam.Candidate(candidate.word, candidate.score + shift, candidate.shapeCost, candidate.tier, candidate.ahead)
        }
    }
    if (!moved) return decoded
    return shifted.sortedByDescending { it.score } // stable: ties keep the decoder's order
}
```

Constants, next to `LM_BLEND` / `LM_BLEND_CAP` in the companion object:

```kotlin
const val GLIDE_LM_BLEND = 0.7
const val GLIDE_LM_BLEND_CAP = 3.0
```

The typing path stays at `0.2 / 1.0`. The blend uses the leader's log-probability as the
reference, so the leader never moves; a word the model cannot read (`NaN`) keeps its
decoder score. It runs before the rank-unit rerank, so the blend sets the incoming order
and the reranker can still reorder on its own evidence. `GLIDE_RERANK_POOL` stays 8.

### 2.2 Why 0.7 / 3.0

The cap sweep on the same pool (2,294 strokes with a previous word). The language model in
this measurement is a corpus bigram built from the `sentence` field of the strokes, the
same stand-in as `rerank_eval.py`, not the downloaded `.wmlm`:

| cap | w=0.5 | 0.7 | 1.0 | 1.5 |
|---|---|---|---|---|
| 1.0 | 75.41 | 75.37 | 75.33 | 75.33 |
| 1.5 | 77.07 | 77.03 | 76.94 | 76.94 |
| 2.0 | 78.60 | 78.47 | 78.38 | 78.33 |
| 2.5 | 79.82 | 79.86 | 79.60 | 79.56 |
| **3.0** | 80.73 | **80.82** | 80.56 | 80.21 |
| 4.0 | 81.34 | 81.73 | 81.65 | 81.26 |
| uncapped | 81.65 | 82.39 | 82.91 | **83.13** |

The uncapped ceiling at this pool is 83.13; 3 nats is the requested 2–3 range and costs
~2 points against it. On the device the `.wmlm` has a different nats scale, so treat
0.7/3.0 as a starting point and re-sweep the weight once with the real model.

### 2.3 The exact measurement

Dump the top 8 with scores:

```sh
ALL=1 THREADS=8 RESULTS=8 COLS=11 DUMP=pool.jsonl \
    ./target/release/examples/glide_beam_eval de_swipes.jsonl german.json de_150k.txt
```

The pool rows are aligned with the harness's filtered stroke list (same predicate: at
least two letters, alphabetic). The subset is `word_idx > 0` and a non-empty pool; it is
2,294 of the 2,588. The bigram model is built from the stroke file's `sentence` fields:

- tokenise with `[^\wäöüß]` removed, lower-cased;
- unigram `(count + 1) / (total + vocab)`;
- bigram `(count + 0.3 * pu * previous) / (previous + 0.3)`, interpolated with
  `0.7 * pb + 0.3 * pu`;
- `logp(word, prev)` falls back to the unigram when `prev` was never seen.

The full sweep script (reads the dump and the stroke file, prints the table):

```python
#!/usr/bin/env python3
import json, math, re, sys
from collections import Counter

LAMBDA = 0.7
WEIGHTS = (0.5, 0.7, 1.0, 1.5)
CAPS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, float("inf"))

def tokens(s):
    return [re.sub(r"[^\wäöüß]", "", t.lower()) for t in s.split()]

def load_dump(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        pool = []
        for part in f[4].split("|"):
            if part:
                w, _, s = part.rpartition(":")
                if s: pool.append((w, float(s)))
        rows.append((f[0], pool))
    return rows

def load_strokes(path):
    out = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line); w = r["word"].lower()
        if len(w) >= 2 and w.isalpha(): out.append(r)
    return out

rows = load_dump(sys.argv[1]); strokes = load_strokes(sys.argv[2])
assert len(rows) == len(strokes)
uni, bi, prev = Counter(), Counter(), Counter()
for r in strokes:
    t = [x for x in tokens(r.get("sentence", "")) if x]
    for w in t: uni[w] += 1
    for a, b in zip(t, t[1:]): bi[(a, b)] += 1; prev[a] += 1
total, vocab = sum(uni.values()), len(uni)

def logp(w, p):
    pu = (uni[w] + 1) / (total + vocab)
    if prev[p] == 0: return math.log(pu)
    pb = (bi[(p, w)] + 0.3 * pu * prev[p]) / (prev[p] + 0.3)
    return math.log(LAMBDA * pb + (1 - LAMBDA) * pu)

def prev_of(r):
    t = [x for x in tokens(r.get("sentence", "")) if x]
    i = r.get("word_idx", 0) - 1
    return t[i] if 0 <= i < len(t) else None

subset = [(i, r) for i, r in enumerate(strokes) if prev_of(r) and rows[i][1]]
print(f"n={len(subset)} baseline={100 * sum(rows[i][1][0][0] == rows[i][0] for i, _ in subset) / len(subset):.2f} %")
for cap in CAPS:
    cells = []
    for w in WEIGHTS:
        hit = 0
        for i, r in subset:
            pool, p = rows[i][1], prev_of(r)
            ref = logp(pool[0][0], p)
            best = max(pool, key=lambda c: c[1] + max(-cap, min(cap, w * (logp(c[0], p) - ref))))
            hit += best[0] == rows[i][0]
        cells.append(100 * hit / len(subset))
    print(f"{cap:>5} " + " ".join(f"{x:6.2f}" for x in cells))
```

For the shipped `0.7 / 3.0` the script prints `80.82`.

### 2.4 Held-out check

The 80.82 above is **in-sample**: the corpus bigram is built from the same sentences it
is evaluated on. On a 20 % sentence split (SHA-256; the LM is built on the other 80 %),
the same blend gives **68.97 -> 69.17 (+0.20)**. The train LM has only a 1,293-word
vocabulary and the target is in its top-50 for 34.9 % of the held-out strokes, so this is
a small-corpus lower bound, not the device number. A real `.wmlm` is trained on a much
larger corpus; the device gain should sit between +0.2 and the in-sample +10, and it needs
to be measured on a held-out sentence set before anyone quotes 80.82 as a product number.

The same held-out check kills the easy follow-ups:

- **Wider pool** (8 -> 16 -> 32) with the 3-nat cap: **81.04 at every width**; the extra
  candidates are more than 3 nats behind. Uncapped it is +0.48 from 8 to 32, so the cap,
  not the pool, is binding.
- **Trigram instead of bigram**: +0.43 in-sample at cap 3, **+0.00 on the held-out split**.
  The real `.wmlm` already conditions on the sentence.
- **Frequency exponent** `ln(1+f)^a`: top-1 is best at a = 1.0 (74.15); a = 1.2 buys
  +0.50 top-4 but loses 0.66 top-1.
- **Cap as a function of stroke spread** (sloppy strokes trust the LM more): the real
  strokes have a median spread of 0.572 key widths; the best fixed cap is as good as the
  spread-dependent one (69.17 held-out), and trusting sloppy strokes less loses.
- **Cache/recent words**: +0.08 at best; only 91 of 2,294 strokes have a pool candidate
  that appeared earlier in the same sentence, so this corpus cannot measure it.
- **Learned 9-feature logit** over the pool: 67.92 on the held-out split against 69.17 for
  the simple capped blend. It overfits the training sentences; not shippable at this size.
- **Compound score/prior**: a full-list bonus or a 471k part-pair table adds **+0.12** on
  the guard pool. Only 25 of the 118 joinable targets reach the top-32 pool; the gap is
  candidate generation, not scoring. A full-list/compound **source** (the 1.16M list was
  72.41 % against 71.45 with shipped tuning; with the German profile it is 75.46, §2.6)
  is the direction, not another join constant.
- **LM top-N as an extra source**: the target is in the held-out top-50 for 34.9 %, and
  when it is, the decoder reads it (33.3 % extra-only vs 34.9 % in-list, ~95 %). Combined
  main + source: 69.43 against 68.84 (+0.59). This is the one extension with a clear
  mechanism beyond the pool ceiling, but it needs the real `.wmlm` and per-word logp; the
  small corpus LM is too weak to show more.

### 2.5 There is no German `.wmlm`

`ContextModelCatalog` publishes `en` and `bn_rom` only. German has an **n-gram pack**
(`data/de/de_bigrams.txt.gz` + `de_trigrams.txt.gz`, about 1.3 MB), not a neural model, so
`contextModel` is null on a German device and `blendGlideContextModel` is a no-op there.
The blend patch only pays off once a German `.wmlm` is trained and published
(`tools/wmlm`).

What the real German pack does on the same strokes (2,294 with a previous word):

| use of the pack | top-1 |
|---|---|
| decoder | 70.84 |
| score-space blend (the shipped `blendGlideContextModel`) | 69.83 (negative) |
| rank-unit rerank (the `NgramReranker` path already in the app) | **71.3 (+0.45)** |
| pack top-50 as a context source; target outside the decoder pool | **0.4–1.2 %** |

So the only German context gain available **today** is the pack reranker: **+0.45**, not
+10. The score blend with the pack loses because its frequency scale does not match the
decoder's nats. A pack context source has almost no headroom: when the decoder misses the
target, it is rarely in the pack's top-N (2–6 of 506 strokes). The earlier high outside-pool
recall was the in-sample corpus bigram leaking the test sentence, not the pack.

Consequence: for German the first item is not a tuning field but a **German `.wmlm`** (or a
better pack reranker). The blend patch is correct for languages with a model; it is inert
for German until that model exists. This is not hypothetical: the published **English**
`.wmlm` on English FUTO strokes gives **+4.9 top-1** with the same 0.7/3.0 blend (known
words, 1,824 strokes: 73.41 -> 78.34; +5.8 uncapped). A German model trained on comparable
data should land in the same range (+3 to +5 on the 74.15 German base).

### 2.6 A real compound list is the best German lever

The 150k list misses the compounds people swipe. Generating compounds was a net loss
(under 2 % were words), but the **full FrequencyWords list already contains real
compounds**. Take every `de_full` word absent from `de_150k` that splits into two
`de_150k` words (both parts at least three letters) and keep its observed frequency:
**441,470 real words**, no generation. German profile, `RESULTS=4 COLS=11`:

| dictionary | top-1 | top-4 |
|---|---|---|
| 150k | 74.15 | 82.81 |
| **150k + 441k real compounds** | **75.70** | **84.23** |
| 150k + 346k (parts >= 4) | 75.58 | 84.20 |
| full 1.16M list | 75.46 | 84.39 |
| **150k + 441k + join guard** | **75.77** | **84.47** |

That is **+1.55 top-1 / +1.42 top-4** from a data change, more than the guard (+0.46) and
more than the German pack rerank (+0.45). The curated 591k list even beats the full 1.16M
list on top-1 because it leaves out the rare non-compounds. The join guard still adds a
little on top (+0.07/+0.24), but the list is the bigger lever. The builder is
`tools/build_compound_list.py`; the result is a dictionary/word-list addition, not an
engine patch.

## 3. Compound guard

### 3.1 The change (Rust)

`Tuning` in `native/wm-engine/src/glide/mod.rs` gets two fields, with the old behaviour as
the defaults:

```rust
pub join_min_part: i32,       // default MIN_JOIN_PART (3)
pub join_part_penalty: f64,   // default 0.0
```

`Workspace` in `native/wm-engine/src/glide/workspace.rs` carries the accumulated penalty
per state, copied from the parent on every push (0 at the root):

```rust
pub join_penalty: Vec<f64>,
```

`reset()` clears it, and `push()` copies `join_penalty[parent]` (or pushes `0.0` at the
root). In `search_one`, the state's charge becomes:

```rust
// join charge plus the common-part penalties this state already earned
let charge = tuning.join_charge(joins) + self.ws.join_penalty[s];
```

The emit score subtracts `charge` as before. The join is now gated on the configured part
length, and every part that the walk joins *past* pays its own penalty:

```rust
if join_on
    && joins < MAX_JOINS
    && length - part_from >= tuning.join_min_part
    && (length + tuning.join_min_part) as usize <= n
    && walker.is_word(node)
    && walker.frequency(node) >= min_frequency
{
    let cap = lm_cap(part_freq, walker.frequency(node));
    let floor_cost = self.ws.floor_cost[s];
    let part_penalty = tuning.join_part_penalty * ln1p(walker.frequency(node));
    let bound = src.log_weight + tuning.freq_weight * ln1p(lm_cap(cap, walker.max_subtree(root)))
        - tuning.shape_weight * (floor_cost + extra) as f64
        - tuning.join_charge(joins + 1)
        - self.ws.join_penalty[s]
        - part_penalty;
    if bound >= floor - EPS {
        if let Some(id) = self.ws.push(root, s as i32, NO_LABEL, last_key, length, extra, floor_cost, bound, self.ws.letter_cp[s]) {
            self.ws.part_freq[id] = cap;
            self.ws.part_from[id] = length;
            self.ws.joins[id] = joins + 1;
            self.ws.join_penalty[id] = self.ws.join_penalty[s] + part_penalty;
            self.ws.copy_column(s, id);
        }
    }
}
```

The last part of a reading is not charged: it is not followed by a join. The same
`join_penalty[s]` is subtracted in `descend_silent` and in `look_ahead`, so every bound
stays an upper bound and the pruning stays exact.

This penalises the first part in the same form as `λ·ln(1+f1)`, and also the middle parts of
a three-part compound (`bundes` + `verfassungs` + `gericht`), which is where the common
short tails (`nun`, `alt`) come from.

### 3.2 Kotlin and JNI

`GlideBeam.Tuning` gets the same two fields after `joinCost`:

```kotlin
val joinMinPart: Int = 3,
val joinPartPenalty: Double = 0.0,
```

`NativeGlide.tuningArray` appends them after `joinCost`:

```kotlin
lookAheadBudget.toDouble(), joinerCost.toDouble(), freqWeight, joinCost,
joinMinPart.toDouble(), joinPartPenalty,
```

and `wm-engine-jni/src/glide.rs` reads them at the new indices. The Kotlin array now has 30 values; `tuning()` requires at least 30
(`if v.len() < 30 { return None; }`) and reads:

```rust
join_min_part: v[28] as i32,
join_part_penalty: v[29],
```

`GlideLanguageProfiles.Profile` carries the two fields and copies them in `applyTo`:

```kotlin
class Profile(
    val freqWeight: Double,
    val gapWeight: Float,
    val joinCost: Double,
    val joinMinPart: Int,
    val joinPartPenalty: Double,
) {
    fun applyTo(tuning: GlideBeam.Tuning): GlideBeam.Tuning =
        if (tuning.freqWeight == freqWeight && tuning.gapWeight == gapWeight &&
            tuning.joinCost == joinCost && tuning.joinMinPart == joinMinPart &&
            tuning.joinPartPenalty == joinPartPenalty
        ) {
            tuning
        } else {
            tuning.copy(
                freqWeight = freqWeight, gapWeight = gapWeight, joinCost = joinCost,
                joinMinPart = joinMinPart, joinPartPenalty = joinPartPenalty,
            )
        }
}
```

`DEFAULT` passes `Tuning.DEFAULT`'s five values; the German profile becomes:

```kotlin
val GERMAN = Profile(
    freqWeight = 0.5,
    gapWeight = 2.0f,
    joinCost = 8.0,
    joinMinPart = 4,
    joinPartPenalty = 0.1,
)
```

The `.so` must be rebuilt before this ships. A 28-value Kotlin caller against the new
library returns no candidates instead of silently dropping the two fields. An old library
with a new 30-value caller still ignores the extra values, so the `.so` rebuild is required, not optional.

### 3.3 Why this guard

`join_cost 3.0` with the bare `ln(1 + min(f1, f2))` score was a net loss: two common parts
outbid the listed word and spell non-words (`hast` + `alt` over `haushalt`). The four-letter
floor removes the shortest false splits; the per-part charge makes common parts pay.

I also measured the margin-over-best-plain-reading guard suggested earlier: a post-filter
that keeps a join only when it beats the best listed reading by `m` nats. On the join dumps
at `join_cost 3`, `m = 3` recovers 66.11 -> 68.70 (still below plain 71.45); at 8/10 it is
neutral to negative. So the length/penalty guard is the one that measured positive.

The oracle (target absent from the list and splittable into two listed words of at least
three letters each) is **118/2,588 = 4.56 %**. The guard captures about a tenth of it. The
rest is not reachable with part frequencies: `bundes` (122) + `ministerium` (903) loses to a
wrong split of common words (`binden` + `nun`), which needs compound frequencies or a
compound LM.

The oracle count, without a separate file:

```python
import json
known = {l.split()[0].lower() for l in open("de_150k.txt", encoding="utf-8") if l.split()}
targets = [json.loads(l)["word"].lower() for l in open("de_swipes.jsonl", encoding="utf-8")]
targets = [w for w in targets if len(w) >= 2 and w.isalpha()]
def joinable(w):
    return any(w[:i] in known and w[i:] in known for i in range(3, len(w) - 2))
hits = [w for w in targets if w not in known and joinable(w)]
print(len(hits), len(targets), 100 * len(hits) / len(targets))  # 118 2588 4.56
```

### 3.4 The guard test

Add to `native/wm-engine/tests/glide_join.rs`; it reuses the file's existing `list()`,
`swipe()` and `decode()` helpers:

```rust
#[test]
fn a_four_letter_floor_keeps_a_three_letter_tail_from_joining() {
    let trie = list();
    let mut guarded = Decoder::new(Tuning { join_cost: 2.0, join_min_part: 4, ..Tuning::default() });
    let false_compound = decode(&mut guarded, &trie, &swipe("hastalt"));
    assert!(
        false_compound.iter().all(|c| word_of(c) != "hastalt"),
        "hastalt read: {:?}",
        false_compound.iter().map(word_of).collect::<Vec<_>>()
    );
    let compound = decode(&mut guarded, &trie, &swipe("haushalt"));
    assert_eq!(compound.first().map(word_of).as_deref(), Some("haushalt"));
}
```

## 4. Tests and CI

The two red tests:

- `glide_freq_weight.rs`, `at_weight_zero_the_order_is_the_shape_order`: the premise is
  that the score is the shape term alone, but `shape_channel` is a separate learned-shape
  term. Set it to zero in that decoder:

```rust
let mut none = Decoder::new(Tuning { freq_weight: 0.0, shape_channel: 0.0, ..Tuning::default() });
```

- `glide_join.rs`, `with_a_finite_charge_a_two_part_word_absent_from_the_list_is_read`:
  `ln1p_count` approximates the trie count on ~3e-5 nats while the test uses `f64::ln`.
  Tolerance `1e-4` instead of `1e-6`:

```rust
assert!((top.score - expected).abs() < 1e-4, "{compound}: {} vs {expected}", top.score);
```

CI, in `.github/workflows/ci.yml`, before the Gradle step, and add both crates to the
cache's `workspaces`:

```yaml
workspaces: |
  native/wm-engine
  native/wm-engine-jni

# later, before ./gradlew unitTests
- name: Test the Rust engine
  run: cargo test --release --manifest-path native/wm-engine/Cargo.toml
```

The full engine run is `496 + 3 + 5 + 4` green: 496 unit tests, 3 in
`glide_freq_weight`, 5 in `glide_join` (including the new floor test), 4 in
`glide_long_words`; `segment_eval` is the ignored one. Also update `app/src/test/.../GlideLanguageProfilesTest.kt`: it asserts the German
profile is `8.0 / 4 / 0.1` and resets `joinMinPart`/`joinPartPenalty` to the defaults in
its "nothing else moves" copy:

```kotlin
assertEquals(8.0, tuned.joinCost, 0.0)
assertEquals(4, tuned.joinMinPart)
assertEquals(0.1, tuned.joinPartPenalty, 0.0)
assertEquals(
    GlideBeam.Tuning.DEFAULT,
    tuned.copy(
        freqWeight = 1.0,
        gapWeight = GlideBeam.Tuning.DEFAULT.gapWeight,
        joinCost = Double.POSITIVE_INFINITY,
        joinMinPart = GlideBeam.Tuning.DEFAULT.joinMinPart,
        joinPartPenalty = GlideBeam.Tuning.DEFAULT.joinPartPenalty,
    ),
)
```

## 5. What is not here

The seeding fallback from my earlier comment is untouched. HeliBoard was not re-fetched,
so the guard is unmeasured on that corpus. The blend is fitted on the corpus bigram; the
real `.wmlm` still has to confirm 0.7/3.0.

## 6. Files touched

Engine and call path: `native/wm-engine/src/glide/mod.rs`,
`native/wm-engine/src/glide/workspace.rs`, `native/wm-engine-jni/src/glide.rs`,
`core/prediction/.../SuggestionEngine.kt`, `core/prediction/.../GlideBeam.kt`,
`core/prediction/.../GlideLanguageProfiles.kt`, `core/prediction/.../NativeGlide.kt`.

Tests and CI: `native/wm-engine/tests/glide_freq_weight.rs`,
`native/wm-engine/tests/glide_join.rs`,
`app/src/test/.../GlideLanguageProfilesTest.kt`, `.github/workflows/ci.yml`.

Measurement only, not shipped: `native/wm-engine/examples/glide_beam_eval.rs` (the two
tuning keys and the scored pool dump).

I have not opened a PR. The engine + test diff is ready; if you want it, say so and I can
paste it or prepare the patch series. The compound list is a data change on top of that,
not part of the five patches.
