#!/usr/bin/env python3
"""How much do dedicated umlaut keys buy the German decoder?

Builds two QWERTZ grids, draws the same word list on each as synthetic
strokes (key centres, straight segments, Gaussian noise), and runs
`glide_beam_eval` with the German profile:

  longpress  the app's 10-column grid; u/o/a/s also type ue/oe/ae/ss at the
             same centre, exactly what `GlideKeyMap.of` builds from the
             long-press alternates
  base26     the same grid with only a-z: what a decoder sees when the
             long-press entries are not in its key map (a lower bound)
  umlauts    an 11-column QWERTZ with ue/oe/ae/ss on keys of their own
             (FUTO's German geometry plus ss at the end of the bottom row)

The strokes are synthetic, so the absolute numbers are optimistic; what
transfers is the difference between the grids.

    unzip data/wmk-glide-de-data.zip -d /tmp/wmk-data
    python3 tools/synth_layout_eval.py \
        --words /tmp/wmk-data/de_150k.txt \
        --engine /path/to/wmkeyboard/native/wm-engine \
        --targets 1324 --noise 0.05
"""

import argparse
import json
import math
import os
import random
import subprocess
import tempfile

# QWERTY 10-column grid (FUTO's qwerty.json), y/z swapped for QWERTZ.
QWERTY = {}
for i, c in enumerate("qwertyuiop"):
    QWERTY[c] = (0.05 + 0.10 * i, 1 / 6)
for i, c in enumerate("asdfghjkl"):
    QWERTY[c] = (0.10046728971962617 + 0.1 * i, 0.5)
for i, c in enumerate("zxcvbnm"):
    QWERTY[c] = (0.20046728971962616 + 0.1 * i, 5 / 6)
QWERTY["z"], QWERTY["y"] = QWERTY["y"], QWERTY["z"]

# German 11-column grid (FUTO's german.json) plus ss in the empty bottom slot.
GERMAN = {}
for i, c in enumerate("qwertzuiop\u00fc"):
    GERMAN[c] = (0.04532710280373832 + 0.09090909090909091 * i, 1 / 6)
for i, c in enumerate("asdfghjkl\u00f6\u00e4"):
    GERMAN[c] = (0.04532710280373832 + 0.09090909090909091 * i, 0.5)
for i, c in enumerate("yxcvbnm"):
    GERMAN[c] = (0.22757009345794393 + 0.09090909090909091 * i, 5 / 6)
GERMAN["\u00df"] = (0.8636363636363636, 5 / 6)

LONGPRESS = dict(QWERTY)
for twin, base in {"\u00fc": "u", "\u00f6": "o", "\u00e4": "a", "\u00df": "s"}.items():
    LONGPRESS[twin] = LONGPRESS[base]
BASE26 = dict(QWERTY)


def layout_json(path, centres):
    keys = [{"letter": c, "cx": x, "cy": y} for c, (x, y) in sorted(centres.items())]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"keys": keys}, f, ensure_ascii=False, indent=1)


def swipe(word, centres, cols, rng, noise, step=0.2):
    points = [centres[word[0]]]
    for a, b in zip(word, word[1:]):
        (x0, y0), (x1, y1) = centres[a], centres[b]
        distance = math.hypot((x1 - x0) * cols, (y1 - y0) * cols)  # key widths
        steps = max(1, math.ceil(distance / step))
        for k in range(1, steps + 1):
            f = k / steps
            points.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
    return [[x + rng.gauss(0, noise) / cols, y + rng.gauss(0, noise) / cols] for x, y in points]


def records(path, words, centres, cols, rng, noise):
    width, height = cols * 60.0, 3 * 84.0
    with open(path, "w", encoding="utf-8") as f:
        for word in words:
            points = swipe(word, centres, cols, rng, noise)
            record = {
                "word": word,
                "canvas_width": width,
                "canvas_height": height,
                "data": [{"x": x, "y": y, "t": i * 8} for i, (x, y) in enumerate(points)],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(engine, records_path, layout_path, words_path, cols, profile):
    binary = os.path.join(engine, "target/release/examples/glide_beam_eval")
    env = dict(os.environ, COLS=str(cols), ALL="1", THREADS="8", RESULTS="4")
    out = subprocess.run(
        [binary, records_path, layout_path, words_path],
        input=profile + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    line = [x for x in out.stdout.splitlines() if x.startswith("top1")][-1]
    fields = line.split()
    return float(fields[1]), float(fields[3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True, help="frequency list (word count per line)")
    ap.add_argument("--engine", required=True, help="wmkeyboard/native/wm-engine")
    ap.add_argument("--targets", type=int, default=1324)
    ap.add_argument("--noise", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=966)
    ap.add_argument("--out", default=None)
    ap.add_argument("--profile", default="freq_weight=0.5 gap_weight=2.0")
    args = ap.parse_args()

    words = [line.split()[0] for line in open(args.words, encoding="utf-8") if line.split()]
    words = [w for w in words if len(w) >= 2 and w.isalpha() and all(c in GERMAN for c in w)][: args.targets]
    out = args.out or tempfile.mkdtemp(prefix="wmk-synth-")
    os.makedirs(out, exist_ok=True)

    # draw on one grid, decode on another: base26 keeps the long-press
    # strokes (the finger still lands on u/o/a/s) but hides the umlaut codes
    # from the decoder, which is the lower bound the old 77 % figure came from.
    variants = [
        ("longpress", LONGPRESS, LONGPRESS, 10),
        ("base26", LONGPRESS, BASE26, 10),
        ("umlauts", GERMAN, GERMAN, 11),
    ]
    print(f"{len(words)} words, noise {args.noise:.2f} key widths, profile {args.profile!r}")
    print(f"{'layout':10} {'top-1':>7} {'top-4':>7}")
    results = {}
    for name, draw, decode, cols in variants:
        layout = os.path.join(out, f"layout_{name}.json")
        strokes = os.path.join(out, f"{name}.jsonl")
        layout_json(layout, decode)
        records(strokes, words, draw, cols, random.Random(args.seed), args.noise)
        top1, top4 = run(args.engine, strokes, layout, args.words, cols, args.profile)
        results[name] = (top1, top4)
        print(f"{name:10} {100 * top1:6.2f}% {100 * top4:6.2f}%")
    lp, um = results["longpress"][0], results["umlauts"][0]
    print(f"\nlong-press -> dedicated keys: {100 * (um - lp):+.2f} points")


if __name__ == "__main__":
    main()
