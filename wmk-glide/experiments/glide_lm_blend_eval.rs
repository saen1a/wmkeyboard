//! The glide pool re-ranked by a real `.wmlm` in score space, the way
//! `SuggestionEngine.blendGlideContextModel` does it: score + clamp(w*(lp-lp_leader)).
//!
//! cargo run --release --example glide_lm_blend_eval -- records.jsonl layout.json list.txt model.wmlm
//!
//! `RESULTS=8`, `COLS=10`, `THREADS=8`, `WEIGHT=0.7`, `CAP=3`. Prints no-blend and
//! blended top-1/top-4, and the number of strokes with a previous word.

use std::io::{BufRead, Write};
use std::sync::Arc;

use wm_engine::fuzzy::Tier;
use wm_engine::glide::keymap::KeyMap;
use wm_engine::glide::{Decoder, Point, Source, Tuning};
use wm_engine::lm::{Lm, Prefix, Session};
use wm_engine::user_lexicon::UserTrie;

struct Record { word: String, sentence: String, word_idx: usize, width: f32, height: f32, points: Vec<Point> }
fn number(v: &serde_json::Value, key: &str) -> f32 { v[key].as_f64().unwrap_or(0.0) as f32 }
fn keymap(layout: &[(i32, f32, f32)], width: f32, height: f32, cols: f32) -> KeyMap {
    let kw = width / cols;
    let mut order: Vec<usize> = (0..layout.len()).collect();
    order.sort_by_key(|&i| layout[i].0);
    let xs = layout.iter().map(|k| k.1 * width / kw).collect();
    let ys = layout.iter().map(|k| k.2 * height / kw).collect();
    let sorted = order.iter().map(|&i| layout[i].0).collect();
    let key_of = order.iter().map(|&i| i as i32).collect();
    KeyMap::new(xs, ys, sorted, key_of)
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let layout_json: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&args[2]).unwrap()).unwrap();
    let layout: Vec<(i32, f32, f32)> = layout_json["keys"].as_array().unwrap().iter()
        .filter_map(|k| Some((k["letter"].as_str()?.chars().next()? as i32, number(k, "cx"), number(k, "cy")))).collect();
    let text = std::fs::read_to_string(&args[3]).unwrap();
    let mut trie = UserTrie::new();
    for (word, frequency) in wm_engine::wordlist::parse(&text) { trie.insert(&word, frequency); }
    let lm = Arc::new(Lm::open(std::fs::read(&args[4]).unwrap()).expect("a .wmlm"));
    let cols: f32 = std::env::var("COLS").ok().and_then(|v| v.parse().ok()).unwrap_or(10.0);
    let results: usize = std::env::var("RESULTS").ok().and_then(|v| v.parse().ok()).unwrap_or(8);
    let threads: usize = std::env::var("THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(8);
    let weight: f64 = std::env::var("WEIGHT").ok().and_then(|v| v.parse().ok()).unwrap_or(0.7);
    let cap: f64 = std::env::var("CAP").ok().and_then(|v| v.parse().ok()).unwrap_or(3.0);
    let records: Vec<Record> = std::io::BufReader::new(std::fs::File::open(&args[1]).unwrap()).lines().map_while(Result::ok)
        .filter_map(|line| {
            let v: serde_json::Value = serde_json::from_str(&line).ok()?;
            let word = v["word"].as_str()?.to_lowercase();
            if word.chars().count() < 2 || !word.chars().all(char::is_alphabetic) { return None; }
            let (width, height) = (number(&v, "canvas_width"), number(&v, "canvas_height"));
            let points = v["data"].as_array()?.iter().map(|p| Point { x: number(p, "x") * width, y: number(p, "y") * height, t: p["t"].as_i64().unwrap_or(0) }).collect();
            Some(Record { word, sentence: v["sentence"].as_str().unwrap_or("").to_string(), word_idx: v["word_idx"].as_u64().unwrap_or(0) as usize, width, height, points })
        }).collect();
    eprintln!("{} strokes", records.len());
    let chunk = records.len().div_ceil(threads).max(1);
    let tallies: Vec<(usize, usize, usize, usize, usize, usize, usize)> = std::thread::scope(|scope| {
        let handles: Vec<_> = records.chunks(chunk).map(|part| {
            let (trie, layout, lm) = (&trie, &layout, &lm);
            scope.spawn(move || {
                let mut decoder = Decoder::new(Tuning::default());
                let mut session = Session::new(lm.clone());
                let (mut n, mut top1, mut top4, mut b1, mut b4, mut with_prev, mut moved) = (0,0,0,0,0,0,0);
                for r in part {
                    let keys = keymap(layout, r.width, r.height, cols);
                    let sources = [Source { walker: trie, log_weight: 0.0, tier: Tier::Dictionary, min_frequency: 0 }];
                    let out = decoder.decode(&r.points, &keys, r.width / cols, &sources, results, None, 0);
                    let words: Vec<String> = out.iter().map(|c| String::from_utf16_lossy(&c.word).to_lowercase()).collect();
                    n += 1;
                    top1 += (words.first() == Some(&r.word)) as usize;
                    top4 += (words.iter().take(4).any(|w| *w == r.word)) as usize;
                    // Context: the sentence's words before the target.
                    let ctx: Vec<&str> = r.sentence.split_whitespace().take(r.word_idx).collect();
                    let mut blended: Vec<(String, f64)> = out.iter().zip(words.iter()).map(|(c, w)| (w.clone(), c.score)).collect();
                    if !ctx.is_empty() && blended.len() > 1 {
                        with_prev += 1;
                        session.set_context(Prefix::default(), &ctx);
                        let lps: Vec<Option<f32>> = words.iter().map(|w| session.logprob(w)).collect();
                        if let Some(Some(reference)) = lps.first().copied() {
                            let mut any = false;
                            for (i, (_, score)) in blended.iter_mut().enumerate() {
                                if let Some(lp) = lps[i] {
                                    let shift = (weight * (lp - reference) as f64).clamp(-cap, cap);
                                    if shift != 0.0 { *score += shift; any = true; }
                                }
                            }
                            if any {
                                moved += 1;
                                let best = blended.iter().max_by(|a, b| a.1.total_cmp(&b.1)).map(|x| &x.0).cloned().unwrap_or_default();
                                b1 += (best == r.word) as usize;
                                blended.sort_by(|a, b| b.1.total_cmp(&a.1));
                                b4 += (blended.iter().take(4).any(|(w, _)| *w == r.word)) as usize;
                                continue;
                            }
                        }
                    }
                    b1 += (words.first() == Some(&r.word)) as usize;
                    b4 += (words.iter().take(4).any(|w| *w == r.word)) as usize;
                }
                (n, top1, top4, b1, b4, with_prev, moved)
            })
        }).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let (mut n, mut top1, mut top4, mut b1, mut b4, mut wp, mut moved) = (0,0,0,0,0,0,0);
    for (a,b,c,d,e,f,g) in tallies { n+=a; top1+=b; top4+=c; b1+=d; b4+=e; wp+=f; moved+=g; }
    println!("n {n} | no blend top1 {:.4} top4 {:.4} | blend top1 {:.4} top4 {:.4} | with prev {wp} moved {moved} | w {weight} cap {cap}",
        top1 as f64/n as f64, top4 as f64/n as f64, b1 as f64/n as f64, b4 as f64/n as f64);
    std::io::stdout().flush().ok();
}
