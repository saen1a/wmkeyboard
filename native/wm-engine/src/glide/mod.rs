//! The glide decoder: the Kotlin `GlideBeam` (core/gesture), line for line.
//! A best-first lattice over the dictionary trie itself; see the Kotlin
//! class for the model (the alignment, the bound, the loops and pauses, the
//! shape channel), which is kept there with its measurements.
//!
//! Arithmetic follows the Kotlin types exactly: `Float` is `f32`, `Double`
//! is `f64`, the same operations in the same order, logarithms through
//! [`strict_math`], so a decode returns the same candidates with the same
//! scores to the bit. The user's learned shapes are passed in by the caller
//! ([`LearnedShapes`]); the vocabulary cap arrives as each source's minimum
//! frequency, which the caller reads off its own rank tables.

mod api;
mod costs;
mod geometry;
mod search;
mod shape;

pub mod ctc;
pub mod duet;
pub mod keymap;
pub mod loops;
pub mod workspace;

pub use api::{
    Alignment, Candidate, DecodeStats, Decoder, LearnedShapes, Marks, Point, Ranked, Source,
    Tuning, MAX_POPS, MAX_WORD_LENGTH, RESULT_K, SHAPE_QUANT,
};
pub use geometry::{open_run, OPEN_RUN_BEND, OPEN_RUN_DESCENT, OPEN_RUN_LEVEL};

use search::by_score;

#[cfg(test)]
use crate::fuzzy::Tier;
#[cfg(test)]
use keymap::KeyMap;
#[cfg(test)]
use workspace::{Workspace, NO_LABEL};

#[cfg(test)]
mod kernel_parity {
    //! The band kernels (`kernels::band`) against their scalar references
    //! through whole decodes: the scalar path is the loop the Kotlin oracles
    //! were matched against, so equal decodes here keep that parity.

    use super::duet::{DuetDecoder, Token};
    use super::*;
    use crate::kernels::testing::{Rng, FORCE};
    use crate::kernels::{active, set_force_scalar};
    use crate::user_lexicon::UserTrie;

    const ROWS: [(&str, f32); 3] = [("qwertyuiop", 0.0), ("asdfghjkl", 0.5), ("zxcvbnm", 1.5)];
    const KEY_W: f32 = 60.0;
    const KEY_H: f32 = 84.0;

    fn centre(c: char) -> (f32, f32) {
        for (row, (letters, offset)) in ROWS.iter().enumerate() {
            if let Some(i) = letters.find(c) {
                return (
                    (offset + i as f32 + 0.5) * KEY_W,
                    (row as f32 + 0.5) * KEY_H,
                );
            }
        }
        unreachable!()
    }

    fn keymap() -> KeyMap {
        let mut letters: Vec<char> = ROWS.iter().flat_map(|(l, _)| l.chars()).collect();
        letters.sort();
        let xs = letters.iter().map(|&c| centre(c).0 / KEY_W).collect();
        let ys = letters.iter().map(|&c| centre(c).1 / KEY_W).collect();
        let cps = letters.iter().map(|&c| c as i32).collect();
        KeyMap::new(xs, ys, cps, (0..letters.len() as i32).collect())
    }

    fn gauss(r: &mut Rng) -> f32 {
        let u = (r.f32() as f64).max(1e-9);
        ((-2.0 * u.ln()).sqrt() * (2.0 * std::f64::consts::PI * r.f32() as f64).cos()) as f32
    }

    /// The Phase 0 harness's swipe: jittered corners, a point every 4 ms.
    fn swipe(word: &str, r: &mut Rng) -> Vec<Point> {
        let corners: Vec<(f32, f32)> = word
            .chars()
            .map(|c| {
                let (x, y) = centre(c);
                (x + gauss(r) * 0.2 * KEY_W, y + gauss(r) * 0.2 * KEY_H)
            })
            .collect();
        let mut out = vec![Point {
            x: corners[0].0,
            y: corners[0].1,
            t: 0,
        }];
        let mut t = 0;
        for w in corners.windows(2) {
            let ((ax, ay), (bx, by)) = (w[0], w[1]);
            let len = ((bx - ax) * (bx - ax) + (by - ay) * (by - ay)).sqrt();
            let steps = ((len / KEY_W * 35.0 / 4.0) as usize).max(1);
            for s in 1..=steps {
                t += 4;
                let f = s as f32 / steps as f32;
                out.push(Point {
                    x: ax + (bx - ax) * f + gauss(r) * 1.5,
                    y: ay + (by - ay) * f + gauss(r) * 1.5,
                    t,
                });
            }
        }
        out
    }

    fn both<T: PartialEq + std::fmt::Debug>(mut run: impl FnMut() -> T) -> T {
        set_force_scalar(true);
        let reference = run();
        set_force_scalar(false);
        let kernels = run();
        assert_eq!(reference, kernels);
        kernels
    }

