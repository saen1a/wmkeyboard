#!/usr/bin/env python3
"""Would a two-model teacher (Qwen + gpt-oss) beat the better one alone?

Different models tokenize differently, so a token-level blend is impossible.
Word level is not: every model's candidates are mapped onto the *student*
vocabulary, and the true word's probability is exact in both (`actual_p`).
This probe puts both teachers on that common ground and reports

* word-level NLL of each single teacher and of a weighted blend for a pi grid,
* captured mass per teacher and for the **union** of their candidates,
* how often the two candidate sets overlap at all.

    TOGETHER_API_KEY=... python3 ensemble_probe.py --sentences 60
    python3 ensemble_probe.py --self-test
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for extra in (HERE, os.path.abspath(os.path.join(HERE, "..", "scaleway"))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import client as tg            # noqa: E402
import together_common as tc   # noqa: E402
import vllm_common as vc       # noqa: E402
import wordmap as wm           # noqa: E402

DEFAULT_SENTENCES = os.path.abspath(os.path.join(
    HERE, "..", "..", "artifacts", "out", "ab_sentences.tsv"))
DEFAULT_MODELS = ["Qwen/Qwen3.5-9B", "openai/gpt-oss-120b"]
PRICE_IN = {"Qwen/Qwen3.5-9B": 0.17, "openai/gpt-oss-120b": 0.15}


def load_sentences(path, limit=0):
    """`[(class, text), ...]` — the class split matters: Qwen wins chat, GLM wins news."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                rows.append((parts[0], parts[2]))
    return rows[:limit] if limit else rows


def build_vocab(sentences):
    """Student vocabulary stand-in: the corpus' own word types.

    A stand-in, not the real 22.5k list (that lives with the corpus). It keeps
    the experiment honest because *both* teachers are mapped against the same
    list, so per-model differences are not a mapping artefact.
    """
    vc._load_common()
    seen = {}
    for text in sentences:
        for w in text.split():
            key = w.strip(".,!?;:\"'()").lower()
            if key and key.replace("-", "").isalpha():
                seen.setdefault(key, True)
    return list(vc.SPECIALS) + sorted(seen)


def sentence_rows(choice, text, ends, actual, by_first, topk=8, temperature=1.0):
    """Rows for one sentence from an already-fetched answer (no request here)."""
    ch = choice
    if "".join(ch.tokens[:ch.prompt_tokens]) != text:
        return None
    ids, probs, mass, act, ap, _ = tc.rows_from_sentence(
        ch.tokens, ch.logs, ch.alts, ch.prompt_tokens, ends, by_first,
        topk=topk, actual=actual, temperature=temperature)
    return ids, probs, mass, act, ap


def word_prompt_parts(vocab, text_words):
    """`text`, char end offsets and student ids for a raw sentence."""
    text, ends, ids = "", [], []
    for w in text_words:
        text += " " + w
        ends.append(len(text))
        ids.append(vocab.index(w) if w in vocab else -1)
    return text, ends, ids


def blend_metrics(per_model, pis=(0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0)):
    """`per_model`: {name: [(ids, probs, mass, actual_p, nll?), ...]} per row."""
    names = list(per_model)
    a, b = names[0], names[1]
    rows = min(len(per_model[a]), len(per_model[b]))
    out = {"rows": rows, "single": {}, "blend": {}, "overlap": None,
           "union_mass_max": 0.0, "gain_rows": 0}
    if rows == 0:
        return out

    def row_abs(row):                      # absolute probability per student id
        ids, probs, mass, ap = row
        return {int(i): float(p) * float(mass) for i, p in zip(ids, probs) if p > 0}, float(ap)

    nll = {n: 0.0 for n in names}
    used = 0
    union_mass = 0.0
    overlap = 0
    jacc = []
    gains = 0
    mass_single = {n: 0.0 for n in names}
    blend_abs = {pi: 0.0 for pi in pis}
    for r in range(rows):
        absA, apA = row_abs(per_model[a][r])
        absB, apB = row_abs(per_model[b][r])
        mass_single[a] += float(per_model[a][r][2])
        mass_single[b] += float(per_model[b][r][2])
        # The same student word from two teachers must not be added twice:
        # the union aggregates by *max*, which is the "best single teacher per
        # word" bound. A π-weighted mean is reported separately via `blend`.
        union = dict(absA)
        for k, v in absB.items():
            union[k] = max(union.get(k, 0.0), v)
        union_mass += min(1.0, sum(union.values()))
        inter = set(absA) & set(absB)
        uni = set(absA) | set(absB)
        overlap += 1 if inter else 0
        if uni:
            jacc.append(len(inter) / len(uni))
        if apA > 0 and apB > 0:
            used += 1
            nll[a] += -math.log(apA)
            nll[b] += -math.log(apB)
            for pi in pis:
                p = pi * apA + (1 - pi) * apB
                blend_abs[pi] += -math.log(p) if p > 0 else 40.0
        if min(1.0, sum(union.values())) - max(float(per_model[a][r][2]),
                                               float(per_model[b][r][2])) > 0.10:
            gains += 1

    out["single"] = {n: {"mean_mass": mass_single[n] / rows,
                         "word_nll": (nll[n] / used) if used else None} for n in names}
    out["blend"] = {pi: (blend_abs[pi] / used) if used else None for pi in pis}
    out["overlap"] = overlap / rows
    out["jaccard"] = (sum(jacc) / len(jacc)) if jacc else None
    out["union_mass_max"] = union_mass / rows
    out["mass_gain"] = out["union_mass_max"] - max(out["single"][n]["mean_mass"]
                                                  for n in names)
    out["gain_rows"] = gains / rows
    out["pi_best"] = min(out["blend"], key=lambda k: out["blend"][k]) if used else None
    return out


