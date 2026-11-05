#!/usr/bin/env python3
"""Shared vLLM-offline plumbing for the German H100 teacher run.

`distill_vllm.py`, `benchmark_quick.py` and `benchmark_prompt_logprobs.py`
all need the same three things, and they must agree with
`tools/wmlm/distill.py` (patched by `wmk-glide/patches/0005-...`), because
the `.npz` they write is consumed unchanged by `tools/wmlm/train.py`:

1. **The prompt.** `distill.py` turns the student tokens of `train.npz`
   back into the raw text the teacher reads: drop the 4-token prefix
   (`reg`, `field`, `lang`, `<s>`), join `##` continuation pieces onto the
   word they belong to, and keep the character end offset of every word.
2. **The word -> teacher-token mapping.** A student word maps to the
   teacher token sequence for `" word"` (lower case and capitalised);
   with `multi=1` a word spelled in several tokens keeps the product of
   its conditional token probabilities, which is the `word_mass` rule of
   patch 0005. With `multi=0` only single-token words map (old rule).
3. **The soft rows.** Row `k` of a sentence is the teacher's next-word
   distribution after word `k-1`, projected onto the student vocabulary,
   top-k renormalised, `float16`/`int16`. Row 0 is zeros.

The one difference to the `transformers` path: vLLM gives us
`prompt_logprobs`, i.e. the top-k distribution over each *actual* prompt
position, not the full vocabulary. That is enough because
 - the first factor of every candidate word is read from the returned
   top-k distribution (a word outside it simply gets no mass, exactly like
   a word outside `topk` in `distill.py`), and
 - every later factor of a multi-token word is the probability of the
   *actual* token at that later position, which vLLM always includes, so
   no factor is lost to truncation.

No chat template, no special tokens beyond what `train.npz` already holds.
"""
import json
import math
import os
import sys

import numpy as np

PREFIX_LEN = 4  # reg field lang <s>

# Imported lazily so the module stays importable without the repo checkout
# (the shell scripts put <repo>/tools/wmlm on PYTHONPATH; this is the
# fallback for a copied tree).
SPECIALS = None
START, CONT = "\u2581", "##"


def _load_common(repo_root=None):
    """Import `tools/wmlm/common.py` and cache its constants."""
    global SPECIALS, START, CONT
    if SPECIALS is not None:
        return
    roots = []
    if repo_root:
        roots.append(os.path.join(repo_root, "tools", "wmlm"))
    here = os.path.dirname(os.path.abspath(__file__))
    # wmk-glide/cloud/scaleway -> repo root is three levels up.
    roots.append(os.path.abspath(os.path.join(here, "..", "..", "..", "tools", "wmlm")))
    for root in roots:
        if os.path.isfile(os.path.join(root, "common.py")):
            if root not in sys.path:
                sys.path.insert(0, root)
            import common  # noqa: PLC0415 - resolved at runtime

            SPECIALS = list(common.SPECIALS)
            START, CONT = common.START, common.CONT
            return
    raise SystemExit(
        "cannot find tools/wmlm/common.py; run from the repo (python3 "
        "wmk-glide/cloud/scaleway/<script>.py) or set WMLM_REPO"
    )


def load_corpus(data_dir, repo_root=None):
    """vocab.txt + train.npz of a `prep.py` output directory."""
    _load_common(repo_root)
    with open(os.path.join(data_dir, "vocab.txt"), encoding="utf-8") as f:
        vocab = [line.rstrip("\n") for line in f]
    z = np.load(os.path.join(data_dir, "train.npz"))
    return vocab, z["tokens"], z["starts"]


def select_indices(n, sentences, seed=0, start=0, count=0):
    """The exact selection `distill.py` makes, so chunks line up.

    sorted(rng.choice(n, size=min(sentences, n), replace=False)) then the
    optional [start : start+count] slice used by the chunked runs.
    """
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(n, size=min(sentences, n), replace=False))
    if count:
        chosen = chosen[start : start + count]
    return chosen


def prompt_text(vocab, row):
    """(text, word_end_offsets) for one train.npz row, as distill.py builds it."""
    text, ends = "", []
    for t in row[PREFIX_LEN:-1]:  # drop prefix and </s>
        w = vocab[int(t)]
        if w.startswith(CONT):
            text += w[len(CONT) :]
            if ends:
                ends[-1] = len(text)
        else:
            text += " " + (w[len(START) :] if w.startswith(START) else w)
            ends.append(len(text))
    return text, ends


def student_to_teacher(vocab, encode, multi=True):
    """student id -> list of teacher token sequences.

    `encode(" word")` returns the teacher token ids for one form (a stub is
    enough for the self-test). Words the teacher cannot spell are skipped.
    """
    mapping = []
    for sid, w in enumerate(vocab):
        if sid < len(SPECIALS) or w.startswith(START) or w.startswith(CONT):
            continue
        seqs = []
        for form in {w, w.capitalize()}:
            enc = encode(" " + form)
            if not enc:
                continue
            if not multi and len(enc) != 1:
                continue
            seqs.append(enc)
        if seqs:
            mapping.append((sid, seqs))
    return mapping