    #[test]
    fn decodes_are_the_same_with_and_without_the_band_kernels() {
        let _pinned = FORCE.lock().unwrap_or_else(|e| e.into_inner());
        let text = std::fs::read_to_string(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../app/dictionaries-src/en.txt"
        ))
        .unwrap();
        let entries = crate::wordlist::parse(&text);
        let mut trie = UserTrie::new();
        for (w, f) in &entries {
            trie.insert(w, *f);
        }
        let sources = [Source {
            walker: &trie,
            log_weight: 0.0,
            tier: Tier::Dictionary,
            min_frequency: 0,
        }];
        let keys = keymap();
        let words: Vec<&str> = entries
            .iter()
            .map(|(w, _)| w.as_str())
            .filter(|w| (3..=10).contains(&w.len()) && w.chars().all(|c| c.is_ascii_lowercase()))
            .take(4000)
            .collect();
        let mut r = Rng::new(7);
        let mut decoder = Decoder::new(Tuning::default());
        let mut duet = DuetDecoder::default();
        let mut candidates = 0;
        for _ in 0..150 {
            let word = words[r.below(words.len() as u64) as usize];
            let path = swipe(word, &mut r);
            for ahead in [0, 1] {
                candidates +=
                    both(|| decoder.decode(&path, &keys, KEY_W, &sources, 8, None, ahead)).len();
            }
            // Live previews: the stroke so far, six times.
            for step in 1..=6 {
                let upto = path.len() * step / 6;
                if upto >= 3 {
                    both(|| decoder.decode(&path[..upto], &keys, KEY_W, &sources, 8, None, 1));
                }
            }
            for partial in [false, true] {
                let tokens = [Token::Swipe(path.clone())];
                candidates +=
                    both(|| duet.decode(&tokens, &keys, KEY_W, &sources, 8, partial)).len();
            }
        }
        #[cfg(target_arch = "aarch64")]
        assert!(active().neon, "the kernels must have run");
        assert!(candidates > 1000, "{candidates} candidates");
    }
}

#[cfg(test)]
mod chained {
    //! Open ends (#968): a segment of a glide that crossed the spacebar ends
    //! or starts at the bar's edge, and the walk there is not a letter.

    use super::*;
    use crate::user_lexicon::UserTrie;

    const ROWS: [(&str, f32); 3] = [("qwertyuiop", 0.0), ("asdfghjkl", 0.5), ("zxcvbnm", 1.5)];
    const KEY_W: f32 = 60.0;
    const KEY_H: f32 = 84.0;
    /// The bar's top edge: right under the bottom row.
    const BAR_TOP: f32 = 3.0 * KEY_H;

    fn centre(c: char) -> (f32, f32) {
        for (row, (letters, offset)) in ROWS.iter().enumerate() {
            if let Some(i) = letters.find(c) {
                return (
                    (offset + i as f32 + 0.5) * KEY_W,
                    (row as f32 + 0.5) * KEY_H,
                );
            }
        }
        unreachable!()
    }

    fn keymap() -> KeyMap {
        let mut letters: Vec<char> = ROWS.iter().flat_map(|(l, _)| l.chars()).collect();
        letters.sort();
        let xs = letters.iter().map(|&c| centre(c).0 / KEY_W).collect();
        let ys = letters.iter().map(|&c| centre(c).1 / KEY_W).collect();
        let cps = letters.iter().map(|&c| c as i32).collect();
        KeyMap::new(xs, ys, cps, (0..letters.len() as i32).collect())
    }

    /// A straight line from `from` to `to`, a sample every eighth of a key.
    fn line(out: &mut Vec<Point>, from: (f32, f32), to: (f32, f32)) {
        let len = ((to.0 - from.0).powi(2) + (to.1 - from.1).powi(2)).sqrt();
        let steps = ((len / KEY_W) * 8.0).ceil().max(1.0) as usize;
        let t0 = out.last().map_or(0, |p| p.t);
        for s in 1..=steps {
            let f = s as f32 / steps as f32;
            out.push(Point {
                x: from.0 + (to.0 - from.0) * f,
                y: from.1 + (to.1 - from.1) * f,
                t: t0 + 4 * s as i64,
            });
        }
    }

    /// The word drawn centre to centre, no jitter.
    fn swipe(word: &str) -> Vec<Point> {
        let mut out = vec![Point {
            x: centre(word.chars().next().unwrap()).0,
            y: centre(word.chars().next().unwrap()).1,
            t: 0,
        }];
        let chars: Vec<char> = word.chars().collect();
        for w in chars.windows(2) {
            line(&mut out, centre(w[0]), centre(w[1]));
        }
        out
    }

    /// `word` then straight down to the bar's edge: a chained stroke's earlier segment.
    fn walked_to_bar(word: &str) -> Vec<Point> {
        let mut out = swipe(word);
        let last = *out.last().unwrap();
        line(&mut out, (last.x, last.y), (last.x, BAR_TOP));
        out
    }

