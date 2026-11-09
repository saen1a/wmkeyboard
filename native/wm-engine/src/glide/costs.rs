//! The per-decode cost tables: key costs and anchors, dwells and pauses, and
//! the loop scan and its charges.

use super::api::{Decoder, Marks, Point, MIN_SAMPLES};
use super::geometry::anchor_mask;
use super::keymap::KeyMap;

const DWELL_RADIUS: f32 = 0.8;
const DWELL_TIE: f32 = 0.25;
const END_LOOP_REACH: f32 = 0.5;

impl Decoder {
    /// `marks`: the loops `decode` would read in the stroke, found exactly as
    /// it finds them, for a decoder that does not walk the stroke itself
    /// (`ctc`). `None` when `decode` would not read the stroke at all.
    pub fn marks(&mut self, path: &[Point], keys: &KeyMap, key_width: f32) -> Option<Marks> {
        if path.len() < MIN_SAMPLES || key_width <= 0.0 || keys.key_count() == 0 {
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
        let mut marks = Marks {
            ends_on_loop: self.ends_on_loop(),
            ..Marks::default()
        };
        for e in 0..self.ws.loop_count {
            if self.ws.loop_score[e] > 0.0 && self.ws.loop_key[e] >= 0 {
                marks
                    .loops
                    .push((self.ws.loop_key[e], self.ws.loop_score[e]));
            }
        }
        Some(marks)
    }

    pub(super) fn build_costs(&mut self, keys: &KeyMap) {
        let n = self.ws.samples;
        let key_count = keys.key_count();
        let inv = self.tuning.inv_two_sigma_sq();
        let max_point_cost = self.tuning.max_point_cost;
        let near_cost = self.tuning.near_cost();
        for i in 0..n {
            let base = i * key_count;
            let (px, py) = (self.ws.path_x[i], self.ws.path_y[i]);
            for k in 0..key_count {
                let dx = px - keys.key_x[k];
                let dy = py - keys.key_y[k];
                let scaled = (dx * dx + dy * dy) * inv;
                self.ws.point_cost[base + k] = if scaled > max_point_cost {
                    max_point_cost
                } else {
                    scaled
                };
                if scaled <= near_cost {
                    self.ws.near_key[k] = true;
                }
            }
        }
        let (x0, y0, xn, yn) = (
            self.ws.path_x[0],
            self.ws.path_y[0],
            self.ws.path_x[n - 1],
            self.ws.path_y[n - 1],
        );
        anchor_mask(
            x0,
            y0,
            keys,
            &mut self.ws.start_key,
            self.tuning.start_radius_sq(),
        );
        anchor_mask(
            xn,
            yn,
            keys,
            &mut self.ws.end_key,
            self.tuning.end_radius_sq(),
        );
        self.anchor_slack(0, self.tuning.start_slack(), true, keys);
        self.anchor_slack(n - 1, self.tuning.end_slack(), false, keys);
        // An open end (#968) is no anchor at all: the stroke's end sits at
        // the spacebar's edge, and any key the walk passed may begin or end
        // the word. The near set widens to every key the open zone passed.
        if self.ws.open_head_to > 0 {
            for k in 0..key_count {
                self.ws.start_key[k] = true;
            }
        }
        if self.ws.open_tail_from < n - 1 {
            for k in 0..key_count {
                self.ws.end_key[k] = true;
            }
        }
    }

    fn anchor_slack(&mut self, j: usize, slack: f32, start: bool, keys: &KeyMap) {
        if slack <= 0.0 {
            return;
        }
        let key_count = keys.key_count();
        let base = j * key_count;
        let inv = self.tuning.inv_two_sigma_sq();
        let max_point_cost = self.tuning.max_point_cost;
        for k in 0..key_count {
            let dx = self.ws.path_x[j] - keys.key_x[k];
            let dy = self.ws.path_y[j] - keys.key_y[k];
            let past = (dx * dx + dy * dy).sqrt() - slack;
            let scaled = if past > 0.0 { past * past * inv } else { 0.0 };
            self.ws.point_cost[base + k] = if scaled > max_point_cost {
                max_point_cost
            } else {
                scaled
            };
            let masked = if start {
                self.ws.start_key[k]
            } else {
                self.ws.end_key[k]
            };
            if masked {
                self.ws.near_key[k] = true;
            }
        }
    }

    pub(super) fn anchor_lead(&self, j: usize, key: i32, slack: f32, keys: &KeyMap) -> f32 {
        if slack <= 0.0 || key < 0 {
            return 0.0;
        }
        let dx = self.ws.path_x[j] - keys.key_x[key as usize];
        let dy = self.ws.path_y[j] - keys.key_y[key as usize];
        let d = (dx * dx + dy * dy).sqrt();
        if d < slack {
            d
        } else {
            slack
        }
    }

    pub(super) fn gap_charge(&self, gap: f32, ease: f32) -> f32 {
        let over = (if gap < 0.0 { -gap } else { gap }) - ease;
        if over > 0.0 {
            self.tuning.gap_weight * over
        } else {
            0.0
        }
    }

    pub(super) fn build_dwell(&mut self, keys: &KeyMap) {
        if self.tuning.unclaimed_dwell <= 0.0 {
            return;
        }
        let n = self.ws.samples;
        let span = (self.ws.path_t[n - 1] - self.ws.path_t[0]) as f32;
        if span <= 0.0 {
            return;
        }
        let even_step = span / (n - 1) as f32;
        let dwell_scale = self.tuning.dwell_scale();
        let mut run_end: i32 = -1;
        for j in 1..n {
            let step = (self.ws.path_t[j] - self.ws.path_t[j - 1]) as f32;
            let lingering = ((step / even_step) - 1.0) / dwell_scale;
            if lingering <= 0.0 {
                continue;
            }
            let score = if lingering > 1.0 { 1.0 } else { lingering };
            self.record_pause(j, score, run_end);
            run_end = j as i32;
        }
        for p in 0..self.ws.pause_count {
            let j = self.ws.pause_at[p];
            let (x, y) = (self.ws.path_x[j], self.ws.path_y[j]);
            self.place_pause(p, x, y, keys);
        }
    }

    fn place_pause(&mut self, p: usize, x: f32, y: f32, keys: &KeyMap) {
        let mut nearest_sq = f32::MAX;
        for k in 0..keys.key_count() {
            let dx = x - keys.key_x[k];
            let dy = y - keys.key_y[k];
            let d = dx * dx + dy * dy;
            if d < nearest_sq {
                nearest_sq = d;
            }
        }
        let reach = DWELL_RADIUS.min(nearest_sq.sqrt() + DWELL_TIE);
        self.ws.pause_x[p] = x;
        self.ws.pause_y[p] = y;
        self.ws.pause_reach_sq[p] = reach * reach;
    }

    fn record_pause(&mut self, j: usize, score: f32, run_end: i32) {
        let count = self.ws.pause_count;
        if count > 0 && run_end == j as i32 - 1 {
            if score > self.ws.pause_score[count - 1] {
                self.ws.pause_score[count - 1] = score;
                self.ws.pause_at[count - 1] = j;
            }
            return;
        }
        self.ws.pause_at[count] = j;
        self.ws.pause_score[count] = score;
        self.ws.pause_count = count + 1;
    }

    pub(super) fn unclaimed_dwell(&self, s: usize, keys: &KeyMap) -> f32 {
        let weight = self.tuning.unclaimed_dwell;
        if weight <= 0.0 || self.ws.pause_count == 0 {
            return 0.0;
        }
        let mut charge = 0f32;
        for p in 0..self.ws.pause_count {
            let (px, py, reach_sq) = (
                self.ws.pause_x[p],
                self.ws.pause_y[p],
                self.ws.pause_reach_sq[p],
            );
            let mut claimed = false;
            let mut cur = s as i32;
            while cur >= 0 && !claimed {
                let key = self.ws.last_key[cur as usize];
                if key >= 0 {
                    let dx = px - keys.key_x[key as usize];
                    let dy = py - keys.key_y[key as usize];
                    claimed = dx * dx + dy * dy <= reach_sq;
                }
                cur = self.ws.parent[cur as usize];
            }
            if !claimed {
                charge += self.ws.pause_score[p];
            }
        }
        weight * charge
    }

    // ---- loops ----

    pub(super) fn build_loops(&mut self, path: &[Point], key_width: f32, keys: &KeyMap) {
        self.ws.loop_count = 0;
        let found = self.scan.find(path, key_width, &self.tuning);
        for w in 0..found {
            let is_loop = self.scan.window_is_loop[w];
            let (from, to) = (self.scan.window_from[w], self.scan.window_to[w]);
            let e = self.record_loop(from, to, if is_loop { 1.0 } else { 0.0 }, keys);
            if !is_loop {
                self.record_wiggle(e, keys);
            }
        }
        if self.ws.loop_count > 0 {
            self.exclude_neighbours(keys);
            self.collapse_arc();
        }
    }

    pub(super) fn ends_on_loop(&self) -> bool {
        let last = self.ws.samples - 1;
        for e in (0..self.ws.loop_count).rev() {
            if self.ws.loop_score[e] <= 0.0 || self.ws.loop_key[e] < 0 {
                continue;
            }
            return self.ws.arc_at[last] - self.ws.arc_at[self.ws.loop_to[e]] <= END_LOOP_REACH;
        }
        false
    }

    fn record_wiggle(&mut self, e: usize, keys: &KeyMap) {
        let p = self.ws.pause_count;
        if self.tuning.unclaimed_dwell <= 0.0 || self.tuning.wiggle_weight <= 0.0 {
            return;
        }
        if p >= self.ws.samples {
            return;
        }
        self.ws.pause_at[p] = (self.ws.loop_from[e] + self.ws.loop_to[e]) / 2;
        self.ws.pause_score[p] = self.tuning.wiggle_weight;
        let (x, y) = (self.ws.loop_x[e], self.ws.loop_y[e]);
        self.place_pause(p, x, y, keys);
        self.ws.pause_count = p + 1;
    }

    fn exclude_neighbours(&mut self, keys: &KeyMap) {
        let charge = self.tuning.loop_exclusion;
        if charge <= 0.0 {
            return;
        }
        let key_count = keys.key_count();
        let cap = self.tuning.max_point_cost;
        for e in 0..self.ws.loop_count {
            let own = self.ws.loop_key[e];
            if own < 0 {
                continue;
            }
            for j in self.ws.loop_from[e] + 1..self.ws.loop_to[e] {
                let base = j * key_count;
                for k in 0..key_count {
                    if k as i32 != own {
                        let c = self.ws.point_cost[base + k] + charge;
                        self.ws.point_cost[base + k] = if cap < c { cap } else { c };
                    }
                }
            }
        }
    }

    fn record_loop(&mut self, from: usize, to: usize, score: f32, keys: &KeyMap) -> usize {
        self.scan.measure(from, to);
        let (cx, cy, length, chord) = (
            self.scan.centre_x,
            self.scan.centre_y,
            self.scan.length,
            self.scan.chord,
        );
        let last = self.ws.samples - 1;
        let to_sample = self.scan.fine_step / self.ws.arc_step;
        let mut a = last.min((from as f32 * to_sample + 0.5) as i32 as usize);
        let mut b = last.min((to as f32 * to_sample + 0.5) as i32 as usize);
        if b <= a {
            if a < last {
                b = a + 1;
            } else {
                a = b - 1;
            }
        }
        let e = self.ws.loop_count;
        self.ws.loop_from[e] = a;
        self.ws.loop_to[e] = b;
        self.ws.loop_shrink[e] = if length > 0.0 { chord / length } else { 1.0 };
        self.ws.loop_x[e] = cx;
        self.ws.loop_y[e] = cy;
        self.ws.loop_score[e] = score;
        self.ws.loop_count = e + 1;
        let own = self
            .scan
            .nearest_key(cx, cy, keys, self.tuning.loop_radius_sq());
        self.ws.loop_key[e] = own;
        if own >= 0 && score > self.ws.key_loop[own as usize] {
            self.ws.key_loop[own as usize] = score;
        }
        e
    }

    fn collapse_arc(&mut self) {
        let n = self.ws.samples;
        let step = self.ws.arc_step;
        let mut removed = 0f32;
        let mut e = 0;
        self.ws.arc_at[0] = 0.0;
        for j in 1..n {
            if e < self.ws.loop_count && j > self.ws.loop_from[e] && j <= self.ws.loop_to[e] {
                let a = self.ws.loop_from[e];
                let shrink = self.ws.loop_shrink[e];
                self.ws.arc_at[j] = self.ws.arc_at[a] + (j - a) as f32 * step * shrink;
                if j == self.ws.loop_to[e] {
                    removed += (j - a) as f32 * step * (1.0 - shrink);
                    e += 1;
                }
            } else {
                self.ws.arc_at[j] = self.ws.arc_at[j - 1] + step;
            }
        }
        self.ws.collapsed_samples = (removed / step).ceil() as i32;
    }

    pub(super) fn repeat_charge(&self, key: usize) -> f32 {
        (self.tuning.repeat_cost + self.tuning.unlooped_repeat) * (1.0 - self.ws.key_loop[key])
    }

    pub(super) fn unclaimed_loop(&self, s: usize) -> f32 {
        let weight = self.tuning.unclaimed_loop;
        if weight <= 0.0 || self.ws.loop_count == 0 {
            return 0.0;
        }
        let mut charge = 0f32;
        for e in 0..self.ws.loop_count {
            let own = self.ws.loop_key[e];
            if self.ws.loop_score[e] <= 0.0 || own < 0 {
                continue;
            }
            let mut claimed = false;
            let mut cur = s as i32;
            while cur >= 0 && !claimed {
                let parent = self.ws.parent[cur as usize];
                let c = cur as usize;
                if parent >= 0
                    && self.ws.letter_cp[c] == self.ws.letter_cp[parent as usize]
                    && self.ws.length[c] == self.ws.length[parent as usize] + 1
                {
                    claimed = self.ws.last_key[c] == own;
                }
                cur = parent;
            }
            if !claimed {
                charge += self.ws.loop_score[e];
            }
        }
        weight * charge
    }
}
