//! The walk: the best-first lattice over the dictionary trie, and the shape
//! channel's caller. The cost tables it reads live in [`super::costs`], the
//! shape rescore in [`super::shape`].

use std::collections::HashMap;

use super::api::{
    is_high, is_low, Candidate, DecodeStats, Decoder, LearnedShapes, Point, Ranked, Source,
    MAX_WORD_LENGTH, RESULT_K,
};
use super::keymap::KeyMap;
use super::loops::{is_joiner, is_non_word};
use super::workspace::{NO_LABEL, SAMPLE_POINTS, UNREACHABLE};
use crate::fuzzy::Tier;
use crate::kernels::band;
use crate::sort;
use crate::strict_math;

const MIN_WORD_LENGTH: i32 = 2;
const MIN_LOOKAHEAD_PREFIX: i32 = 3;
/// Most joins in one reading: three parts, `bundes`-`verfassungs`-`gericht`
/// sized, and no further.
const MAX_JOINS: i32 = 2;
const EPS: f64 = 1e-9;

fn ln1p(v: i32) -> f64 {
    strict_math::ln1p_count(v)
}

/// The frequency a compound's language-model term is read at: the least
/// of its finished parts' (`cap`, `workspace::NO_PART` for none) and `f`, the current
/// part's or its subtree's. `f` itself for a plain word, so the plain
/// decode's arithmetic is untouched.
fn lm_cap(cap: i32, f: i32) -> i32 {
    if f < cap {
        f
    } else {
        cap
    }
}

pub(super) fn by_score(a: &Candidate, b: &Candidate) -> std::cmp::Ordering {
    b.score
        .total_cmp(&a.score)
        .then_with(|| a.word.cmp(&b.word))
}

impl Decoder {
    /// `decode`, all of it: when the caller has its learned shapes at hand.
    #[allow(clippy::too_many_arguments)]
    pub fn decode(
        &mut self,
        path: &[Point],
        keys: &KeyMap,
        key_width: f32,
        sources: &[Source],
        limit: usize,
        shapes: Option<&LearnedShapes>,
        look_ahead: usize,
    ) -> Vec<Candidate> {
        match self.decode_ranked(path, keys, key_width, sources, limit, look_ahead) {
            None => Vec::new(),
            Some(ranked) => self.finish(ranked, keys, shapes, None),
        }
    }

    /// The walk, up to the shape channel: the ranked readings and guesses,
    /// or `None` when the stroke or the request is not a decode at all. The
    /// workspace keeps what [`Decoder::finish`] needs, so the two are called
    /// in turn on the same decoder.
    pub fn decode_ranked(
        &mut self,
        path: &[Point],
        keys: &KeyMap,
        key_width: f32,
        sources: &[Source],
        limit: usize,
        look_ahead: usize,
    ) -> Option<Ranked> {
        self.last_stats = DecodeStats::default();
        if path.len() < super::api::MIN_SAMPLES || key_width <= 0.0 {
            return None;
        }
        if keys.key_count() == 0 || sources.is_empty() || limit == 0 {
            return None;
        }
        if !self.resample(path, key_width) {
            return None;
        }
        self.ws.prepare_keys(keys.key_count());
        self.build_costs(keys);
        self.build_dwell(keys);
        if self.ws.arc_step <= 0.0 {
            return None;
        }
        self.build_loops(path, key_width, keys);
        self.build_remain(keys);
        self.ws.max_states = self.tuning.max_states.max(1);

        let k = (limit * 2).max(RESULT_K);
        let mut results: HashMap<Vec<u16>, Candidate> = HashMap::new();
        let mut ahead: Option<HashMap<Vec<u16>, Candidate>> =
            if look_ahead > 0 && !self.ends_on_loop() {
                Some(HashMap::new())
            } else {
                None
            };
        let mut budget = self.tuning.look_ahead_budget;
        let mut floor = f64::NEG_INFINITY;
        let mut ordered: Vec<&Source> = sources.iter().collect();
        let fw = self.tuning.freq_weight;
        let root_bound =
            |s: &Source| s.log_weight + fw * ln1p(s.walker.max_subtree(s.walker.root()));
        sort::by(&mut ordered, |a, b| root_bound(b).total_cmp(&root_bound(a)));
        for src in ordered {
            if root_bound(src) < floor - EPS {
                continue;
            }
            floor = self.search_one(
                src,
                keys,
                k,
                &mut results,
                floor,
                ahead.as_mut(),
                &mut budget,
            );
        }
        self.last_stats.read = results.len();
        let mut read: Vec<Candidate> = results.into_values().collect();
        sort::by(&mut read, by_score);
        let guesses = ahead.map(|a| a.into_values().collect()).unwrap_or_default();
        Some(Ranked {
            read,
            guesses,
            look_ahead,
            limit,
        })
    }

