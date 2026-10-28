//! Does a per-stroke LM next-word list add readable candidates?
//!
//! Reads the same records/layout/list as `glide_beam_eval`, plus a JSONL file
//! with one array of words per stroke (the LM's top-N next words). Decodes
//! against the main trie and a per-stroke trie of those words, and prints how
//! often the target is in the extra list and how often it is read top-1.

use std::io::{BufRead, Write};

use wm_engine::fuzzy::Tier;
use wm_engine::glide::keymap::KeyMap;
use wm_engine::glide::{Decoder, Point, Source, Tuning};
use wm_engine::user_lexicon::UserTrie;

struct Record { word: String, width: f32, height: f32, points: Vec<Point> }

fn number(v: &serde_json::Value, key: &str) -> f32 { v[key].as_f64().unwrap_or(0.0) as f32 }

fn key_width(w: f32) -> f32 {
    let cols: f32 = std::env::var("COLS").ok().and_then(|v| v.parse().ok()).unwrap_or(11.0);
    w / cols
}
fn keymap(layout: &[(i32, f32, f32)], width: f32, height: f32) -> KeyMap {
    let kw = key_width(width);
    let mut order: Vec<usize> = (0..layout.len()).collect();
    order.sort_by_key(|&i| layout[i].0);
    let xs = layout.iter().map(|k| k.1 * width / kw).collect();
    let ys = layout.iter().map(|k| k.2 * height / kw).collect();
    let sorted = order.iter().map(|&i| layout[i].0).collect();
    let key_of = order.iter().map(|&i| i as i32).collect();
    KeyMap::new(xs, ys, sorted, key_of)
}

fn extra_freq_default() -> i32 { 1000 }

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let layout_json: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&args[2]).unwrap()).unwrap();
    let layout: Vec<(i32, f32, f32)> = layout_json["keys"].as_array().unwrap().iter()
        .filter_map(|k| Some((k["letter"].as_str()?.chars().next()? as i32, number(k, "cx"), number(k, "cy"))))
        .collect();
    let text = std::fs::read_to_string(&args[3]).unwrap();
    let mut trie = UserTrie::new();
    for (word, frequency) in wm_engine::wordlist::parse(&text) { trie.insert(&word, frequency); }
    let extra_file = std::io::BufReader::new(std::fs::File::open(&args[4]).unwrap());
    let extra_scale: f64 = std::env::var("EXTRA_SCALE").ok().and_then(|v| v.parse().ok()).unwrap_or(1e6);
    let extras: Vec<Vec<(String, i32)>> = extra_file.lines().map_while(Result::ok).map(|l| {
        let v: serde_json::Value = serde_json::from_str(&l).unwrap_or_default();
        v.as_array().unwrap_or(&vec![]).iter().filter_map(|e| {
            if let Some(w) = e.as_str() { return Some((w.to_lowercase(), extra_freq_default())); }
            let a = e.as_array()?;
            let w = a.first()?.as_str()?.to_lowercase();
            let lp = a.get(1)?.as_f64()?;
            Some((w, (lp.exp() * extra_scale).round().max(1.0) as i32))
        }).collect()
    }).collect();
    let extra_freq: i32 = std::env::var("EXTRA_FREQ").ok().and_then(|v| v.parse().ok()).unwrap_or(1000);
    let extra_weight: f64 = std::env::var("EXTRA_WEIGHT").ok().and_then(|v| v.parse().ok()).unwrap_or(0.0);
    let extra_only = std::env::var("EXTRA_ONLY").is_ok_and(|v| v == "1");
    let results: usize = std::env::var("RESULTS").ok().and_then(|v| v.parse().ok()).unwrap_or(8);
    let threads: usize = std::env::var("THREADS").ok().and_then(|v| v.parse().ok()).unwrap_or(8);

    let records: Vec<Record> = std::io::BufReader::new(std::fs::File::open(&args[1]).unwrap()).lines().map_while(Result::ok)
        .filter_map(|line| {
            let v: serde_json::Value = serde_json::from_str(&line).ok()?;
            let word = v["word"].as_str()?.to_lowercase();
            if word.chars().count() < 2 || !word.chars().all(char::is_alphabetic) { return None; }
            let (width, height) = (number(&v, "canvas_width"), number(&v, "canvas_height"));
            let points = v["data"].as_array()?.iter().map(|p| Point { x: number(p, "x") * width, y: number(p, "y") * height, t: p["t"].as_i64().unwrap_or(0) }).collect();
            Some(Record { word, width, height, points })
        }).collect();
    assert_eq!(records.len(), extras.len(), "records vs extra lines");
    eprintln!("{} strokes", records.len());

    let chunk = records.len().div_ceil(threads).max(1);
    let tallies: Vec<(usize, usize, usize, usize, usize)> = std::thread::scope(|scope| {
        let handles: Vec<_> = records.chunks(chunk).enumerate().map(|(ci, part)| {
            let (trie, layout, extras) = (&trie, &layout, &extras);
            scope.spawn(move || {
                let mut decoder = Decoder::new(Tuning::default());
                let (mut n, mut top1, mut top4, mut in_extra, mut extra_top1) = (0, 0, 0, 0, 0);
                for (j, r) in part.iter().enumerate() {
                    let i = ci * chunk + j;
                    let words = &extras[i];
                    let mut et = UserTrie::new();
                    for (w, f) in words { et.insert(w, *f); }
                    let keys = keymap(layout, r.width, r.height);
                    let mut sources = vec![];
                    if !extra_only { sources.push(Source { walker: trie, log_weight: 0.0, tier: Tier::Dictionary, min_frequency: 0 }); }
                    sources.push(Source { walker: &et, log_weight: extra_weight, tier: Tier::User, min_frequency: 0 });
                    let out = decoder.decode(&r.points, &keys, key_width(r.width), &sources, results, None, 0);
                    let got: Vec<String> = out.iter().map(|c| String::from_utf16_lossy(&c.word).to_lowercase()).collect();
                    n += 1;
                    top1 += (got.first() == Some(&r.word)) as usize;
                    top4 += (got.iter().take(4).any(|w| *w == r.word)) as usize;
                    in_extra += words.iter().any(|(w, _)| *w == r.word) as usize;
                    extra_top1 += (got.iter().find(|w| words.iter().any(|(x, _)| x == *w)) == Some(&r.word)) as usize;
                }
                (n, top1, top4, in_extra, extra_top1)
            })
        }).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let (mut n, mut top1, mut top4, mut in_extra, mut extra_top1) = (0, 0, 0, 0, 0);
    for (a, b, c, d, e) in tallies { n += a; top1 += b; top4 += c; in_extra += d; extra_top1 += e; }
    println!(
        "n {n} | top1 {:.4} top4 {:.4} | target in extra {:.4} | target read among extras top1 {:.4} | extra_freq {extra_freq} weight {extra_weight} only {extra_only}",
        top1 as f64 / n as f64, top4 as f64 / n as f64, in_extra as f64 / n as f64, extra_top1 as f64 / n as f64
    );
    std::io::stdout().flush().ok();
}