    /// Up from the bar's edge into `word`: a chained stroke's later segment.
    fn begun_at_bar(word: &str) -> Vec<Point> {
        let first = centre(word.chars().next().unwrap());
        let mut out = vec![Point {
            x: first.0,
            y: BAR_TOP,
            t: 0,
        }];
        line(&mut out, (first.0, BAR_TOP), first);
        out.extend(
            swipe(word)
                .into_iter()
                .skip(1)
                .map(|p| Point { t: p.t + 400, ..p }),
        );
        out
    }

    fn trie() -> UserTrie {
        let text = std::fs::read_to_string(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../app/dictionaries-src/en.txt"
        ))
        .unwrap();
        let mut trie = UserTrie::new();
        for (word, frequency) in crate::wordlist::parse(&text) {
            trie.insert(&word, frequency);
        }
        trie
    }

    fn top(decoder: &mut Decoder, trie: &UserTrie, path: &[Point]) -> Option<String> {
        let sources = [Source {
            walker: trie,
            log_weight: 0.0,
            tier: Tier::Dictionary,
            min_frequency: 0,
        }];
        decoder
            .decode(path, &keymap(), KEY_W, &sources, 4, None, 0)
            .first()
            .map(|c| String::from_utf16_lossy(&c.word))
    }

    #[test]
    fn the_walk_to_the_bar_is_an_open_run_and_a_plain_word_has_none() {
        let walked = walked_to_bar("the");
        let run = open_run(&walked, KEY_W, true);
        // From e (top row) to the bar is a little over two and a half rows
        // straight down: well over the twenty samples a two-row walk has.
        assert!(run >= 20, "{run}");
        assert_eq!(open_run(&swipe("the"), KEY_W, true), 0);
        let begun = begun_at_bar("cat");
        assert!(open_run(&begun, KEY_W, false) >= 4);
    }

    #[test]
    fn a_diagonal_walk_is_a_run_and_it_stops_at_the_corner() {
        // "top" ends far right of the bar; the walk from p makes for its end.
        let mut walked = swipe("top");
        let (last, drawn) = (*walked.last().unwrap(), walked.len());
        let bar = (last.x - 2.0 * KEY_W, BAR_TOP);
        line(&mut walked, (last.x, last.y), bar);
        let run = open_run(&walked, KEY_W, true);
        // The whole walk, and at most the sample the corner is drawn from.
        assert!(
            (walked.len() - drawn..=walked.len() - drawn + 1).contains(&run),
            "{run}"
        );
    }

    #[test]
    fn words_walked_to_the_bar_read_with_an_open_tail() {
        let trie = trie();
        let mut decoder = Decoder::new(Tuning::default());
        for word in ["the", "then", "want", "similar", "going"] {
            let path = walked_to_bar(word);
            decoder.open_tail = open_run(&path, KEY_W, true);
            assert_eq!(
                top(&mut decoder, &trie, &path).as_deref(),
                Some(word),
                "{word} with an open tail"
            );
            decoder.open_tail = 0;
        }
    }

    #[test]
    fn words_begun_at_the_bar_read_with_an_open_head() {
        let trie = trie();
        let mut decoder = Decoder::new(Tuning::default());
        for word in ["cat", "dog", "to", "understanding", "people"] {
            let path = begun_at_bar(word);
            decoder.open_head = open_run(&path, KEY_W, false);
            assert_eq!(
                top(&mut decoder, &trie, &path).as_deref(),
                Some(word),
                "{word} with an open head"
            );
            decoder.open_head = 0;
        }
    }

    #[test]
    fn an_ordinary_stroke_is_unchanged_by_zero_open_ends() {
        let trie = trie();
        let mut decoder = Decoder::new(Tuning::default());
        let path = swipe("keyboard");
        assert_eq!(top(&mut decoder, &trie, &path).as_deref(), Some("keyboard"));
    }

    #[test]
    fn the_default_budgets_are_the_shipped_constants() {
        let tuning = Tuning::default();
        assert_eq!(tuning.max_pops, MAX_POPS);
        assert_eq!(tuning.max_states, workspace::MAX_STATES);
    }

    #[test]
    fn the_workspace_honours_its_state_cap_and_reports_saturation() {
        let mut ws = Workspace::new();
        ws.max_states = 1;
        assert!(ws.push(0, -1, NO_LABEL, -1, 0, 0.0, 0.0, 0.0, 0).is_some());
        assert!(ws.push(1, -1, NO_LABEL, -1, 0, 0.0, 0.0, 0.0, 0).is_none());
        assert!(ws.saturated);
    }

    #[test]
    fn a_tiny_pop_budget_stops_the_walk_before_it_finds_a_word() {
        let trie = trie();
        let path = swipe("the");
        let mut shipped = Decoder::new(Tuning::default());
        assert_eq!(top(&mut shipped, &trie, &path).as_deref(), Some("the"));
        let mut capped = Decoder::new(Tuning {
            max_pops: 1,
            ..Tuning::default()
        });
        assert_eq!(top(&mut capped, &trie, &path), None);
    }
}
