//! The shape channel: the drawn stroke, the textbook path through a word's
//! keys, and the learned shapes the user has drawn before.

use super::api::{
    code_points, Alignment, Candidate, Decoder, LearnedShapes, Point, MIN_SAMPLES, SHAPE_QUANT,
};
use super::geometry::{normalise_in_place, quantise, resample_polyline};
use super::keymap::KeyMap;
use super::loops::is_joiner;
use super::search::by_score;
use super::workspace::{MAX_IDEAL_POINTS, SAMPLE_POINTS, SHAPE_POINTS, UNREACHABLE};
use crate::sort;

impl Decoder {
    /// `sampleShape`: the stroke as the shape store keeps one.
    pub fn sample_shape(&mut self, path: &[Point], key_width: f32) -> Option<Vec<i8>> {
        if path.len() < MIN_SAMPLES || key_width <= 0.0 {
            return None;
        }
        if !self.resample(path, key_width) {
            return None;
        }
        self.drawn_shape();
        let mut out = vec![0i8; 2 * SHAPE_POINTS];
        quantise(&self.ws.drawn_shape_x, &self.ws.drawn_shape_y, &mut out);
        Some(out)
    }

    /// The drawn stroke quantised, after a decode, for the learned-shape
    /// seeding the caller does.
    pub fn drawn_shape8(&mut self) -> Vec<i8> {
        self.drawn_shape();
        let mut out = vec![0i8; 2 * SHAPE_POINTS];
        quantise(&self.ws.drawn_shape_x, &self.ws.drawn_shape_y, &mut out);
        out
    }

    /// The stroke resampled as the shape channel reads it, ready for
    /// [`Decoder::learned_gain`]; false when it is too short to have a shape.
    pub fn prepare_shape(&mut self, path: &[Point], key_width: f32) -> bool {
        if path.len() < MIN_SAMPLES || key_width <= 0.0 || !self.resample(path, key_width) {
            return false;
        }
        self.drawn_shape();
        normalise_in_place(&mut self.ws.drawn_shape_x, &mut self.ws.drawn_shape_y);
        self.plain_shape(false);
        true
    }

    /// How much nearer the stroke [`Decoder::prepare_shape`] took sits to
    /// `word` as the user has drawn it before than to the textbook path
    /// through its keys: the shape channel's own learned-shape benefit, in
    /// its normalised distance units, 0 for a word with no stored shapes and
    /// never more than `learned_shape_gain`.
    pub fn learned_gain(&mut self, word: &[u16], keys: &KeyMap, shapes: &LearnedShapes) -> f64 {
        if self.tuning.learned_shape_gain <= 0.0 || shapes.get(word).is_none_or(|s| s.is_empty()) {
            return 0.0;
        }
        let Some(ideal) = self.shape_distance(word, keys) else {
            return 0.0;
        };
        ideal - self.learned_distance(word, ideal, Some(shapes))
    }

