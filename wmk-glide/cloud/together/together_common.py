#!/usr/bin/env python3
"""Target construction for a Together-AI teacher pull (German `.wmlm`).

This is the API twin of `cloud/scaleway/vllm_common.py`: same prompt, same
mapping rules, same `.npz` contract for `tools/wmlm/train.py`, different
transport. It deliberately *imports* `vllm_common` for everything that is
transport-independent (`load_corpus`, `prompt_text`, `select_indices`,
`student_to_teacher`, `index_mapping`, `word_positions`, JSON/JSONL helpers),
so the two collectors cannot drift apart.

What is different from vLLM, and why the code here is not a copy:

* vLLM returns `prompt_logprobs[p]` = the top-k token ids with logprobs.
  Together returns the same thing as **token strings** (`top_logprobs[p]`),
  *plus* the logprob of the token that is actually there (`token_logprobs[p]`).
  So the candidate set per position is `top_logprobs[p] ∪ {tokens[p]}` — at
  most 6, and it always contains the true token.
* That makes the multi-token word rule (`p(w) = p(t1)·p(t2|t1)·…`) usable for
  the **actual** word even when its first token is outside the returned
  top-k, because every later factor is the actual token's own logprob. Those
  rows are exactly the 15.3 % piece rows the top-24 pipeline scored 0.0 on.
* A word whose first token is outside the top-6 gets its exact probability
  injected as an extra candidate (`actual_p`, see `inject_actual`), because
  the echoed stream tells us that probability for free. The row is therefore
  *more* accurate than the teacher's truncated list, never less.
* Two extra per-row diagnostics are written to a **sibling** file
  (`<out>.audit.npz`), never into the four-key soft npz: `mass` (the teacher
  probability the row actually captured before renormalisation, i.e. `1 -
  residual`) and `actual` / `actual_p` (the true word's id and its exact
  teacher probability). The merged soft npz stays exactly the four arrays
  `check_soft.validate_soft` and `merge_soft.py` expect; the sibling is what
  a residual-bucket KD term and the per-row weighting need.

Row layout is the one `distill.py` writes: one row per word group, row `0` of
every sentence all-zero (`soft_mask.py fill` owns it), row `k` = the teacher's
next-word distribution after word `k-1`.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCALEWAY = os.path.abspath(os.path.join(HERE, "..", "scaleway"))
if SCALEWAY not in sys.path:
    sys.path.insert(0, SCALEWAY)

import vllm_common as vc  # noqa: E402  (path bootstrap above)

MAX_LOGPROBS = 5        # Together's hard cap (logprobs=6 -> HTTP 400)
MAX_CANDIDATES = MAX_LOGPROBS + 1   # returned alternatives + the actual token
DEFAULT_TOPK = 8        # 6 candidates + the injected actual word + headroom
AUDIT_KEYS = ("mass", "actual", "actual_p", "weight", "piece")


# ------------------------------------------------------------------ helpers
def candidates(tokens, logs, alts, p):
    """`{token string: logprob}` at position p: the best returned
    alternatives plus the actual token.

    The cap is enforced here, not trusted from the response: Together returns
    at most 5 alternatives (a hard API limit), and a provider that ever
    returned more must not silently change what a row means.
    """
    returned = {}
    if p < len(alts):
        for t, lp in alts[p].items():
            if isinstance(lp, (int, float)) and math.isfinite(lp):
                returned[t] = float(lp)
    if len(returned) > MAX_LOGPROBS:
        keep = sorted(returned.items(), key=lambda kv: -kv[1])[:MAX_LOGPROBS]
        returned = dict(keep)
    if p < len(tokens) and p < len(logs):
        lp = logs[p]
        if lp is not None and math.isfinite(lp):
            returned[tokens[p]] = float(lp)
    return returned


def token_char_ends(tokens, n):
    """Character end offset of each of the first n tokens."""
    ends, total = [], 0
    for t in tokens[:n]:
        total += len(t)
        ends.append(total)
    return ends


def spans(word_ends):
    """(start, end) character span per word, given the cumulative ends."""
    out, prev = [], 0
    for e in word_ends:
        out.append((prev, e))
        prev = e
    return out


def align_tokens(tokens, tok_ends, word_end, word_start):
    """Token indices covering one word's character span, or None.

    A word is covered when its span is fully inside consecutive tokens and at
    least one token ends exactly at `word_end` (the same rule
    `word_positions` uses: a boundary that is not on a token boundary leaves
    the row empty).
    """
    idx = [i for i, e in enumerate(tok_ends) if word_start < e <= word_end]
    if not idx or tok_ends[idx[0]] <= word_start:
        return None
    if tok_ends[-1] < word_end:
        return None
    first = idx[0]
    if tok_ends[first] - len(tokens[first]) > word_start:
        # The token starts before the word: it is shared with the previous
        # word, so this word has no own first token.
        return None
    return idx


def word_mass(tokens, logs, alts, tok_ends, word_start, word_end):
    """Exact teacher probability of the word occupying this span.

    `p(w) = exp(sum(log p(token)))` over the word's own tokens; `None` when
    the span is not token-aligned or a logprob is missing.
    """
    idx = align_tokens(tokens, tok_ends, word_end, word_start)
    if idx is None:
        return None
    total = 0.0
    for i in idx:
        lp = logs[i] if i < len(logs) else None
        if lp is None or not math.isfinite(lp):
            return None
        total += lp
    if total < -700.0:      # underflow guard: exp(-745) is the float64 floor
        return 0.0
    return math.exp(total)


# ------------------------------------------------------------- target rows
def rows_from_sentence(tokens, logs, alts, prompt_tokens, word_ends, by_first,
                       topk=DEFAULT_TOPK, id_dtype=np.int16, inject_actual=True,
                       actual=None, min_mass=0.0, temperature=1.0):
    """Soft rows for one sentence.

    `tokens`/`logs`/`alts` are the raw response arrays, `prompt_tokens` the
    echoed length (positions >= prompt_tokens are the generated token and are
    ignored), `word_ends` the character end offsets from
    `vllm_common.prompt_text`, `by_first` the string-keyed mapping from
    `index_mapping(student_to_teacher(vocab, encode))`.

    Returns `(ids, probs, mass, actual_id, actual_p, stats)` with
    `ids/probs` shaped `[len(word_ends), topk]` (row 0 all-zero),
    `mass/actual_id/actual_p` shaped `[len(word_ends)]`.
    """
    words = len(word_ends)
    ids = np.zeros((words, topk), dtype=id_dtype)
    probs = np.zeros((words, topk), dtype=np.float16)
    mass_out = np.zeros(words, dtype=np.float32)
    actual_out = np.full(words, -1, dtype=np.int32)
    actual_p_out = np.zeros(words, dtype=np.float32)
    stats = {
        "rows": words, "filled": 0, "skipped": 0, "injected": 0,
        "empty_after": 0, "nonfinite": 0, "width_min": MAX_CANDIDATES,
        "mass_sum": 0.0, "cand_sum": 0,
    }
    if words < 2 or prompt_tokens < 2:
        stats["skipped"] = words
        stats["empty_after"] = words
        return ids, probs, mass_out, actual_out, actual_p_out, stats

    n = min(prompt_tokens, len(tokens))
    tok_ends = token_char_ends(tokens, n)
    positions = vc.word_positions(word_ends, tok_ends)
    word_spans = spans(word_ends)

    for k in range(1, words):
        j = positions[k - 1]
        if j is None:
            stats["skipped"] += 1
            stats["empty_after"] += 1
            continue
        p = j + 1
        if p >= n:
            stats["skipped"] += 1
            stats["empty_after"] += 1
            continue
        cand = candidates(tokens, logs, alts, p)
        if not cand:
            stats["skipped"] += 1
            stats["empty_after"] += 1
            continue
        stats["width_min"] = min(stats["width_min"], len(cand))
        stats["cand_sum"] += len(cand)

        # 1) candidates from returned alternatives + the actual token
        mass = {}
        for t1, lp in cand.items():
            if not math.isfinite(lp):
                stats["nonfinite"] += 1
                continue
            entries = by_first.get(t1)
            if not entries:
                continue
            base = math.exp(lp)
            for sid, tail in entries:
                m = base
                for off, t in enumerate(tail, start=1):
                    q = p + off
                    if q >= n:
                        m = 0.0
                        break
                    lq = candidates(tokens, logs, alts, q).get(t)
                    if lq is None or not math.isfinite(lq):
                        m = 0.0
                        break
                    m *= math.exp(lq)
                    if m == 0.0:
                        break
                if m > 0.0:
                    mass[sid] = mass.get(sid, 0.0) + m

        # 2) the true word, exactly (this is what echo buys us)
        start_char, end_char = word_spans[k]
        pw = word_mass(tokens, logs, alts, tok_ends, start_char, end_char)
        sid_true = None if actual is None else int(actual[k])
        if sid_true is not None and sid_true >= 0:
            actual_out[k] = sid_true
            if pw is not None:
                actual_p_out[k] = pw
                # 3) inject it when the truncated list missed it
                if inject_actual and sid_true not in mass and pw > 0.0:
                    mass[sid_true] = pw
                    stats["injected"] += 1

        if not mass:
            stats["empty_after"] += 1
            continue
        raw_total = sum(mass.values())
        if raw_total < min_mass:
            stats["empty_after"] += 1
            continue
        if temperature != 1.0:
            inv = 1.0 / float(temperature)
            mass = {sid: (v ** inv if v > 0.0 else 0.0) for sid, v in mass.items()}
        ranked = sorted(mass.items(), key=lambda kv: (-kv[1], kv[0]))[:topk]
        total = sum(v for _, v in ranked)
        if total <= 0.0 or not math.isfinite(total):
            stats["empty_after"] += 1
            continue
        mass_out[k] = raw_total
        for i, (sid, v) in enumerate(ranked):
            ids[k, i] = sid
            probs[k, i] = v / total
        stats["filled"] += 1
        stats["mass_sum"] += total
    return ids, probs, mass_out, actual_out, actual_p_out, stats


def sentence_audit(tokens, logs, alts, prompt_tokens):
    """Actual-token NLL, top-1 share and candidate width over a prompt."""
    n = min(prompt_tokens, len(tokens))
    rows, total, top1, widths, missing = 0, 0.0, 0, [], 0
    for p in range(1, n):
        lp = logs[p] if p < len(logs) else None
        if lp is None or not math.isfinite(lp):
            missing += 1
            continue
        cand = candidates(tokens, logs, alts, p)
        widths.append(len(cand))
        rows += 1
        total += -lp
        best = max(cand.values(), default=None)
        if best is not None and abs(best - lp) < 1e-9:
            top1 += 1
    return {
        "rows": rows,
        "missing": missing,
        "mean_nll": (total / rows) if rows else None,
        "top1": (top1 / rows) if rows else None,
        "width_mean": (sum(widths) / len(widths)) if widths else None,
        "width_min": min(widths) if widths else None,
    }


# ----------------------------------------------------------------- weights
def row_weights(mode, mass, counts, piece, topk, piece_weight=0.1, word_weight=1.0):
    """Per-row KD weight, the array `train_v2.py distill_weight=` consumes.

    * `mass`  — the teacher probability the row actually captured. The
      principled choice: a row whose candidates explain 40 % of the teacher's
      distribution should not weigh like one that explains 99 %. This is the
      "true per-row tail" signal `plans/student-quality-audit.md:251-255`
      asks for.
    * `cand`  — `filled candidates / topk`, what `soft_mask.py build
      --weight=cand` does (candidate-count discount).
    * `piece` — `piece_weight` on rows whose word is spelled in pieces,
      `word_weight` elsewhere, `0` on empty rows; this reproduces
      `build_kd_weight.py` (student v2 default: 0.1 / 1.0 / 0).
    """
    mass = np.asarray(mass, dtype=np.float32)
    counts = np.asarray(counts, dtype=np.float32)
    piece = np.asarray(piece, dtype=bool)
    empty = mass <= 0.0
    if mode == "mass":
        w = mass.astype(np.float32)
    elif mode == "cand":
        w = np.clip(counts / float(max(1, topk)), 0.0, 1.0).astype(np.float32)
    elif mode == "piece":
        w = np.where(piece, piece_weight, word_weight).astype(np.float32)
    else:
        raise ValueError(f"unknown weight mode {mode!r}")
    w[empty] = 0.0
    return w


# ------------------------------------------------------------ audit sibling
def save_audit(path, mass, actual, actual_p, weight=None, piece=None, extra=None):
    """Write the per-row diagnostics next to a soft npz (atomic)."""
    tmp = path + ".tmp.npz"
    payload = {
        "mass": np.asarray(mass, dtype=np.float16),
        "actual": np.asarray(actual, dtype=np.int32),
        "actual_p": np.asarray(actual_p, dtype=np.float16),
    }
    if weight is not None:
        payload["weight"] = np.asarray(weight, dtype=np.float32)
    if piece is not None:
        payload["piece"] = np.asarray(piece, dtype=np.uint8)
    for key, arr in (extra or {}).items():
        payload[key] = arr
    with open(tmp, "wb") as f:
        np.savez(f, **payload)
    os.replace(tmp, path)


def load_audit(path):
    z = np.load(path)
    return {k: z[k] for k in z.files}


# ------------------------------------------------------------------ self-test
class _Fake:
    """Minimal mapping stand-in: word -> (sid, [first token, tail tokens])."""


def _mapping_from(d):
    """`{sid: [token strings]}` -> `by_first` shaped like index_mapping's."""
    by_first = {}
    for sid, seq in d.items():
        by_first.setdefault(seq[0], []).append((sid, list(seq[1:])))
    return by_first