    /// The shape channel over a [`Ranked`] walk, the learned-shape seeding,
    /// and the guesses merged in. `seeds` are the words whose stored shapes
    /// sit near the drawn one, nearest first, when seeding is on: the store
    /// that finds them is the caller's, so the caller asks it (with
    /// [`Decoder::sample_shape`] of the same stroke) and passes the answer.
    pub fn finish(
        &mut self,
        ranked: Ranked,
        keys: &KeyMap,
        shapes: Option<&LearnedShapes>,
        seeds: Option<&[Vec<u16>]>,
    ) -> Vec<Candidate> {
        let Ranked {
            read,
            guesses,
            look_ahead,
            limit,
        } = ranked;
        let mut read = self.rescore_shape(read, keys, shapes);
        read.truncate(limit);
        if let Some(near) = seeds.filter(|n| !n.is_empty()) {
            let top = read.iter().map(|c| c.score).reduce(f64::max).unwrap_or(0.0);
            let had: std::collections::HashSet<Vec<u16>> =
                read.iter().map(|c| c.word.clone()).collect();
            for c in read.iter_mut() {
                if near.contains(&c.word) {
                    c.score = c.score.max(top);
                }
            }
            for word in near {
                if !had.contains(word) {
                    read.push(Candidate {
                        word: word.clone(),
                        score: top,
                        shape_cost: 0.0,
                        tier: Tier::Dictionary,
                        ahead: 0,
                    });
                }
            }
            sort::by(&mut read, by_score);
            read.truncate(limit);
        }
        if guesses.is_empty() {
            return read;
        }
        let read_words: std::collections::HashSet<&Vec<u16>> =
            read.iter().map(|c| &c.word).collect();
        let guesses: Vec<Candidate> = guesses
            .into_iter()
            .filter(|g| !read_words.contains(&g.word))
            .collect();
        let mut completions = self.rescore_shape(guesses, keys, shapes);
        completions.truncate(look_ahead);
        let mut all = read;
        all.extend(completions);
        sort::by(&mut all, by_score);
        all
    }

    // ---- the walk ----

