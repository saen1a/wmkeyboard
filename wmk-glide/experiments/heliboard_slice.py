#!/usr/bin/env python3
"""Turn HeliBoard gesture records into the glide beam harness's slices.

HeliBoard's published gesture records carry the keyboard geometry with every
stroke. The harness reads one layout per file, so this script samples a fixed
number of single-finger a-z strokes, groups them by geometry, and writes one
records.jsonl + layout.json per group.

    heliboard_slice.py --lang da --out /tmp/slices/da \
        --list /tmp/wordlists/da_aosp.txt \
        /tmp/helio/da/1/records.json /tmp/helio/da/3/records.json

Every output record is:

    {"word": "huis", "session": "<geometry>", "sentence": "",
     "word_idx": -1, "canvas_width": 1080, "canvas_height": 603,
     "data": [{"x": 0.1, "y": 0.2, "t": 12}, ...]}

and the layout is the harness's {"keys": [{"letter", "cx", "cy"}, ...]} with
cx/cy normalised to the canvas. The filter is the Finnish protocol: one pointer
id, an ASCII a-z target of at least two letters, and a geometry that holds every
letter of the target.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
from collections import defaultdict

AZ = re.compile(r"^[a-z]{2,}$")


def single_letter(value: object) -> str | None:
    if not isinstance(value, str) or len(value) != 1:
        return None
    ch = value.lower()
    return ch if ch.isalpha() else None


def geometry(record: dict) -> tuple[int, int, tuple, set[str]] | None:
    info = record.get("keyboardInfo")
    if not isinstance(info, dict):
        return None
    width = info.get("width")
    height = info.get("height")
    keys = info.get("keys")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return None
    if width <= 0 or height <= 0 or not isinstance(keys, list):
        return None
    letters: dict[str, tuple] = {}
    for key in keys:
        if not isinstance(key, dict):
            continue
        letter = single_letter(key.get("value"))
        if letter is None or letter in letters:
            continue
        try:
            left = float(key["left"])
            top = float(key["top"])
            kw = float(key["width"])
            kh = float(key["height"])
        except (KeyError, TypeError, ValueError):
            continue
        letters[letter] = (left, top, kw, kh)
    if len(letters) < 2:
        return None
    signature = (
        int(round(float(width))),
        int(round(float(height))),
        tuple(sorted((ch, int(round(v[0])), int(round(v[1])), int(round(v[2])), int(round(v[3]))) for ch, v in letters.items())),
    )
    return int(round(float(width))), int(round(float(height))), signature, set(letters)


def layout_for(record: dict) -> dict:
    info = record["keyboardInfo"]
    width = float(info["width"])
    height = float(info["height"])
    keys = []
    seen: set[str] = set()
    for key in info["keys"]:
        if not isinstance(key, dict):
            continue
        letter = single_letter(key.get("value"))
        if letter is None or letter in seen:
            continue
        seen.add(letter)
        left = float(key["left"])
        top = float(key["top"])
        kw = float(key["width"])
        kh = float(key["height"])
        keys.append({
            "letter": letter,
            "cx": (left + kw / 2.0) / width,
            "cy": (top + kh / 2.0) / height,
        })
    return {"keys": keys}


def record_points(record: dict) -> list[dict] | None:
    gesture = record.get("gesture")
    if not isinstance(gesture, list) or len(gesture) < 2:
        return None
    info = record["keyboardInfo"]
    width = float(info["width"])
    height = float(info["height"])
    points = []
    for point in gesture:
        if not isinstance(point, dict):
            return None
        if point.get("id", 0) != 0:
            return None
        try:
            x = float(point["x"]) / width
            y = float(point["y"]) / height
        except (KeyError, TypeError, ValueError):
            return None
        points.append({"x": x, "y": y, "t": int(point.get("millis", 0))})
    return points


def load_records(paths: list[str], word_list: str, alphabet: str, require_listed: bool) -> list[dict]:
    wanted: set[str] = set()
    if require_listed:
        with open(word_list, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                word = line.split()[0].lower() if line.split() else ""
                if word.isalpha() and len(word) >= 2:
                    wanted.add(word)
    out: list[dict] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            try:
                rows = json.load(fh)
            except json.JSONDecodeError as exc:
                print(f"{path}: {exc}", file=sys.stderr)
                continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            word = str(row.get("targetWord", "")).strip().lower()
            if alphabet == "az":
                ok = AZ.fullmatch(word) is not None
            else:
                ok = word.isalpha() and len(word) >= 2
            if not ok:
                continue
            if require_listed and word not in wanted:
                continue
            geo = geometry(row)
            if geo is None or not set(word) <= geo[3]:
                continue
            points = record_points(row)
            if points is None:
                continue
            out.append({"row": row, "word": word, "geo": geo, "points": points})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--list", required=True)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--alphabet", choices=("az", "full"), default="az")
    parser.add_argument("--require-listed", action="store_true")
    parser.add_argument("records", nargs="+")
    args = parser.parse_args()

    rows = load_records(args.records, args.list, args.alphabet, args.require_listed)
    if not rows:
        print(f"{args.lang}: no eligible records", file=sys.stderr)
        return 1
    rows.sort(key=lambda r: (
        r["word"],
        len(r["points"]),
        str(r["row"].get("uuid", "")),
        r["points"][0]["x"],
        r["points"][0]["y"],
    ))
    rng = random.Random(args.seed)
    take = min(args.count, len(rows))
    sample = rng.sample(rows, take)

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in sample:
        groups[r["geo"][2]].append(r)

    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(args.out, exist_ok=True)
    manifest = []
    for index, (signature, members) in enumerate(sorted(groups.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))):
        group = f"g{index:02d}"
        directory = os.path.join(args.out, group)
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "records.jsonl"), "w", encoding="utf-8") as fh:
            for r in members:
                info = r["row"]["keyboardInfo"]
                fh.write(json.dumps({
                    "word": r["word"],
                    "session": group,
                    "sentence": "",
                    "word_idx": -1,
                    "canvas_width": float(info["width"]),
                    "canvas_height": float(info["height"]),
                    "data": r["points"],
                }, separators=(",", ":")) + "\n")
        with open(os.path.join(directory, "layout.json"), "w", encoding="utf-8") as fh:
            json.dump(layout_for(members[0]["row"]), fh, separators=(",", ":"))
        manifest.append({"group": group, "strokes": len(members), "width": signature[0], "height": signature[1]})
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "language": args.lang,
            "alphabet": args.alphabet,
            "require_listed": args.require_listed,
            "eligible": len(rows),
            "sampled": len(sample),
            "seed": args.seed,
            "groups": manifest,
        }, fh, indent=2)
    print(f"{args.lang}: eligible {len(rows)}, sampled {len(sample)}, groups {len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
