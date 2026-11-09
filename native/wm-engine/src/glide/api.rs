//! The glide decoder's public model: the tuning, the candidates, the sources
//! and the decoder shell. The walk, the costs, the shape channel and the
//! geometry live in their own modules; this one keeps the API the app and the
//! JNI bridge read.

use std::collections::HashMap;

use super::keymap::KeyMap;
use super::loops::LoopScan;
use super::workspace::{self, Workspace};
use crate::fuzzy::{Tier, Walker};

/// A touch point in pixels, with its time in milliseconds.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Point {
    pub x: f32,
    pub y: f32,
    pub t: i64,
}

/// `GlideBeam.Tuning`. Defaults are the shipped ones, fitted on real swipes
/// (`examples/glide_beam_eval`, `native/bench/futo-swipe/fit_glide.py`).
/// `freq_weight` is the weight on `ln(1 + frequency)`, the one field a
/// language profile moves (#966, `GlideLanguageProfiles` on the Kotlin
/// side): every bound carries it too, so the walk's pruning stays sound
/// at any value, and at 1.0 a decode is the unweighted one to the bit.
/// `join_cost` is the charge, in nats, for each join of a compound read
/// as two or three listed words in a row (#966 §5.2); infinite, the
/// default, switches the joining off and the decode is the plain one to
/// the bit. A language profile sets it where the list cannot hold the
/// compounds people swipe. `join_min_part` is the letters every part must
/// have, and `join_part_penalty` the nats each part a join goes on from
/// pays per `ln(1 + frequency)` of its own: the guard that keeps two common
/// short words (`hast` + `alt`) from outbidding the listed `haushalt`
/// (#966, measured on 2,588 German swipes at 8 / 4 / 0.1). At their
/// defaults, 3 and 0, a joined decode is the one before them to the bit.
#[derive(Clone, Debug, PartialEq)]
pub struct Tuning {
    pub sigma: f32,
    pub max_point_cost: f32,
    pub gap_weight: f32,
    pub gap_window: f32,
    pub shape_weight: f64,
    pub freq_weight: f64,
    pub repeat_cost: f32,
    pub unlooped_repeat: f32,
    pub dwell_full: f32,
    pub unclaimed_dwell: f32,
    pub loop_extent: f32,
    pub loop_min_arc: f32,
    pub loop_radius: f32,
    pub wiggle_extent: f32,
    pub wiggle_weight: f32,
    pub loop_exclusion: f32,
    pub unclaimed_loop: f32,
    pub learned_shape_gain: f64,
    pub shape_seeding: bool,
    pub shape_channel: f64,
    pub start_radius: f32,
    pub end_radius: f32,
    pub near_radius: f32,
    pub vocabulary_rank: i32,
    pub look_ahead_cost: f64,
    pub look_ahead_budget: i32,
    pub joiner_cost: f32,
    pub join_cost: f64,
    pub join_min_part: i32,
    pub join_part_penalty: f64,
    /// Runaway backstop on the pops one decode reads; floor pruning ends a
    /// healthy walk far earlier. A per-decode search budget, not a language
    /// weight: clamped to at least 1 at use and never below what a full
    /// decode needs at its default.
    pub max_pops: usize,
    /// Frontier cap on the states one decode may schedule, a per-decode
    /// backstop like `max_pops` rather than a language weight. Clamped to at
    /// least 1 and capped at [`workspace::MAX_STATES`] by the JNI bridge.
    pub max_states: usize,
}

impl Default for Tuning {
    fn default() -> Self {
        Tuning {
            sigma: 0.42,
            max_point_cost: 18.0,
            gap_weight: 1.33,
            gap_window: 32.0,
            shape_weight: 0.5,
            freq_weight: 1.0,
            repeat_cost: 0.8,
            unlooped_repeat: 0.1,
            dwell_full: 2.0,
            unclaimed_dwell: 0.9,
            loop_extent: 0.8,
            loop_min_arc: 1.0,
            loop_radius: 0.6,
            wiggle_extent: 0.0,
            wiggle_weight: 0.0,
            loop_exclusion: 1.5,
            unclaimed_loop: 1.1,
            learned_shape_gain: 0.15,
            shape_seeding: false,
            shape_channel: 6.0,
            start_radius: 1.6,
            end_radius: 2.0,
            near_radius: 1.9,
            vocabulary_rank: 0,
            look_ahead_cost: 1.4,
            look_ahead_budget: 48,
            joiner_cost: 0.2,
            join_cost: f64::INFINITY,
            join_min_part: MIN_JOIN_PART,
            join_part_penalty: 0.0,
            max_pops: MAX_POPS,
            max_states: workspace::MAX_STATES,
        }
    }
}

