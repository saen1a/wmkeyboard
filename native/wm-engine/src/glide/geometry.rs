//! Pure geometry: stroke resampling, the open ends of a chained stroke, and
//! the shape helpers that only move points.

use super::api::{Decoder, Point, SHAPE_QUANT};
use super::keymap::KeyMap;
use super::workspace::{self, SHAPE_POINTS};

const MIN_STROKE_LENGTH: f32 = 0.5;
const SHAPE_BYTE_LIMIT: i32 = 127;
const MIN_SHAPE_SPREAD: f32 = 1e-4;

impl Decoder {
    pub(super) fn resample(&mut self, path: &[Point], key_width: f32) -> bool {
        let mut total_px = 0f32;
        for i in 1..path.len() {
            total_px += distance(&path[i - 1], &path[i]);
        }
        if total_px / key_width < MIN_STROKE_LENGTH {
            return false;
        }
        let n = workspace::samples_for(total_px / key_width);
        self.ws.samples = n;
        let step = total_px / (n - 1) as f32;
        self.ws.arc_step = step / key_width;
        let arc_step = self.ws.arc_step;
        for j in 0..n {
            self.ws.arc_at[j] = j as f32 * arc_step;
        }
        self.ws.collapsed_samples = 0;
        let first = path[0];
        self.ws.path_x[0] = first.x / key_width;
        self.ws.path_y[0] = first.y / key_width;
        self.ws.path_t[0] = first.t;
        let mut out = 1;
        let mut index = 0;
        let (mut cx, mut cy, mut ct) = (first.x, first.y, first.t);
        let mut accumulated = 0f32;
        while out < n - 1 && index + 1 < path.len() {
            let next = path[index + 1];
            let segment = ((next.x - cx) * (next.x - cx) + (next.y - cy) * (next.y - cy)).sqrt();
            if accumulated + segment >= step && segment > 0.0 {
                let fraction = (step - accumulated) / segment;
                cx += fraction * (next.x - cx);
                cy += fraction * (next.y - cy);
                ct += ((next.t - ct) as f32 * fraction) as i64;
                self.ws.path_x[out] = cx / key_width;
                self.ws.path_y[out] = cy / key_width;
                self.ws.path_t[out] = ct;
                out += 1;
                accumulated = 0.0;
            } else {
                accumulated += segment;
                cx = next.x;
                cy = next.y;
                ct = next.t;
                index += 1;
            }
        }
        let last = path[path.len() - 1];
        while out < n {
            self.ws.path_x[out] = last.x / key_width;
            self.ws.path_y[out] = last.y / key_width;
            self.ws.path_t[out] = last.t;
            out += 1;
        }
        self.map_open_ends(path, total_px);
        true
    }

    /// Where the open head ends and the open tail begins on the resampled
    /// stroke (#968): the raw sample counts in `open_head` and `open_tail`,
    /// read off the path by arc length. At least one sample stays closed at
    /// each end, and the two zones never meet.
    fn map_open_ends(&mut self, path: &[Point], total_px: f32) {
        let n = self.ws.samples;
        self.ws.open_head_to = 0;
        self.ws.open_tail_from = n - 1;
        self.ws.open_ends = false;
        if (self.open_head == 0 && self.open_tail == 0) || total_px <= 0.0 || path.len() < 2 {
            return;
        }
        let at = |raw: usize| -> usize {
            let mut arc = 0f32;
            for i in 1..=raw.min(path.len() - 1) {
                arc += distance(&path[i - 1], &path[i]);
            }
            ((arc / total_px) * (n - 1) as f32).round() as usize
        };
        if self.open_head > 0 {
            self.ws.open_head_to = at(self.open_head.min(path.len() - 1)).min(n - 2);
        }
        if self.open_tail > 0 {
            let raw = path.len() - 1 - self.open_tail.min(path.len() - 1);
            self.ws.open_tail_from = at(raw).max(1).max(self.ws.open_head_to + 1).min(n - 1);
        }
        self.ws.open_ends = self.ws.open_head_to > 0 || self.ws.open_tail_from < n - 1;
    }
}

/// How many samples at one end of `path` are a straight walk to or from
/// the spacebar (#968): from the bar end inward, every sample that lies
/// below the next one inward (within [`OPEN_RUN_LEVEL`] of level: the bar
/// is under the keys, so the walk descends toward it in a tail and climbs
/// away from it in a head), for as long as the samples between stay within
/// [`OPEN_RUN_BEND`] key widths of the straight line from the bar end to
/// that sample. Straight, not vertical: the bar spans the middle five keys,
/// so a word ending on `p` walks to it diagonally. The first bend is the
/// corner at the letter the walk left. The run has to drop at least [`OPEN_RUN_DESCENT`]
/// in all, so the shallow last leg of an ordinary word does not pass for
/// one. The letter the walk left may sit on the run itself ("then": `n` is
/// straight above the bar), which is why the run becomes optional for the
/// decoder rather than cut. `0` for no run, and never more than leaves
/// three samples closed.
pub fn open_run(path: &[Point], key_width: f32, at_end: bool) -> usize {
    let n = path.len();
    if n < 4 || key_width <= 0.0 {
        return 0;
    }
    let level = OPEN_RUN_LEVEL * key_width;
    let bend = OPEN_RUN_BEND * key_width;
    let at = |i: usize| if at_end { path[n - 1 - i] } else { path[i] };
    let bar_end = at(0);
    let mut run = 0usize;
    let max_run = n - 3;
    while run < max_run {
        // The next sample inward, and the one between it and the bar.
        let (inner, outer) = (at(run + 1), at(run));
        // The bar-side sample sits lower on the board than the one inward.
        if outer.y < inner.y - level {
            break;
        }
        // Every sample so far on the straight line to the new one.
        let (dx, dy) = (inner.x - bar_end.x, inner.y - bar_end.y);
        let reach = (dx * dx + dy * dy).sqrt().max(1e-3);
        if (1..=run)
            .any(|i| ((at(i).x - bar_end.x) * dy - (at(i).y - bar_end.y) * dx).abs() > bend * reach)
        {
            break;
        }
        run += 1;
    }
    if run < 2 {
        return 0;
    }
    if bar_end.y - at(run).y < OPEN_RUN_DESCENT * key_width {
        return 0;
    }
    run
}