    /// `align`: where `word`'s keys landed along the stroke.
    pub fn align(
        &mut self,
        word: &[u16],
        path: &[Point],
        keys: &KeyMap,
        key_width: f32,
    ) -> Option<Alignment> {
        if path.len() < MIN_SAMPLES || key_width <= 0.0 || keys.key_count() == 0 {
            return None;
        }
        let mut visits: Vec<usize> = Vec::new();
        let mut starts: Vec<i32> = Vec::new();
        let mut previous = -1;
        for (cp, start) in code_points(word) {
            let key = keys.key_index(cp);
            if key < 0 {
                if is_joiner(cp) {
                    continue;
                }
                return None;
            }
            if key == previous {
                continue;
            }
            if visits.len() >= MAX_IDEAL_POINTS {
                return None;
            }
            visits.push(key as usize);
            starts.push(start as i32);
            previous = key;
        }
        let count = visits.len();
        if count < 2 {
            return None;
        }
        if !self.resample(path, key_width) {
            return None;
        }
        if self.ws.arc_step <= 0.0 {
            return None;
        }
        self.ws.prepare_keys(keys.key_count());
        self.build_costs(keys);
        self.build_loops(path, key_width, keys);

        let n = self.ws.samples;
        let key_count = keys.key_count();
        let step = self.ws.arc_step;
        let mut back = vec![0i32; count * n];
        let mut prev = vec![0f32; n];
        let mut cur = vec![0f32; n];
        prev[0] = self.ws.point_cost[visits[0]];
        for v in prev.iter_mut().skip(1) {
            *v = UNREACHABLE;
        }
        for m in 1..count {
            let key = visits[m];
            let span = keys.distance(visits[m - 1], key);
            let expected = span / step;
            let lo = 1.max((expected - self.tuning.gap_window) as i32);
            let hi =
                lo.max((expected + self.tuning.gap_window) as i32 + 1) + self.ws.collapsed_samples;
            let lead = self.anchor_lead(0, visits[m - 1] as i32, self.tuning.start_slack(), keys);
            let tail = self.anchor_lead(n - 1, key as i32, self.tuning.end_slack(), keys);
            cur[0] = UNREACHABLE;
            for j in 1..n {
                let mut best = UNREACHABLE;
                let mut from: i32 = -1;
                let arc_j = self.ws.arc_at[j];
                let ease_j = if j == n - 1 { tail } else { 0.0 };
                let mut i = 0.max(j as i32 - hi);
                let to = j as i32 - lo;
                while i <= to {
                    let before = prev[i as usize];
                    if before < UNREACHABLE {
                        let gap = arc_j - self.ws.arc_at[i as usize] - span;
                        let v = before
                            + self.gap_charge(gap, if i == 0 { lead + ease_j } else { ease_j });
                        if v < best {
                            best = v;
                            from = i;
                        }
                    }
                    i += 1;
                }
                cur[j] = if from < 0 {
                    UNREACHABLE
                } else {
                    best + self.ws.point_cost[j * key_count + key]
                };
                back[m * n + j] = from;
            }
            std::mem::swap(&mut prev, &mut cur);
        }
        if prev[n - 1] >= UNREACHABLE {
            return None;
        }
        let mut x = vec![0f32; count];
        let mut y = vec![0f32; count];
        let mut samples = vec![0i32; count];
        let mut j = n - 1;
        for m in (0..count).rev() {
            x[m] = self.ws.path_x[j];
            y[m] = self.ws.path_y[j];
            samples[m] = j as i32;
            if m > 0 {
                j = back[m * n + j] as usize;
            }
        }
        Some(Alignment {
            keys: visits.iter().map(|&k| k as i32).collect(),
            x,
            y,
            samples,
            chars: starts,
            sample_count: n as i32,
        })
    }

    // ---- shape channel ----

    pub(super) fn rescore_shape(
        &mut self,
        ranked: Vec<Candidate>,
        keys: &KeyMap,
        shapes: Option<&LearnedShapes>,
    ) -> Vec<Candidate> {
        let weight = self.tuning.shape_channel;
        // A stroke with an open end carries a walk to or from the spacebar
        // that no word's ideal path has (#968): the drawn shape and the
        // ideal cannot be compared, so the walk's ranking stands.
        if weight <= 0.0 || ranked.is_empty() || self.ws.open_ends {
            return ranked;
        }
        self.drawn_shape();
        normalise_in_place(&mut self.ws.drawn_shape_x, &mut self.ws.drawn_shape_y);
        self.plain_shape(true);
        let learned = shapes.filter(|_| self.tuning.learned_shape_gain > 0.0);
        let mut rescored = Vec::with_capacity(ranked.len());
        for candidate in ranked {
            let distance = if candidate.ahead > 0 {
                let keep = candidate
                    .word
                    .len()
                    .saturating_sub(candidate.ahead as usize);
                self.shape_distance(&candidate.word[..keep], keys)
            } else {
                self.shape_distance(&candidate.word, keys)
                    .map(|ideal| self.learned_distance(&candidate.word, ideal, learned))
            };
            rescored.push(match distance {
                None => candidate,
                Some(d) => Candidate {
                    score: candidate.score - weight * d,
                    ..candidate
                },
            });
        }
        sort::by(&mut rescored, by_score);
        rescored
    }