def index_mapping(mapping):
    """first teacher token id -> [(student id, tail token ids), ...]."""
    by_first = {}
    for sid, seqs in mapping:
        for seq in seqs:
            by_first.setdefault(seq[0], []).append((sid, seq[1:]))
    return by_first


def word_positions(ends, tok_ends):
    """Teacher token index that ends each word (or None when unaligned)."""
    by_end = {}
    for idx, end in enumerate(tok_ends):
        by_end[end] = idx
    return [by_end.get(e) for e in ends]


def rows_from_logprobs(prompt_logprobs, n_tokens, positions, by_first, topk, id_dtype=np.int16):
    """Soft rows for one sentence from vLLM's per-position top-k dicts.

    `positions[k]` is the teacher token that ends student word `k`;
    the distribution over the next word is `prompt_logprobs[positions[k]+1]`
    (vLLM's position p gives P(token p | tokens < p), the same thing
    `probs[i, j]` gives at HF logit j = p-1).

    `id_dtype` must hold every student id: `distill.py` narrows to int16
    only when the vocabulary fits, int32 otherwise, and narrowing after the
    rows were written would silently wrap ids >= 32768.

    Returns (ids [words, topk] int, probs [words, topk] float, stats).
    """
    words = len(positions)
    ids = np.zeros((words, topk), dtype=id_dtype)
    probs = np.zeros((words, topk), dtype=np.float16)
    stats = {
        "rows": 0,
        "nonfinite": 0,
        "width_min": topk,
        "skipped": 0,
    }
    for k in range(1, words):
        j = positions[k - 1]
        if j is None:
            stats["skipped"] += 1
            continue
        p = j + 1
        if p >= n_tokens:
            stats["skipped"] += 1
            continue
        dist = prompt_logprobs[p] if prompt_logprobs else None
        if not dist:
            stats["skipped"] += 1
            continue

        # Non-finite logprobs are a corruption signal, not a candidate.
        stats["nonfinite"] += sum(
            1
            for lp in dist.values()
            if lp.logprob is None or not np.isfinite(lp.logprob)
        )

        mass = {}
        for tid, lp in dist.items():
            v = lp.logprob
            if v is None or not np.isfinite(v):
                continue
            entries = by_first.get(tid)
            if not entries:
                continue
            base = np.exp(v)
            for sid, tail in entries:
                m = base
                for off, t in enumerate(tail, start=1):
                    q = p + off
                    d = prompt_logprobs[q] if q < n_tokens else None
                    lp2 = d.get(t) if d else None
                    if lp2 is None or lp2.logprob is None or not np.isfinite(lp2.logprob):
                        m = 0.0
                        break
                    m *= np.exp(lp2.logprob)
                    if m == 0.0:
                        break
                if m > 0.0:
                    mass[sid] = mass.get(sid, 0.0) + m

        stats["width_min"] = min(stats["width_min"], len(dist))
        if not mass:
            stats["rows"] += 1
            continue
        ranked = sorted(mass.items(), key=lambda kv: (-kv[1], kv[0]))[:topk]
        total = sum(v for _, v in ranked)
        if total <= 0:
            stats["rows"] += 1
            continue
        for i, (sid, v) in enumerate(ranked):
            ids[k, i] = sid
            probs[k, i] = v / total
        stats["rows"] += 1
    return ids, probs, stats


def nll_for_row(prompt_logprobs, p, token_id):
    """(logprob, rank) of the actual token at position p, or None."""
    dist = prompt_logprobs[p] if prompt_logprobs else None
    if not dist:
        return None
    lp = dist.get(token_id)
    if lp is None or lp.logprob is None or not np.isfinite(lp.logprob):
        return None
    return float(lp.logprob), int(getattr(lp, "rank", -1) or -1)


