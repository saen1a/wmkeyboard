//! How much the per-context piece-spelling cache saves when a glide previews
//! a largely repeated pool on several frames.
//!
//! A glide decodes on every touch move, and the context model is asked to
//! spell the same handful of unlisted candidates again and again. The first
//! frame pays the piece forward passes; the next frames under the same
//! context should be lookups. This bench picks unlisted words the model can
//! spell, scores them once (cold), then again (warm), and then compares a
//! cached sliding pool against the same pool on a fresh session per frame.
//!
//! A real preview replaces some candidates as the stroke grows; the sliding
//! window here is a synthetic model of that (one word out, one word in).
//!
//! ```text
//! cargo run --release --example lm_cache_bench -- <word list> <model.wmlm> [context words]
//! ```
//!
//! For the German numbers: `de_150k.txt`, `de_context.wmlm`, and
//! `"ich habe das"` as the context.

use std::collections::HashSet;
use std::sync::Arc;
use std::time::{Duration, Instant};

use wm_engine::lm::{token_key, Lm, Prefix, Session, MAX_WORD_PIECES};

const FRAME_WORDS: usize = 16;
const FRAMES: usize = 10;

fn time(mut run: impl FnMut()) -> Duration {
    let started = Instant::now();
    run();
    started.elapsed()
}

fn usage() -> ! {
    eprintln!("usage: lm_cache_bench <word list> <model.wmlm> [context words]");
    std::process::exit(2);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        usage();
    }
    let text = std::fs::read_to_string(&args[1]).expect("word list");
    let lm = Arc::new(Lm::open(std::fs::read(&args[2]).expect("model")).expect("a .wmlm the reader knows"));
    let context: Vec<&str> = args.get(3).map(|s| s.split_whitespace().collect()).unwrap_or_default();

    let mut words: Vec<String> = Vec::new();
    let mut keys: HashSet<String> = HashSet::new();
    for (word, _) in wm_engine::wordlist::parse(&text) {
        let Some(key) = token_key(&word) else { continue };
        if lm.id_of(&key).is_some() {
            continue;
        }
        let Some(pieces) = lm.pieces_of(&key) else { continue };
        if !(2..=MAX_WORD_PIECES).contains(&pieces.len()) {
            continue;
        }
        // `logprob` is keyed by `token_key`, so two spellings of the same key
        // are one cold word, not two.
        if !keys.insert(key) {
            continue;
        }
        words.push(word);
        if words.len() == FRAME_WORDS + FRAMES - 1 {
            break;
        }
    }
    assert!(
        words.len() >= FRAME_WORDS + FRAMES - 1,
        "the list holds too few unlisted words the model can spell: {}",
        words.len()
    );

    let mut cached = Session::new(lm.clone());
    cached.set_context(Prefix::default(), &context);
    cached.distribution();

    let cold_time = time(|| {
        for word in &words[..FRAME_WORDS] {
            cached.logprob(word);
        }
    });
    let warm_time = time(|| {
        for word in &words[..FRAME_WORDS] {
            cached.logprob(word);
        }
    });

    // A preview's pool moves as the stroke grows: one candidate leaves and one
    // arrives, so ten frames over a sixteen-word window are nine new words.
    let slide_time = time(|| {
        for first in 0..FRAMES {
            for word in &words[first..first + FRAME_WORDS] {
                cached.logprob(word);
            }
        }
    });

    // The same sliding pool without the cache: a fresh context per frame. Only
    // the spelling is timed, so the context setup is not part of the comparison.
    let mut uncached_time = Duration::ZERO;
    for first in 0..FRAMES {
        let mut fresh = Session::new(lm.clone());
        fresh.set_context(Prefix::default(), &context);
        fresh.distribution();
        uncached_time += time(|| {
            for word in &words[first..first + FRAME_WORDS] {
                fresh.logprob(word);
            }
        });
    }

    println!(
        "{FRAME_WORDS} words cold {cold_time:?}, warm {warm_time:?} ({:.0}x). \
         {FRAMES}-frame sliding pool: cached {slide_time:?}, fresh context per frame {uncached_time:?} ({:.1}x).",
        cold_time.as_secs_f64() / warm_time.as_secs_f64().max(1e-9),
        uncached_time.as_secs_f64() / slide_time.as_secs_f64().max(1e-9),
    );
}
