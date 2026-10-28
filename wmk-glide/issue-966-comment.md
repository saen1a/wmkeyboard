I built `main` (`22d5020b`) and re-ran both corpora from the zip. Three findings that
survive a clean build, and one note on the tests before you run them.

## 1. Compound joining reads *more* wrong words at the shipped 3.0

Same strokes, same lists, `join_cost=` through the harness (success per swipe):

| `join_cost` | FUTO de (2,588) | HeliBoard de (10,908) |
|---|---|---|
| off (∞) | **71.45 %** | **21.93 %** |
| **3.0 (shipped)** | **66.11 %** | **13.04 %** |
| 5 | 69.40 % | 17.96 % |
| 8 | 71.37 % | 21.50 % |
| 10 | 71.60 % | – |
| 15 | 71.45 % | – |

Neutral at ~10, positive nowhere. It looks structural rather than a bad constant: a join
scores `ln(1 + min(f1, f2))`, so two frequent parts outrank the *listed* word they are part
of, and they also spell non-words that score like one (`hast` + `alt`). German has many
words that are both listed and decomposable; the test checks three.

Two guards worth measuring rather than a different constant: charge the join on the first
part too (`join_cost + λ·ln(1+f1)` — a frequent first part is the strong claim), or only
take a join that beats the best plain reading by a margin, which the floor already gives
you. Until one of them is measured, `joinCost = ∞` is the value the data supports.

## 2. The seeding index drops the case it exists for

`startingNear` returns `null` only when the 3×3 cells hold **no shape at all**
(`total == 0`). A real store has ~40 shapes there (3,131 shapes over ~676 cells), so the
fallback never runs. A qualifying shape starting two cells away — the `can`-starts-near-`v`
case — is dropped as soon as the window holds anything that does not match.

Fall back when the window found **nothing** (`found.isEmpty()`), not when it holds no
shapes; then the second scan only runs on queries that would have come back empty before.
The existing "two cells away" test passes only because that store leaves the cells empty,
so a dense-store variant would pin it.

## 3. `cargo test` is not in CI

`./gradlew unitTests` builds the host library but does not run the crate's own test files.
A `cargo test --release --manifest-path native/wm-engine/Cargo.toml` step would cover
`glide_freq_weight`, `glide_join`, `glide_long_words` and `segment_eval` — and it is the
only place the two below would have shown up before the `.so` rebuild.

## Before you run the new tests

- `at_weight_zero_the_order_is_the_shape_order` fails on `god: goof before gods`. The test
  assumes `freq_weight = 0` leaves the shape term alone, but `finish()`/`rescore_shape()`
  subtracts `shape_channel × d` too (`shape_channel = 6`). `shape_channel = 0.0` in that
  test's `Tuning` makes it pass — the code is right, the premise is not.
- `with_a_finite_charge_a_two_part_word_absent_from_the_list_is_read` is off by 2.77·10⁻⁵
  against a `1e-6` tolerance: `strict_math::ln1p_count` approximates `ln(1+f)` by ~3·10⁻⁵
  while the test uses `f64::ln`. Tolerance `1e-4`, or the same function.

One note for the `.so` rebuild whenever it happens: `tuning()` accepts `v.len() >= 28`
while an older library accepts `>= 26` and reads the first 26, so a stale build decodes
without `freqWeight`/`joinCost` instead of failing. `!= 28`, or a version word, would make
that loud.

## What checked out

- The profile: every `ln1p` site and every bound scaled, bit-identical at 1.0, `de-DE`/
  `de_DE` keyed, `retuneGlide` on language change, JNI order 27/28 on both sides.
  +2.9 / +10.6 reproduce; English unaffected.
- 32 letters and `samples_for`: 4/4 green, Kotlin mirror consistent, sub-40-key strokes
  sampled as before.
- The check-up fits `freqWeight`, not the radii — which is what the numbers support.
