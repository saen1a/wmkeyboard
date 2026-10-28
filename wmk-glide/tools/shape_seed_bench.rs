//! Prototype: exact speed-up for `GlideShapeStore.wordsNear`.
//!
//! The shipped scan computes, for every stored shape, the mean euclidean
//! distance to the drawn stroke and aborts once the running sum passes
//! `radius * n * QUANT`. Each comparison pays a `sqrt`.
//!
//! This variant does the same scan with a *lower bound* first: the mean of the
//! point distances is at least `sqrt(mean of squared distances)`, so a shape
//! whose sum of squared deltas already exceeds `limit^2` can be dropped with
//! integer math and no `sqrt` at all. Survivors are then measured exactly, so
//! the result is identical to the shipped scan — same words, same order.
//!
//! cargo run --release --example shape_seed_bench -- /tmp/shapes.jsonl

use std::collections::HashMap;
use std::io::BufRead;
use std::time::Instant;

const POINTS: usize = 48;
const QUANT: f32 = 10.0;
const RADIUS: f32 = 0.35;
const LIMIT: f32 = RADIUS * POINTS as f32 * QUANT;
const LIMIT_SQ: i32 = (LIMIT * LIMIT) as i32;

struct Shape {
    word: u16,
    bytes: [u8; POINTS * 2],
}

fn decode_hex(s: &str) -> Option<[u8; POINTS * 2]> {
    let b = s.as_bytes();
    if b.len() != POINTS * 4 {
        return None;
    }
    let mut out = [0u8; POINTS * 2];
    for (i, slot) in out.iter_mut().enumerate() {
        let hi = (b[2 * i] as char).to_digit(16)? as u8;
        let lo = (b[2 * i + 1] as char).to_digit(16)? as u8;
        *slot = (hi << 4) | lo;
    }
    Some(out)
}

#[inline]
fn shipped(a: &Shape, b: &[u8; POINTS * 2]) -> f32 {
    let mut sum = 0f32;
    for j in 0..POINTS {
        let dx = (a.bytes[2 * j] as i32 - b[2 * j] as i32) as f32;
        let dy = (a.bytes[2 * j + 1] as i32 - b[2 * j + 1] as i32) as f32;
        sum += (dx * dx + dy * dy).sqrt();
        if sum > LIMIT {
            return RADIUS + 1.0;
        }
    }
    sum / (POINTS as f32 * QUANT)
}

/// Squared lower bound first, exact measurement only for survivors.
#[inline]
fn bounded(a: &Shape, b: &[u8; POINTS * 2]) -> f32 {
    let mut sq = 0i32;
    for j in 0..POINTS {
        let dx = a.bytes[2 * j] as i32 - b[2 * j] as i32;
        let dy = a.bytes[2 * j + 1] as i32 - b[2 * j + 1] as i32;
        sq += dx * dx + dy * dy;
        if sq > LIMIT_SQ {
            return RADIUS + 1.0;
        }
    }
    let mut sum = 0f32;
    for j in 0..POINTS {
        let dx = (a.bytes[2 * j] as i32 - b[2 * j] as i32) as f32;
        let dy = (a.bytes[2 * j + 1] as i32 - b[2 * j + 1] as i32) as f32;
        sum += (dx * dx + dy * dy).sqrt();
    }
    sum / (POINTS as f32 * QUANT)
}

fn collect(shapes: &[Shape], query: &[u8; POINTS * 2], limit: usize, f: fn(&Shape, &[u8; POINTS * 2]) -> f32) -> Vec<(u16, f32)> {
    let mut found: Vec<(u16, f32)> = Vec::with_capacity(16);
    for s in shapes {
        let d = f(s, query);
        if d > RADIUS {
            continue;
        }
        match found.iter_mut().find(|(w, _)| *w == s.word) {
            Some(slot) => {
                if d < slot.1 {
                    slot.1 = d;
                }
            }
            None => found.push((s.word, d)),
        }
    }
    found.sort_by(|a, b| a.1.total_cmp(&b.1));
    found.truncate(limit);
    found
}

/// Shapes bucketed by the cell their stroke starts in, 2 key widths a side.
/// A new stroke of a seeded word starts near the stored one, which is exactly
/// what seeding is for, so one 3x3 neighbourhood is scanned instead of all.
const CELL: i32 = 10;

fn cell_of(x: u8, y: u8) -> (i32, i32) {
    (x as i32 / CELL, y as i32 / CELL)
}

fn collect_bucketed(
    shapes: &[Shape],
    index: &HashMap<(i32, i32), Vec<usize>>,
    query: &[u8; POINTS * 2],
    limit: usize,
) -> (Vec<(u16, f32)>, usize) {
    let (cx, cy) = cell_of(query[0], query[1]);
    let mut found: Vec<(u16, f32)> = Vec::with_capacity(16);
    let mut scanned = 0usize;
    for dx in -1..=1 {
        for dy in -1..=1 {
            let Some(bucket) = index.get(&(cx + dx, cy + dy)) else { continue };
            for &i in bucket {
                scanned += 1;
                let s = &shapes[i];
                let d = bounded(s, query);
                if d > RADIUS {
                    continue;
                }
                match found.iter_mut().find(|(w, _)| *w == s.word) {
                    Some(slot) => {
                        if d < slot.1 {
                            slot.1 = d;
                        }
                    }
                    None => found.push((s.word, d)),
                }
            }
        }
    }
    found.sort_by(|a, b| a.1.total_cmp(&b.1));
    found.truncate(limit);
    (found, scanned)
}

fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| "/tmp/shapes.jsonl".into());
    let file = std::io::BufReader::new(std::fs::File::open(&path).expect("shapes"));
    let mut words: Vec<String> = Vec::new();
    let mut shapes: Vec<Shape> = Vec::new();
    for line in file.lines().map_while(Result::ok) {
        let v: serde_json::Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let (Some(word), Some(hex)) = (v["word"].as_str(), v["shape"].as_str()) else { continue };
        let Some(bytes) = decode_hex(hex) else { continue };
        let id = words.iter().position(|w| w == word).unwrap_or_else(|| {
            words.push(word.to_string());
            words.len() - 1
        }) as u16;
        shapes.push(Shape { word: id, bytes });
    }
    println!("shapes {} words {}", shapes.len(), words.len());

    // Queries: every stored shape nudged by one quantisation step, so the query
    // is near a real stroke without being the stored one.
    let queries: Vec<[u8; POINTS * 2]> = shapes
        .iter()
        .map(|s| {
            let mut q = s.bytes;
            for (i, b) in q.iter_mut().enumerate() {
                *b = b.wrapping_add((i % 3) as u8);
            }
            q
        })
        .collect();

    let mut differs = 0usize;
    for q in queries.iter().take(400) {
        let a = collect(&shapes, q, 8, shipped);
        let b = collect(&shapes, q, 8, bounded);
        if a != b {
            differs += 1;
        }
    }
    println!("result mismatches over 400 queries: {differs}");

    // --- bucketed lookup -------------------------------------------------
    let mut index: HashMap<(i32, i32), Vec<usize>> = HashMap::new();
    for (i, s) in shapes.iter().enumerate() {
        index.entry(cell_of(s.bytes[0], s.bytes[1])).or_default().push(i);
    }
    let within = index.values().map(|v| v.len()).max().unwrap_or(0);
    println!("buckets {} largest {within} shapes", index.len());
    for (label, amp) in [("0.1 key", 1u8), ("0.3 key", 3u8), ("0.8 key", 8u8)] {
        let qs: Vec<[u8; POINTS * 2]> = shapes
            .iter()
            .map(|s| {
                let mut q = s.bytes;
                for (i, b) in q.iter_mut().enumerate() {
                    let step = (i % 5) as i32 - 2;
                    let d = (step * amp as i32 / 2) as i32;
                    *b = b.saturating_add_signed(d as i32 as i8);
                }
                q
            })
            .collect();
        let (mut agree, mut base_hits, mut word_found) = (0usize, 0usize, 0usize);
        let mut scanned = 0usize;
        for (s, q) in shapes.iter().zip(&qs) {
            let base = collect(&shapes, q, 8, shipped);
            let (b, n) = collect_bucketed(&shapes, &index, q, 8);
            scanned += n;
            if let Some((w, _)) = base.first() {
                base_hits += 1;
                if b.first().map(|x| x.0) == Some(*w) {
                    agree += 1;
                }
            }
            if b.iter().any(|(w, _)| *w == s.word) {
                word_found += 1;
            }
        }
        let t = Instant::now();
        for q in &qs {
            let _ = collect_bucketed(&shapes, &index, q, 8);
        }
        println!(
            "noise {label}: top-1 agrees {agree}/{base_hits}, stored word kept {word_found}/{total}, scanned {pct:.1}% of shapes, {us:.1} µs/query",
            total = shapes.len(),
            pct = 100.0 * scanned as f64 / (shapes.len() * shapes.len()) as f64,
            us = t.elapsed().as_secs_f64() * 1e6 / qs.len() as f64
        );
    }

    let run = |f: fn(&Shape, &[u8; POINTS * 2]) -> f32| {
        let t = Instant::now();
        let mut sink = 0usize;
        for q in &queries {
            sink += collect(&shapes, q, 8, f).len();
        }
        (t.elapsed(), sink)
    };

    for round in 0..3 {
        let (t1, s1) = run(shipped);
        let (t2, s2) = run(bounded);
        assert_eq!(s1, s2);
        println!(
            "round {round}: shipped {:>8.1} µs/query   bounded {:>8.1} µs/query   speedup {:.2}×",
            t1.as_secs_f64() * 1e6 / queries.len() as f64,
            t2.as_secs_f64() * 1e6 / queries.len() as f64,
            t1.as_secs_f64() / t2.as_secs_f64()
        );
    }

    // Scale: the store's ceiling is MAX_WORDS 10000 × shapesPerWord, so repeat
    // the real store until it is the size a heavy user reaches.
    let mut big: Vec<Shape> = Vec::new();
    while big.len() < 125_000 {
        big.extend(shapes.iter().map(|s| Shape { word: s.word, bytes: s.bytes }));
    }
    println!("scaled store: {} shapes", big.len());
    for round in 0..2 {
        let t1 = Instant::now();
        for q in queries.iter().take(200) {
            let _ = collect(&big, q, 8, shipped);
        }
        let t2 = Instant::now();
        for q in queries.iter().take(200) {
            let _ = collect(&big, q, 8, bounded);
        }
        println!(
            "round {round}: shipped {:>8.1} µs/query   bounded {:>8.1} µs/query   speedup {:.2}×",
            t1.elapsed().as_secs_f64() * 1e6 / 200.0,
            t2.elapsed().as_secs_f64() * 1e6 / 200.0,
            t1.elapsed().as_secs_f64() / t2.elapsed().as_secs_f64()
        );
    }
}