    fn shape_distance(&mut self, word: &[u16], keys: &KeyMap) -> Option<f64> {
        let mut count = 0usize;
        let mut previous = -1;
        for (cp, _) in code_points(word) {
            let key = keys.key_index(cp);
            if key < 0 {
                if is_joiner(cp) {
                    continue;
                }
                return None;
            }
            if key == previous {
                continue;
            }
            if count >= MAX_IDEAL_POINTS {
                return None;
            }
            self.ws.ideal_x[count] = keys.key_x[key as usize];
            self.ws.ideal_y[count] = keys.key_y[key as usize];
            count += 1;
            previous = key;
        }
        if count < 2 {
            return None;
        }
        let count = self.with_anchor_leads(count);
        let (ix, iy) = (self.ws.ideal_x, self.ws.ideal_y);
        resample_polyline(
            &ix,
            &iy,
            count,
            &mut self.ws.ideal_shape_x,
            &mut self.ws.ideal_shape_y,
        );
        normalise_in_place(&mut self.ws.ideal_shape_x, &mut self.ws.ideal_shape_y);
        let mut sum = 0f64;
        for j in 0..SHAPE_POINTS {
            let dx = self.ws.plain_shape_x[j] - self.ws.ideal_shape_x[j];
            let dy = self.ws.plain_shape_y[j] - self.ws.ideal_shape_y[j];
            sum += (dx * dx + dy * dy).sqrt() as f64;
        }
        Some(sum / SHAPE_POINTS as f64)
    }

    fn with_anchor_leads(&mut self, count: usize) -> usize {
        let mut size = count;
        let start = self.tuning.start_slack();
        if start > 0.0 && size < MAX_IDEAL_POINTS {
            for p in (1..=size).rev() {
                self.ws.ideal_x[p] = self.ws.ideal_x[p - 1];
                self.ws.ideal_y[p] = self.ws.ideal_y[p - 1];
            }
            size += 1;
            let (x, y) = (self.ws.path_x[0], self.ws.path_y[0]);
            self.reach_toward(1, 0, x, y, start);
        }
        let end = self.tuning.end_slack();
        if end > 0.0 && size < MAX_IDEAL_POINTS {
            let last = self.ws.samples - 1;
            let (x, y) = (self.ws.path_x[last], self.ws.path_y[last]);
            self.reach_toward(size - 1, size, x, y, end);
            size += 1;
        }
        size
    }

    fn reach_toward(&mut self, from: usize, into: usize, x: f32, y: f32, reach: f32) {
        let (fx, fy) = (self.ws.ideal_x[from], self.ws.ideal_y[from]);
        let dx = x - fx;
        let dy = y - fy;
        let d = (dx * dx + dy * dy).sqrt();
        let t = if d <= reach { 1.0 } else { reach / d };
        self.ws.ideal_x[into] = fx + dx * t;
        self.ws.ideal_y[into] = fy + dy * t;
    }