def sentence_stats(prompt_logprobs, token_ids):
    """Actual-token NLL/rank over positions 1..n-1 of one prompt."""
    n = len(token_ids)
    nll = 0.0
    rows = 0
    missing = 0
    widths = []
    top1 = 0
    for p in range(1, n):
        got = nll_for_row(prompt_logprobs, p, token_ids[p])
        if got is None:
            missing += 1
            continue
        lp, _rank = got
        nll += -lp
        rows += 1
        dist = prompt_logprobs[p]
        widths.append(len(dist))
        best = max((v.logprob for v in dist.values() if v.logprob is not None), default=None)
        if best is not None and abs(best - lp) < 1e-9:
            top1 += 1
    return {
        "rows": rows,
        "missing": missing,
        "mean_nll": (nll / rows) if rows else None,
        "top1": (top1 / rows) if rows else None,
        "width_mean": (sum(widths) / len(widths)) if widths else None,
        "width_min": min(widths) if widths else None,
    }


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def teacher_info(llm):
    """Model/quantisation/speculative-decoding facts for the report."""
    info = {"model": None, "quantization": None, "speculative": None, "max_model_len": None}
    try:
        cfg = llm.llm_engine.model_config
        info["model"] = getattr(cfg, "model", None) or getattr(cfg, "served_model_name", None)
        info["quantization"] = getattr(cfg, "quantization", None)
        info["max_model_len"] = getattr(cfg, "max_model_len", None)
    except Exception:  # noqa: BLE001 - reporting only
        pass
    try:
        vcfg = llm.llm_engine.vllm_config
        spec = getattr(vcfg, "speculative_config", None)
        info["speculative"] = None if spec is None else str(spec)
    except Exception:  # noqa: BLE001 - older/newer vLLM layout
        pass
    try:
        import torch  # noqa: PLC0415

        info["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
        info["torch"] = torch.__version__
    except Exception:  # noqa: BLE001
        pass
    try:
        import vllm  # noqa: PLC0415

        info["vllm"] = vllm.__version__
    except Exception:  # noqa: BLE001
        pass
    return info


# ---------------------------------------------------------------- self-test


class _LP:
    __slots__ = ("logprob", "rank")

    def __init__(self, logprob, rank=-1):
        self.logprob = logprob
        self.rank = rank


def self_test():
    """Hand-computed checks for the text/offset bridge and the row builder."""
    _load_common()
    vocab = list(SPECIALS) + ["ich", "will", "hause", "fahren", "\u2581hau", "##se"]
    ich, will, hause, fahren = (vocab.index(w) for w in ("ich", "will", "hause", "fahren"))
    hau, se = vocab.index("\u2581hau"), vocab.index("##se")

    # 1. prompt_text: prefix and </s> dropped, a piece joins its word.
    row = [0, 0, 0, 0, ich, will, hau, se, 2]
    text, ends = prompt_text(vocab, row)
    assert text == " ich will hause", repr(text)
    assert ends == [4, 9, 15], ends

    # 2. word_positions: aligned ends map, an off-grid end does not.
    assert word_positions(ends, [4, 9, 15]) == [0, 1, 2]
    assert word_positions(ends, [3, 9, 15]) == [None, 1, 2]

    # 3. Single-token words: top-k + renormalisation, exactly as distill.py.
    #    Lower case and capitalised are distinct teacher tokens (as in Qwen),
    #    and their masses add, so only the forms present in the dict count.
    forms = {
        " ich": [10],
        " Ich": [40],
        " will": [11],
        " Will": [41],
        " hause": [12],
        " Hause": [42],
        " fahren": [13],
        " Fahren": [43],
    }
    mapping = student_to_teacher(vocab, lambda s: forms.get(s, []), multi=True)
    by_first = index_mapping(mapping)
    lp = math.log
    dist = {10: _LP(lp(0.50)), 11: _LP(lp(0.30)), 12: _LP(lp(0.10)),
            13: _LP(lp(0.05)), 99: _LP(lp(0.05))}
    ids, probs, stats = rows_from_logprobs([None, dist], 2, [0, 0, 0], by_first, topk=2)
    # Row 1 + row 2 both read the same position here; each word form is one
    # token, so the ranking is by probability and renormalised over top-2.
    assert ids[1].tolist() == [ich, will], ids[1]
    assert abs(float(probs[1, 0]) - 0.50 / 0.80) < 1e-3, probs[1]
    assert abs(float(probs[1, 1]) - 0.30 / 0.80) < 1e-3, probs[1]
    assert stats["rows"] == 2

    # 4. Multi-token word: p = p(t1) * p(t2 | t1), from two positions.
    forms[" hause"] = [20, 21]
    forms[" Hause"] = [30, 31]
    mapping = student_to_teacher(vocab, lambda s: forms.get(s, []), multi=True)
    by_first = index_mapping(mapping)
    d0 = {20: _LP(lp(0.40)), 11: _LP(lp(0.60))}
    d1 = {21: _LP(lp(0.50))}
    ids, probs, _ = rows_from_logprobs([None, d0, d1], 3, [0, 0], by_first, topk=2)
    # will = 0.60, hause = 0.40 * 0.50 = 0.20 -> normalised 0.75 / 0.25
    assert ids[1, 0] == will and ids[1, 1] == hause, ids[1]
    assert abs(float(probs[1, 0]) - 0.75) < 1e-3, probs[1]
    assert abs(float(probs[1, 1]) - 0.25) < 1e-3, probs[1]

    # 5. A tail token outside the returned top-k is a zero, not a guess.
    ids, probs, _ = rows_from_logprobs([None, d0, {99: _LP(lp(0.9))}], 3, [0, 0], by_first, topk=2)
    assert ids[1, 0] == will and float(probs[1, 0]) == 1.0, (ids[1], probs[1])

    # 6. non-finite logprobs are counted, never used.
    _, _, stats = rows_from_logprobs([None, {11: _LP(float("nan"))}], 2, [0, 0], by_first, topk=2)
    assert stats["nonfinite"] == 1, stats
    print("self-test ok: prompt text, offsets, single/multi-token rows, truncation, NaN")


def main():
    if "--self-test" in sys.argv[1:]:
        self_test()
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