const MIN_DWELL_FULL: f32 = 0.1;
/// `GlideBeam.Tuning.SLACK_BASE`: the anchor radius past which the score
/// forgives the distance as well as the gate admitting it.
const SLACK_BASE: f32 = 1.6;

/// Letters each part of a compound must have unless the tuning asks for
/// more (#966): `an` + `halt` is not a reading of `anhalt`, it is a search
/// of every short word against every other, and the charge alone would not
/// keep that out of the pool. `Tuning::join_min_part`'s default.
const MIN_JOIN_PART: i32 = 3;
pub(super) const MIN_SAMPLES: usize = 3;

impl Tuning {
    pub(super) fn inv_two_sigma_sq(&self) -> f32 {
        1.0 / (2.0 * self.sigma * self.sigma)
    }
    pub(super) fn start_radius_sq(&self) -> f32 {
        self.start_radius * self.start_radius
    }
    pub(super) fn end_radius_sq(&self) -> f32 {
        self.end_radius * self.end_radius
    }
    pub(super) fn near_cost(&self) -> f32 {
        self.near_radius * self.near_radius * self.inv_two_sigma_sq()
    }
    pub(super) fn loop_radius_sq(&self) -> f32 {
        self.loop_radius * self.loop_radius
    }
    pub(super) fn start_slack(&self) -> f32 {
        (self.start_radius - SLACK_BASE).max(0.0)
    }
    pub(super) fn end_slack(&self) -> f32 {
        (self.end_radius - SLACK_BASE).max(0.0)
    }
    pub(super) fn dwell_scale(&self) -> f32 {
        if self.dwell_full > MIN_DWELL_FULL {
            self.dwell_full
        } else {
            MIN_DWELL_FULL
        }
    }
    /// What `joins` joins cost: nothing for none, which keeps a plain
    /// word's score the plain one even with the joining off (infinite
    /// times zero is not zero).
    pub(super) fn join_charge(&self, joins: i32) -> f64 {
        if joins > 0 {
            self.join_cost * joins as f64
        } else {
            0.0
        }
    }
}

/// `GlideBeam.Candidate`, the word in UTF-16.
#[derive(Clone, Debug, PartialEq)]
pub struct Candidate {
    pub word: Vec<u16>,
    pub score: f64,
    pub shape_cost: f64,
    pub tier: Tier,
    pub ahead: i32,
}

/// `GlideBeam.Alignment`.
#[derive(Clone, Debug, PartialEq)]
pub struct Alignment {
    pub keys: Vec<i32>,
    pub x: Vec<f32>,
    pub y: Vec<f32>,
    pub samples: Vec<i32>,
    pub chars: Vec<i32>,
    pub sample_count: i32,
}

/// One weighted trie for the decoder, with the vocabulary cap as the least
/// frequency a word in it may have (0 for none).
pub struct Source<'a> {
    pub walker: &'a dyn Walker,
    pub log_weight: f64,
    pub tier: Tier,
    pub min_frequency: i32,
}

/// The user's own drawn shapes per word, quantised as the shape store keeps
/// them; empty for a word they have never glided.
pub type LearnedShapes = HashMap<Vec<u16>, Vec<Vec<i8>>>;

/// The marks [`Decoder::marks`] reads in a stroke that a decoder which does
/// not walk the stroke itself can use: each loop as its key and score (a
/// doubled letter there), and whether the stroke closes on a loop (the word
/// ends there).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Marks {
    pub loops: Vec<(i32, f32)>,
    pub ends_on_loop: bool,
}