    fn learned_distance(
        &mut self,
        word: &[u16],
        ideal: f64,
        shapes: Option<&LearnedShapes>,
    ) -> f64 {
        let Some(shapes) = shapes else { return ideal };
        let Some(stored) = shapes.get(word).filter(|s| !s.is_empty()) else {
            return ideal;
        };
        let n = SHAPE_POINTS;
        let mut own = f64::MAX;
        for shape in stored {
            for j in 0..n {
                self.ws.learned_shape_x[j] = shape[2 * j] as f32 / SHAPE_QUANT;
                self.ws.learned_shape_y[j] = shape[2 * j + 1] as f32 / SHAPE_QUANT;
            }
            normalise_in_place(&mut self.ws.learned_shape_x, &mut self.ws.learned_shape_y);
            let mut sum = 0f64;
            for j in 0..n {
                let dx = self.ws.drawn_shape_x[j] - self.ws.learned_shape_x[j];
                let dy = self.ws.drawn_shape_y[j] - self.ws.learned_shape_y[j];
                sum += (dx * dx + dy * dy).sqrt() as f64;
            }
            own = java_min(own, sum / n as f64);
        }
        java_max(java_min(ideal, own), ideal - self.tuning.learned_shape_gain)
    }

    fn drawn_shape(&mut self) {
        if self.ws.samples == SHAPE_POINTS {
            self.ws
                .drawn_shape_x
                .copy_from_slice(&self.ws.path_x[..SHAPE_POINTS]);
            self.ws
                .drawn_shape_y
                .copy_from_slice(&self.ws.path_y[..SHAPE_POINTS]);
        } else {
            let (px, py) = (self.ws.path_x, self.ws.path_y);
            resample_polyline(
                &px,
                &py,
                self.ws.samples,
                &mut self.ws.drawn_shape_x,
                &mut self.ws.drawn_shape_y,
            );
        }
    }
}

impl Decoder {
    /// `plainShape`: the normalised drawn shape into `plain_shape_*`, with the
    /// stroke's doubling loops cut to their chords when `loops` says this
    /// stroke's loops have been built. Only the ideal paths are compared
    /// against it: no word's ideal path has a loop in it, so a circle left in
    /// the shape matched the words that zigzag where it was drawn better than
    /// the word it doubled, and "need" lost to "needed", "bee" to "bede"
    /// (#886). The learned shapes keep the raw stroke they were stored from.
    fn plain_shape(&mut self, loops: bool) {
        if loops && self.shape_without_loops() {
            normalise_in_place(&mut self.ws.plain_shape_x, &mut self.ws.plain_shape_y);
        } else {
            self.ws.plain_shape_x = self.ws.drawn_shape_x;
            self.ws.plain_shape_y = self.ws.drawn_shape_y;
        }
    }

    /// The stroke resampled into the plain shape with every doubling loop's
    /// inside left out, as [`Decoder::collapse_arc`] collapses the arc; false,
    /// with nothing written, when the stroke has none.
    fn shape_without_loops(&mut self) -> bool {
        let n = self.ws.samples;
        let mut cut = false;
        let mut xs = [0f32; SAMPLE_POINTS];
        let mut ys = [0f32; SAMPLE_POINTS];
        let mut count = 0usize;
        let mut e = 0usize;
        for j in 0..n {
            while e < self.ws.loop_count && j >= self.ws.loop_to[e] {
                e += 1;
            }
            let inside = e < self.ws.loop_count
                && self.ws.loop_score[e] > 0.0
                && self.ws.loop_key[e] >= 0
                && j > self.ws.loop_from[e]
                && j < self.ws.loop_to[e];
            if inside {
                cut = true;
                continue;
            }
            xs[count] = self.ws.path_x[j];
            ys[count] = self.ws.path_y[j];
            count += 1;
        }
        if !cut || count < 2 {
            return false;
        }
        resample_polyline(
            &xs,
            &ys,
            count,
            &mut self.ws.plain_shape_x,
            &mut self.ws.plain_shape_y,
        );
        true
    }
}

fn java_min(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a == b {
        if a.is_sign_negative() {
            a
        } else {
            b
        }
    } else if a < b {
        a
    } else {
        b
    }
}

fn java_max(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a == b {
        if a.is_sign_negative() {
            b
        } else {
            a
        }
    } else if a > b {
        a
    } else {
        b
    }
}