/// `open_run`: how much a sample may sit above the next one inward, in key
/// widths, and still be part of the walk.
pub const OPEN_RUN_LEVEL: f32 = 0.05;

/// `open_run`: how far a sample may lie off the straight line of the walk, in
/// key widths. On phrases of real strokes joined by curved walks (`PHRASES=1`
/// in `glide_beam_eval`), words read right: .790 at 0.15, .781 at 0.25, .766
/// at 0.4, against .792 told the walks' true lengths. A hand curves more than
/// the harness does, so this sits a little wide of the best.
pub const OPEN_RUN_BEND: f32 = 0.2;

/// `open_run`: the least the walk must descend toward the bar in all, in key
/// widths. The bottom row's centre is about seven tenths of a key above
/// the bar's edge.
pub const OPEN_RUN_DESCENT: f32 = 0.5;

fn distance(a: &Point, b: &Point) -> f32 {
    let dx = b.x - a.x;
    let dy = b.y - a.y;
    (dx * dx + dy * dy).sqrt()
}

pub(super) fn quantise(xs: &[f32], ys: &[f32], out: &mut [i8]) {
    for j in 0..SHAPE_POINTS {
        out[2 * j] =
            ((xs[j] * SHAPE_QUANT) as i32).clamp(-SHAPE_BYTE_LIMIT, SHAPE_BYTE_LIMIT) as i8;
        out[2 * j + 1] =
            ((ys[j] * SHAPE_QUANT) as i32).clamp(-SHAPE_BYTE_LIMIT, SHAPE_BYTE_LIMIT) as i8;
    }
}

pub(super) fn normalise_in_place(xs: &mut [f32], ys: &mut [f32]) {
    let n = SHAPE_POINTS;
    let (mut cx, mut cy) = (0f32, 0f32);
    for j in 0..n {
        cx += xs[j];
        cy += ys[j];
    }
    cx /= n as f32;
    cy /= n as f32;
    let mut spread = 0f32;
    for j in 0..n {
        let dx = xs[j] - cx;
        let dy = ys[j] - cy;
        spread += dx * dx + dy * dy;
    }
    let root = (spread / n as f32).sqrt();
    let scale = if root > MIN_SHAPE_SPREAD { root } else { 1.0 };
    for j in 0..n {
        xs[j] = (xs[j] - cx) / scale;
        ys[j] = (ys[j] - cy) / scale;
    }
}

pub(super) fn resample_polyline(
    xs: &[f32],
    ys: &[f32],
    count: usize,
    out_x: &mut [f32],
    out_y: &mut [f32],
) {
    let n = SHAPE_POINTS;
    let mut total = 0f32;
    for i in 1..count {
        let dx = xs[i] - xs[i - 1];
        let dy = ys[i] - ys[i - 1];
        total += (dx * dx + dy * dy).sqrt();
    }
    if total <= 0.0 {
        for j in 0..n {
            out_x[j] = xs[0];
            out_y[j] = ys[0];
        }
        return;
    }
    let step = total / (n - 1) as f32;
    out_x[0] = xs[0];
    out_y[0] = ys[0];
    let mut out = 1;
    let mut index = 0;
    let (mut cx, mut cy) = (xs[0], ys[0]);
    let mut accumulated = 0f32;
    while out < n - 1 && index + 1 < count {
        let (nx, ny) = (xs[index + 1], ys[index + 1]);
        let segment = ((nx - cx) * (nx - cx) + (ny - cy) * (ny - cy)).sqrt();
        if accumulated + segment >= step && segment > 0.0 {
            let fraction = (step - accumulated) / segment;
            cx += fraction * (nx - cx);
            cy += fraction * (ny - cy);
            out_x[out] = cx;
            out_y[out] = cy;
            out += 1;
            accumulated = 0.0;
        } else {
            accumulated += segment;
            cx = nx;
            cy = ny;
            index += 1;
        }
    }
    while out < n {
        out_x[out] = xs[count - 1];
        out_y[out] = ys[count - 1];
        out += 1;
    }
}

pub(super) fn anchor_mask(x: f32, y: f32, keys: &KeyMap, out: &mut [bool], radius_sq: f32) {
    for k in 0..keys.key_count() {
        let dx = x - keys.key_x[k];
        let dy = y - keys.key_y[k];
        out[k] = dx * dx + dy * dy <= radius_sq;
    }
}