def self_test():
    # Prompt " ich will hause": words end at chars 4, 9, 15.
    tokens = [" ich", " will", " hause"]
    word_ends = [4, 9, 15]
    assert token_char_ends(tokens, 3) == [4, 9, 15]
    assert spans(word_ends) == [(0, 4), (4, 9), (9, 15)]
    assert vc.word_positions(word_ends, token_char_ends(tokens, 3)) == [0, 1, 2]

    lp = math.log
    by_first = _mapping_from({10: [" ich"], 11: [" will"], 12: [" hause"],
                              13: [" fahren"]})
    logs = [None, lp(0.50), lp(0.10)]
    alts = [{}, {" ich": lp(0.02)}, {" will": lp(0.30), " fahren": lp(0.05)}]
    # Row k reads the distribution before word k: row 1 -> p=1, row 2 -> p=2.
    ids, probs, mass, act, ap, st = rows_from_sentence(
        tokens, logs, alts, 3, word_ends, by_first, topk=4, actual=[-1, -1, 12])
    assert ids[0].tolist() == [0, 0, 0, 0] and float(probs[0].sum()) == 0.0
    # row 1: candidates {ich: .02, will: .50} -> 11 then 10
    assert ids[1].tolist() == [11, 10, 0, 0], ids[1]
    assert abs(float(probs[1, 0]) - 0.50 / 0.52) < 1e-2, probs[1]
    assert abs(float(mass[1]) - 0.52) < 1e-3, mass[1]
    # row 2: {will: .30, hause: .10 (actual), fahren: .05} -> sorted, renorm
    assert ids[2].tolist() == [11, 12, 13, 0], ids[2]
    assert abs(float(probs[2, 0]) - 0.30 / 0.45) < 1e-2, probs[2]
    assert abs(float(mass[2]) - 0.45) < 1e-3, mass[2]
    assert st["filled"] == 2 and st["width_min"] == 2, st
    # the true word's exact probability, from its own token's logprob
    assert act[2] == 12 and abs(float(ap[2]) - 0.10) < 1e-6, (act[2], ap[2])

    # Injection: when the mapping's tokenization differs from the stream, the
    # multi-token chain yields nothing and the exact span product is used.
    by_first_split = _mapping_from({11: [" will"], 12: [" haus", "e"]})
    ids2, probs2, mass2, act2, ap2, st2 = rows_from_sentence(
        tokens, logs, alts, 3, word_ends, by_first_split, topk=4, actual=[-1, -1, 12])
    assert st2["injected"] == 1, st2
    row = dict(zip(ids2[2].tolist(), probs2[2].astype(float)))
    assert 12 in row, row
    assert abs(float(mass2[2]) - (0.30 + 0.10)) < 1e-3, mass2[2]

    # Multi-token word straight from the actual stream: p(geh)·p(en|geh).
    tokens3 = [" ich", " geh", "en"]
    logs3 = [None, lp(0.20), lp(0.50)]
    by_first3 = _mapping_from({20: [" geh", "en"]})
    ids3, probs3, mass3, _, _, st3 = rows_from_sentence(
        tokens3, logs3, [{}, {}, {}], 3, [4, 10], by_first3, topk=4,
        actual=[-1, 20], inject_actual=False)
    assert ids3[1, 0] == 20, ids3[1]
    assert abs(float(probs3[1, 0]) - 1.0) < 1e-3
    assert abs(float(mass3[1]) - 0.20 * 0.50) < 1e-3, mass3[1]

    # Unaligned word boundary -> that row stays empty, exactly like vLLM's
    # rule (word 1 now ends at char 10, no token ends there).
    ids4, probs4, _, _, _, st4 = rows_from_sentence(
        tokens, logs, alts, 3, [4, 10, 15], by_first, topk=4, actual=None)
    assert float(probs4[2].sum()) == 0.0 and st4["skipped"] >= 1, st4
    assert float(probs4[1].sum()) > 0.0, st4

    # Audit: rank from the logprob, not from an unordered dict's position.
    a = sentence_audit([" a", " b", " c"], [None, lp(0.9), lp(0.2)],
                       [{}, {" a": lp(0.05), " b": lp(0.9)}, {" z": lp(0.7)}], 3)
    assert a["rows"] == 2 and abs(a["top1"] - 0.5) < 1e-9, a
    assert a["width_min"] == 2, a

    # A NaN alternative is dropped, never used.
    c = candidates(["x", "y"], [None, lp(0.5)], [{}, {" a": float("nan"), " b": -1.0}], 1)
    assert c == {"y": lp(0.5), " b": -1.0}, c

    print("self-test ok: rows, mass, injection, multi-token chain, alignment, audit")


def main():
    if "--self-test" in sys.argv[1:]:
        self_test()
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