def self_test():
    # model A: word 1 with p=0.4, model B: word 1 with p=0.2 + word 2 with 0.1
    a = [(np.array([1, 0]), np.array([1.0, 0.0], dtype=np.float16), 0.40, 0.30)]
    b = [(np.array([1, 2]), np.array([0.66, 0.34], dtype=np.float16), 0.30, 0.20)]
    per = {"A": [(list(r[0]), r[1], float(r[2]), float(r[3])) for r in a],
           "B": [(list(r[0]), r[1], float(r[2]), float(r[3])) for r in b]}
    m = blend_metrics(per)
    assert m["rows"] == 1, m
    assert abs(m["single"]["A"]["mean_mass"] - 0.40) < 1e-6, m
    # float16 storage in the probe's inputs -> 1e-3 tolerance
    assert abs(m["union_mass_max"] - (0.40 + 0.30 * 0.34)) < 1e-3, m
    assert abs(m["mass_gain"] - 0.102) < 1e-3, m
    assert m["overlap"] == 1.0
    # word NLL: A = -ln 0.30 = 1.204, B = -ln 0.20 = 1.609; blend pi=1 -> A
    assert abs(m["single"]["A"]["word_nll"] - 1.2039) < 1e-3, m
    assert abs(m["blend"][1.0] - 1.2039) < 1e-3, m
    assert m["pi_best"] == 1.0, m
    print("self-test ok: masses, union, overlap, word NLL, pi grid")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--sentences", default=DEFAULT_SENTENCES)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--per-class", type=int, default=0,
                    help="take N sentences from each class (the A/B file is sorted by class)")
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        self_test()
        return 0

    models = [m.strip() for m in a.models.split(",") if m.strip()]
    if len(models) != 2:
        ap.error("exactly two models")
    rows_in = load_sentences(a.sentences, a.limit)
    if a.per_class:
        seen = {}
        picked = []
        for cls, text in load_sentences(a.sentences, 0):
            if seen.get(cls, 0) < a.per_class:
                seen[cls] = seen.get(cls, 0) + 1
                picked.append((cls, text))
        rows_in = picked
    texts = [t for _, t in rows_in]
    vocab = build_vocab(texts)
    print(f"{len(texts)} sentences, {len(vocab)} word types", file=sys.stderr)

    clients, maps = {}, {}
    for m in models:
        clients[m] = tg.Client(model=m, key_file=a.key_file, batch=8)
        built = wm.build_map(vocab, clients[m].score, m)
        maps[m] = {tok: [(sid, tail) for sid, tail in entries]
                   for tok, entries in built["by_first"].items()}
        print(f"  {m}: {len(maps[m])} first tokens, "
              f"{built['unaligned']}/{built['forms']} unaligned", file=sys.stderr)

    flat = {m: [] for m in models}
    dropped = 0
    # One batched request per model for all sentences: the probe used to send
    # one request per sentence and timed out at 200 sentences.
    prompts, prepared = [], []
    for (cls, text) in rows_in:
        txt, ends, ids = word_prompt_parts(vocab, text.split())
        prompts.append(txt)
        prepared.append((cls, txt, ends, ids))
    answers = {m: clients[m].score(prompts) for m in models}

    per_class = {}
    for i, (cls, txt, ends, ids) in enumerate(prepared):
        got = {}
        for m in models:
            got[m] = sentence_rows(answers[m][i], txt, ends, ids, maps[m], a.topk,
                                   a.temperature)
        if any(v is None for v in got.values()):
            dropped += 1
            continue
        rows_n = min(got[m][0].shape[0] for m in models)
        bucket = per_class.setdefault(cls, {m: [] for m in models})
        for r in range(rows_n):
            for m in models:
                ids_m, probs_m, mass_m, _act, ap_m = got[m]
                row = (ids_m[r], probs_m[r], float(mass_m[r]), float(ap_m[r]))
                flat[m].append(row)
                bucket[m].append(row)

    res = {"models": models, "sentences": len(texts), "vocab": len(vocab),
           "dropped_sentences": dropped}
    res.update(blend_metrics(flat))
    res["by_class"] = {}
    for cls, buckets in per_class.items():
        m = blend_metrics(buckets)
        res["by_class"][cls] = {"rows": m["rows"],
                                "word_nll": {n: m["single"][n]["word_nll"]
                                             for n in m["single"]},
                                "blend_best": (min(m["blend"].values())
                                               if m["blend"] else None),
                                "pi_best": m["pi_best"],
                                "union_mass_max": m["union_mass_max"],
                                "mass_gain": m["mass_gain"]}
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    if a.out:
        tmp = a.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, ensure_ascii=False, default=str)
            f.write("\n")
        os.replace(tmp, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