    #[allow(clippy::too_many_arguments)]
    fn search_one(
        &mut self,
        src: &Source,
        keys: &KeyMap,
        k: usize,
        results: &mut HashMap<Vec<u16>, Candidate>,
        floor_in: f64,
        mut ahead: Option<&mut HashMap<Vec<u16>, Candidate>>,
        budget: &mut i32,
    ) -> f64 {
        let mut floor = floor_in;
        let walker = src.walker;
        let n = self.ws.samples;
        let key_count = keys.key_count();
        let min_frequency = src.min_frequency;
        let tuning = self.tuning.clone();
        let join_on = tuning.join_cost.is_finite();

        self.ws.reset();
        let root = walker.root();
        self.ws.push(
            root,
            -1,
            NO_LABEL,
            -1,
            0,
            0.0,
            0.0,
            src.log_weight + tuning.freq_weight * ln1p(walker.max_subtree(root)),
            0,
        );

        let mut pops = 0;
        let max_pops = tuning.max_pops.max(1);
        let mut children = std::mem::take(&mut self.ws.children);
        while self.ws.heap_size() > 0 && pops < max_pops {
            let s = self.ws.pop_best();
            if self.ws.bound[s] < floor - EPS {
                break;
            }
            pops += 1;

            let node = self.ws.node[s];
            let length = self.ws.length[s];
            let extra = self.ws.extra[s];
            let last_key = self.ws.last_key[s];

            let part_freq = self.ws.part_freq[s];
            let part_from = self.ws.part_from[s];
            let joins = self.ws.joins[s];
            // The join charge plus the common-part penalties this state
            // already earned; both 0.0 for a plain word.
            let charge = tuning.join_charge(joins) + self.ws.join_penalty[s];

            let total = self.terminal_cost(self.ws.column_of(s));
            let at_end = last_key >= 0 && self.ws.end_key[last_key as usize] && total < UNREACHABLE;
            if at_end {
                let shape = total + extra + self.unclaimed_dwell(s, keys) + self.unclaimed_loop(s);
                // A compound's last part is held to the same length as its
                // first; `part_from` is 0 and `charge` 0.0 for a plain word.
                if length >= MIN_WORD_LENGTH
                    && length - part_from >= if joins > 0 { tuning.join_min_part } else { 0 }
                    && walker.is_word(node)
                    && walker.frequency(node) >= min_frequency
                {
                    let score = src.log_weight
                        + tuning.freq_weight * ln1p(lm_cap(part_freq, walker.frequency(node)))
                        - tuning.shape_weight * shape as f64
                        - charge;
                    if score > floor - EPS || results.len() < k {
                        let word = self.ws.materialize(s);
                        if !(src.tier == Tier::Dictionary && is_non_word(&word)) {
                            emit(word, score, shape as f64, src.tier, results);
                            if results.len() >= k {
                                floor = kth_best(results, k, &mut self.ws.score_scratch);
                            }
                        }
                    }
                }
                if let Some(ahead) = ahead.as_deref_mut() {
                    if *budget > 0 && length - part_from >= MIN_LOOKAHEAD_PREFIX {
                        self.look_ahead(src, node, s, shape, min_frequency, ahead, budget);
                    }
                }
            }
            if length >= MAX_WORD_LENGTH || length as usize >= n {
                continue;
            }

            // A compound (#966 §5.2): a finished part of three letters or
            // more may hand the rest of the stroke to a second word, read
            // from the trie root on the same alignment column, as if the
            // list held the joined spelling. The joined word scores on the
            // rarest of its parts, `join_cost` the poorer per join, and
            // the bound carries both, so a join never ranks above what the
            // single-word bound allows and the walk's pruning stays exact.
            // The part joined past pays `join_part_penalty` on its own
            // frequency, so two common parts do not outbid a listed word;
            // the last part is followed by no join and pays nothing.
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
                let bound = src.log_weight
                    + tuning.freq_weight * ln1p(lm_cap(cap, walker.max_subtree(root)))
                    - tuning.shape_weight * (floor_cost + extra) as f64
                    - tuning.join_charge(joins + 1)
                    - self.ws.join_penalty[s]
                    - part_penalty;
                if bound >= floor - EPS {
                    if let Some(id) = self.ws.push(
                        root,
                        s as i32,
                        NO_LABEL,
                        last_key,
                        length,
                        extra,
                        floor_cost,
                        bound,
                        self.ws.letter_cp[s],
                    ) {
                        self.ws.part_freq[id] = cap;
                        self.ws.part_from[id] = length;
                        self.ws.joins[id] = joins + 1;
                        self.ws.join_penalty[id] = self.ws.join_penalty[s] + part_penalty;
                        self.ws.copy_column(s, id);
                    }
                }
            }

            walker.children_into(node, &mut children);
            let via = self.ws.via_label[s];
            let pending_high = if is_high(via) { Some(via) } else { None };
            for &(label, child) in children.iter() {
                let subtree = walker.max_subtree(child);
                if subtree < min_frequency {
                    continue;
                }
                let code_point: i32;
                if let Some(high) = pending_high {
                    if !is_low(label) {
                        continue;
                    }
                    code_point =
                        0x10000 + (((high as i32) - 0xD800) << 10) + ((label as i32) - 0xDC00);
                } else if is_high(label) {
                    if !self.descend_silent(src, subtree, s, child, label, extra, floor) {
                        break;
                    }
                    continue;
                } else {
                    code_point = label as i32;
                }

                let key = keys.key_index(code_point);
                if key < 0
                    && length > 0
                    && is_joiner(code_point)
                    && !is_joiner(self.ws.via_label[s] as i32)
                {
                    let cost = extra + tuning.joiner_cost;
                    if !self.descend_silent(src, subtree, s, child, label, cost, floor) {
                        break;
                    }
                    continue;
                }
                if key < 0 || key as usize >= key_count || !self.ws.near_key[key as usize] {
                    continue;
                }
                if length == 0 && !self.ws.start_key[key as usize] {
                    continue;
                }
                let repeat = length > 0 && code_point == self.ws.letter_cp[s];

                let min_col: f32;
                let mut child_extra = extra;
                if repeat {
                    min_col = self.ws.floor_cost[s];
                    child_extra += self.repeat_charge(last_key as usize);
                } else {
                    let prev_column = if length == 0 {
                        None
                    } else {
                        Some(self.ws.column_of(s))
                    };
                    min_col = self.advance(prev_column, key as usize, last_key, keys);
                    if min_col >= UNREACHABLE {
                        continue;
                    }
                }

                let bound = src.log_weight + tuning.freq_weight * ln1p(lm_cap(part_freq, subtree))
                    - tuning.shape_weight * (min_col + child_extra) as f64
                    - charge;
                if bound < floor - EPS {
                    continue;
                }
                let Some(id) = self.ws.push(
                    child,
                    s as i32,
                    label,
                    key,
                    length + 1,
                    child_extra,
                    min_col,
                    bound,
                    code_point,
                ) else {
                    break;
                };
                if repeat {
                    self.ws.copy_column(s, id);
                } else {
                    self.ws.store_scratch(id);
                }
            }
        }
        self.ws.children = children;
        self.last_stats.pops += pops;
        self.last_stats.states += self.ws.node.len();
        self.last_stats.saturated |= self.ws.saturated;
        floor
    }

    #[allow(clippy::too_many_arguments)]
    fn descend_silent(
        &mut self,
        src: &Source,
        subtree: i32,
        s: usize,
        child: u32,
        label: u16,
        extra: f32,
        floor: f64,
    ) -> bool {
        let bound = src.log_weight
            + self.tuning.freq_weight * ln1p(lm_cap(self.ws.part_freq[s], subtree))
            - self.tuning.shape_weight * (self.ws.floor_cost[s] + extra) as f64
            - self.tuning.join_charge(self.ws.joins[s])
            - self.ws.join_penalty[s];
        if bound < floor - EPS {
            return true;
        }
        let (last_key, length, floor_cost, letter_cp) = (
            self.ws.last_key[s],
            self.ws.length[s],
            self.ws.floor_cost[s],
            self.ws.letter_cp[s],
        );
        let Some(id) = self.ws.push(
            child, s as i32, label, last_key, length, extra, floor_cost, bound, letter_cp,
        ) else {
            return false;
        };
        self.ws.copy_column(s, id);
        true
    }

    #[allow(clippy::too_many_arguments)]
    fn look_ahead(
        &mut self,
        src: &Source,
        node: u32,
        s: usize,
        shape: f32,
        min_frequency: i32,
        ahead: &mut HashMap<Vec<u16>, Candidate>,
        budget: &mut i32,
    ) {
        let walker = src.walker;
        let best = walker.max_subtree(node);
        if best < min_frequency || best <= walker.frequency(node) {
            return;
        }
        *budget -= 1;
        let prefix = self.ws.materialize(s);
        let mut word = prefix.clone();
        let mut at = node;
        let mut steps = 0;
        let mut children = std::mem::take(&mut self.ws.look_ahead_children);
        while steps < MAX_WORD_LENGTH {
            if walker.is_word(at) && walker.frequency(at) == best {
                break;
            }
            walker.children_into(at, &mut children);
            let next = children
                .iter()
                .find(|&&(_, c)| walker.max_subtree(c) == best)
                .copied();
            let Some((label, child)) = next else {
                self.ws.look_ahead_children = children;
                return;
            };
            word.push(label);
            at = child;
            steps += 1;
        }
        self.ws.look_ahead_children = children;
        if steps == 0 || word.len() <= prefix.len() {
            return;
        }
        if src.tier == Tier::Dictionary && is_non_word(&word) {
            return;
        }
        let extra = (word.len() - prefix.len()) as i32;
        let score = src.log_weight
            + self.tuning.freq_weight * ln1p(lm_cap(self.ws.part_freq[s], best))
            - self.tuning.shape_weight * shape as f64
            - self.tuning.look_ahead_cost * extra as f64
            - self.tuning.join_charge(self.ws.joins[s])
            - self.ws.join_penalty[s];
        let replace = match ahead.get(&word) {
            None => true,
            Some(existing) => score > existing.score,
        };
        if replace {
            ahead.insert(
                word.clone(),
                Candidate {
                    word,
                    score,
                    shape_cost: shape as f64,
                    tier: src.tier,
                    ahead: extra,
                },
            );
        }
    }

    fn advance(
        &mut self,
        prev_column: Option<usize>,
        key: usize,
        prev_key: i32,
        keys: &KeyMap,
    ) -> f32 {
        let n = self.ws.samples;
        let key_count = keys.key_count();
        let Some(prev_column) = prev_column else {
            // The first letter stands on the first sample, or on any sample
            // of an open head (#968): the walk up from the spacebar before
            // it is nobody's letter.
            let head_to = self.ws.open_head_to;
            let mut best = UNREACHABLE;
            for j in 0..n {
                if j <= head_to {
                    let at = self.ws.point_cost[j * key_count + key];
                    self.ws.scratch[j] = at;
                    let remain = self.ws.remain[j * key_count + key];
                    if remain < UNREACHABLE && at + remain < best {
                        best = at + remain;
                    }
                } else {
                    self.ws.scratch[j] = UNREACHABLE;
                }
            }
            return best;
        };
        let step = self.ws.arc_step;
        let span = keys.distance(prev_key as usize, key);
        let expected = span / step;
        let lo = 1.max((expected - self.tuning.gap_window) as i32);
        let hi = lo.max((expected + self.tuning.gap_window) as i32 + 1) + self.ws.collapsed_samples;
        let lead = self.anchor_lead(0, prev_key, self.tuning.start_slack(), keys);
        let tail = self.anchor_lead(n - 1, key as i32, self.tuning.end_slack(), keys);

        self.ws.scratch[0] = UNREACHABLE;
        let mut best = UNREACHABLE;
        for j in 1..n {
            // The stroke's two ends are open past the band (#886): the first
            // letter may stand any distance before the next and the last any
            // distance after the one before, the extra travel paying the gap
            // charge. A loop the scan missed, or collapsed only in part, used
            // to put `ill`'s second key out of reach of its first entirely.
            let from = if j == n - 1 { 0 } else { 0.max(j as i32 - hi) };
            let to = j as i32 - lo;
            let arc_j = self.ws.arc_at[j];
            let ease_j = if j == n - 1 { tail } else { 0.0 };
            let mut best_prev = UNREACHABLE;
            let mut i = from;
            // Sample 0 eases by the lead too; the rest of the band is one
            // kernel call (kernels::band, the same arithmetic four at a time).
            if 0 <= to {
                let at = self.ws.cols[prev_column];
                if at < UNREACHABLE {
                    let travelled = arc_j - self.ws.arc_at[0];
                    let gap = travelled - span;
                    let v = at + self.gap_charge(gap, lead + ease_j);
                    if v < best_prev {
                        best_prev = v;
                    }
                }
                i = i.max(1);
            }
            if i <= to {
                let (a, b) = (i as usize, to as usize + 1);
                let v = band::min_arc(
                    &self.ws.cols[prev_column + a..prev_column + b],
                    &self.ws.arc_at[a..b],
                    arc_j,
                    span,
                    ease_j,
                    self.tuning.gap_weight,
                    UNREACHABLE,
                );
                if v < best_prev {
                    best_prev = v;
                }
            }
            let value = if best_prev >= UNREACHABLE {
                UNREACHABLE
            } else {
                best_prev + self.ws.point_cost[j * key_count + key]
            };
            self.ws.scratch[j] = value;
            let rest = self.ws.remain[j * key_count + key];
            if value < UNREACHABLE && rest < UNREACHABLE && value + rest < best {
                best = value + rest;
            }
        }
        best
    }

    fn build_remain(&mut self, keys: &KeyMap) {
        let n = self.ws.samples;
        let key_count = keys.key_count();
        let step = self.ws.arc_step;
        for k in 0..key_count {
            if self.ws.near_key[k] {
                let c = self.ws.near_count;
                self.ws.near_list[c] = k;
                self.ws.near_count += 1;
            }
        }
        let count = self.ws.near_count;
        let last = (n - 1) * key_count;
        for k in 0..key_count {
            self.ws.remain[last + k] = if self.ws.end_key[k] { 0.0 } else { UNREACHABLE };
        }
        // An open tail (#968) ends on any of its samples at no further cost.
        let tail_from = self.ws.open_tail_from.min(n - 1);
        for j in tail_from..n - 1 {
            for k in 0..key_count {
                self.ws.remain[j * key_count + k] = 0.0;
            }
        }
        // The near keys' costs and remainders again, key by key in sample
        // order, for the band kernel to read in runs.
        for x in 0..count {
            let k = self.ws.near_list[x];
            for j in 0..n {
                self.ws.point_cost_t[k * SAMPLE_POINTS + j] = self.ws.point_cost[j * key_count + k];
            }
            for j in tail_from..n {
                self.ws.remain_t[k * SAMPLE_POINTS + j] = self.ws.remain[j * key_count + k];
            }
        }
        let (start_slack, end_slack) = (self.tuning.start_slack(), self.tuning.end_slack());
        for j in (0..tail_from).rev() {
            let base = j * key_count;
            let arc_j = self.ws.arc_at[j];
            for a in 0..key_count {
                self.ws.remain[base + a] = UNREACHABLE;
            }
            for x in 0..count {
                let from = self.ws.near_list[x];
                let lead = if j == 0 {
                    self.anchor_lead(0, from as i32, start_slack, keys)
                } else {
                    0.0
                };
                let mut best = UNREACHABLE;
                for y in 0..count {
                    let to = self.ws.near_list[y];
                    let span = keys.distance(from, to);
                    let expected = span / step;
                    let lo = 1.max((expected - self.tuning.gap_window) as i32);
                    let hi = lo.max((expected + self.tuning.gap_window) as i32 + 1)
                        + self.ws.collapsed_samples;
                    // Open to the last sample from anywhere, and from the
                    // first to anywhere, as in `advance`.
                    let end = if j == 0 {
                        n as i32 - 1
                    } else {
                        (n as i32 - 1).min(j as i32 + hi)
                    };
                    let start = j as i32 + lo;
                    // The band up to the last sample is one kernel call over
                    // `to`'s costs and remainders in sample order; the last
                    // sample eases by the end anchor too.
                    let last = if end == n as i32 - 1 { end - 1 } else { end };
                    if start <= last {
                        let (a, b) = (start as usize, last as usize + 1);
                        let row = to * SAMPLE_POINTS;
                        let v = band::min_ahead(
                            &self.ws.point_cost_t[row + a..row + b],
                            &self.ws.remain_t[row + a..row + b],
                            &self.ws.arc_at[a..b],
                            arc_j,
                            span,
                            lead,
                            self.tuning.gap_weight,
                            UNREACHABLE,
                        );
                        if v < best {
                            best = v;
                        }
                    }
                    if start <= n as i32 - 1 {
                        let iu = n - 1;
                        let rest = self.ws.remain[iu * key_count + to];
                        if rest < UNREACHABLE {
                            let gap = self.ws.arc_at[iu] - arc_j - span;
                            let ease = lead + self.anchor_lead(n - 1, to as i32, end_slack, keys);
                            let v = self.gap_charge(gap, ease)
                                + self.ws.point_cost[iu * key_count + to]
                                + rest;
                            if v < best {
                                best = v;
                            }
                        }
                    }
                }
                self.ws.remain[base + from] = best;
                self.ws.remain_t[from * SAMPLE_POINTS + j] = best;
            }
        }
    }

    /// The cost of a finished word on the column `col`: the last sample's,
    /// or the least over an open tail (#968).
    fn terminal_cost(&self, col: usize) -> f32 {
        let n = self.ws.samples;
        let mut best = self.ws.cols[col + n - 1];
        for j in self.ws.open_tail_from..n - 1 {
            let v = self.ws.cols[col + j];
            if v < best {
                best = v;
            }
        }
        best
    }
}

fn emit(
    word: Vec<u16>,
    score: f64,
    shape_cost: f64,
    tier: Tier,
    results: &mut HashMap<Vec<u16>, Candidate>,
) {
    let replace = match results.get(&word) {
        None => true,
        Some(existing) => score > existing.score,
    };
    if replace {
        results.insert(
            word.clone(),
            Candidate {
                word,
                score,
                shape_cost,
                tier,
                ahead: 0,
            },
        );
    }
}

fn kth_best(results: &HashMap<Vec<u16>, Candidate>, k: usize, scores: &mut Vec<f64>) -> f64 {
    let size = results.len();
    if size < k {
        return f64::NEG_INFINITY;
    }
    scores.clear();
    scores.extend(results.values().map(|c| c.score));
    scores.sort_by(f64::total_cmp);
    scores[size - k]
}