impl Marks {
    /// The keys `word` visits in order, a letter typed twice in a row
    /// visiting its key once: what a stroke can tell apart. -1 for a letter
    /// the map has no key for.
    pub fn visits(word: &[u16], keys: &KeyMap) -> Vec<i32> {
        let mut out: Vec<i32> = Vec::new();
        for (cp, _) in code_points(word) {
            let key = keys.key_index(cp);
            if out.last() != Some(&key) || key < 0 {
                out.push(key);
            }
        }
        out
    }

    /// Whether `word` types a letter twice in a row on `key`.
    pub fn doubles(word: &[u16], key: i32, keys: &KeyMap) -> bool {
        let letters = code_points(word);
        letters
            .windows(2)
            .any(|w| w[0].0 == w[1].0 && keys.key_index(w[1].0) == key)
    }
}

/// Letters the walk spells at most. 24 until issue #966: a 26-letter
/// compound ("Qualitätsmanagementsystem") could not be read at all.
/// `MAX_IDEAL_POINTS` follows it.
pub const MAX_WORD_LENGTH: i32 = 32;
/// Runaway backstop; floor pruning ends healthy walks far earlier.
///
/// It was 2,000. On 2,588 German swipes with the full list and the 8,192
/// frontier, 4,000 pops read 75.81 top-1 against 75.46; with the 12,288
/// frontier it reads 76.31. The extra pops only run where the walk would
/// otherwise have stopped.
pub const MAX_POPS: usize = 4000;
pub const RESULT_K: usize = 8;
/// `GlideShapeStore.QUANT`.
pub const SHAPE_QUANT: f32 = 10.0;

pub(super) fn is_high(u: u16) -> bool {
    (0xD800..0xDC00).contains(&u)
}

pub(super) fn is_low(u: u16) -> bool {
    (0xDC00..0xE000).contains(&u)
}

/// The code points of a UTF-16 word with each one's starting offset,
/// unpaired surrogates as themselves, as `codePointAt` walks it.
pub(super) fn code_points(word: &[u16]) -> Vec<(i32, usize)> {
    let mut out = Vec::with_capacity(word.len());
    let mut at = 0;
    while at < word.len() {
        let u = word[at];
        if is_high(u) && at + 1 < word.len() && is_low(word[at + 1]) {
            let cp = 0x10000 + (((u as i32) - 0xD800) << 10) + ((word[at + 1] as i32) - 0xDC00);
            out.push((cp, at));
            at += 2;
        } else {
            out.push((u as i32, at));
            at += 1;
        }
    }
    out
}

/// What [`Decoder::decode_ranked`] leaves for [`Decoder::finish`]: the
/// readings and the guesses before the shape channel.
pub struct Ranked {
    pub read: Vec<Candidate>,
    pub guesses: Vec<Candidate>,
    pub look_ahead: usize,
    pub limit: usize,
}

/// What the walk of the last [`Decoder::decode_ranked`] cost: the pops and
/// states it spent, how many readings it ended with, and whether the frontier
/// cap bound. Research diagnostics only; the walk's decisions do not read it.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct DecodeStats {
    pub pops: usize,
    pub states: usize,
    pub read: usize,
    pub saturated: bool,
}

pub struct Decoder {
    pub tuning: Tuning,
    pub ws: Workspace,
    pub(super) scan: LoopScan,
    /// How many of the path's leading samples are the walk up from the
    /// spacebar (#968): a chained stroke's later word starts at the bar's
    /// edge, not on a key. The first letter may stand anywhere on them and
    /// the ones before it cost nothing. `0` for a stroke that started on a
    /// key. Set before `decode`, read by every decode until changed.
    pub open_head: usize,
    /// The same for the trailing samples, the walk down to the bar from a
    /// chained stroke's earlier word.
    pub open_tail: usize,
    /// Diagnostics for the most recent decode; see [`DecodeStats`].
    pub last_stats: DecodeStats,
}

impl Decoder {
    pub fn new(tuning: Tuning) -> Decoder {
        Decoder {
            tuning,
            ws: Workspace::new(),
            scan: LoopScan::default(),
            open_head: 0,
            open_tail: 0,
            last_stats: DecodeStats::default(),
        }
    }
}
