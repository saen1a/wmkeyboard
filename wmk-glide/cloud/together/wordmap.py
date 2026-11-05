#!/usr/bin/env python3
"""Build the teacher-token -> student-word map from the API itself.

`distill_together.py` needs to know *which teacher tokens spell which student
word*, and it needs the answer for **Together's** tokenizer, not for a
locally installed one: a tokenizer version, a normalisation flag or a
`add_prefix_space` difference silently produces a map that matches nothing and
starts zeroing rows. So the map is measured instead of derived:

    prompt " hause"  ->  tokens [" haus", "e"]   (echoed, with logprobs)

One array request per 1000 forms makes this ~2 requests per 1000 words, i.e.
about a second and a few cents for a 32k vocabulary.

Output (`--out`): JSON, keys

    model, vocab_sha256, forms, words, by_first
    by_first: {token: [[student id, [tail tokens...]], ...]}

which is exactly `vllm_common.index_mapping`'s structure with token strings
instead of ids. `distill_together.py --map` consumes it; `--self-test` checks
the builder on a fake client without touching the network.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for extra in (HERE, os.path.abspath(os.path.join(HERE, "..", "scaleway"))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import client as tg  # noqa: E402
import vllm_common as vc  # noqa: E402


def _ensure():
    """`vllm_common.SPECIALS` is filled lazily from tools/wmlm/common.py."""
    vc._load_common()  # noqa: SLF001 - the module's documented bootstrap


def forms_for(vocab):
    """`[(student id, " form"), ...]` for every word the teacher could spell.

    Same exclusions as `vllm_common.student_to_teacher`: the 16 specials and
    the piece markers are not whole words.
    """
    _ensure()
    out = []
    for sid, w in enumerate(vocab):
        if sid < len(vc.SPECIALS) or w.startswith(vc.START) or w.startswith(vc.CONT):
            continue
        if not w:
            continue
        for form in sorted({w, w.capitalize()}):
            out.append((sid, " " + form))
    return out


def build_map(vocab, score, model):
    """`{"by_first": ..., "forms": n, "unspellable": n}` from a scoring callable.

    `score(prompts) -> list[Choice]`; the returned map only keeps forms whose
    echoed tokens reproduce the prompt exactly (an alignment guard: a
    response that re-tokenises or trims whitespace must never become a map).
    """
    pairs = forms_for(vocab)
    prompts = [p for _, p in pairs]
    answers = score(prompts) if prompts else []
    if len(answers) != len(prompts):
        raise SystemExit(f"word map: {len(answers)} answers for {len(prompts)} forms")
    by_first, unspellable, unaligned = {}, 0, 0
    for (sid, form), ch in zip(pairs, answers):
        n = ch.prompt_tokens
        toks = ch.tokens[:n]
        if not toks or "".join(toks) != form:
            unaligned += 1
            continue
        if any(not t for t in toks):
            unspellable += 1
            continue
        by_first.setdefault(toks[0], []).append([sid, toks[1:]])
    return {"by_first": by_first, "forms": len(pairs),
            "unspellable": unspellable, "unaligned": unaligned, "model": model}


def save_map(path, built, vocab_sha256):
    payload = dict(built)
    payload["vocab_sha256"] = vocab_sha256
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def load_map(path):
    """`(by_first, meta)` with the JSON lists turned into the shapes the
    target builder expects."""
    with open(path, encoding="utf-8") as f:
        z = json.load(f)
    by_first = {tok: [(int(sid), list(tail)) for sid, tail in entries]
                for tok, entries in z["by_first"].items()}
    meta = {k: v for k, v in z.items() if k != "by_first"}
    return by_first, meta


def vocab_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ------------------------------------------------------------------ self-test
def self_test():
    _ensure()
    vocab = list(vc.SPECIALS) + ["ich", "hause", "\u2581hau", "##se"]

    class _Ch:
        def __init__(self, toks):
            self.tokens = toks
            self.prompt_tokens = len(toks)

    def score(prompts):
        out = []
        for p in prompts:
            body = p[1:]                       # drop the leading space
            if body == "ich":
                out.append(_Ch([" ich"]))
            elif body == "hause":
                out.append(_Ch([" haus", "e"]))
            elif body == "Hause":
                out.append(_Ch([" Hause"]))
            else:
                out.append(_Ch(["?"]))         # does not reproduce the prompt
        return out

    got = build_map(vocab, score, "fake")
    och, hause = vocab.index("ich"), vocab.index("hause")
    assert got["by_first"][" ich"] == [[och, []]], got["by_first"]
    assert got["by_first"][" haus"] == [[hause, ["e"]]], got["by_first"]
    assert got["by_first"][" Hause"] == [[hause, []]]
    assert got["forms"] >= 3
    # specials and pieces never appear as forms
    assert not any(t.startswith(vc.START) or t.startswith(vc.CONT)
                   for t in got["by_first"])
    assert got["unaligned"] >= 0

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "map.json")
        save_map(path, got, "deadbeef")
        by_first, meta = load_map(path)
        assert by_first[" haus"] == [(hause, ["e"])], by_first[" haus"]
        assert meta["vocab_sha256"] == "deadbeef"
        assert meta["model"] == "fake"
    print("self-test ok: forms, mapping, alignment guard, save/load")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_dir", nargs="?", help="prep.py output dir (vocab.txt)")
    ap.add_argument("--out", help="word map JSON to write")
    ap.add_argument("--model", default=tg.DEFAULT_MODEL)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        self_test()
        return 0
    if not a.data_dir or not a.out:
        ap.error("data_dir and --out are required unless --self-test")

    vocab, _, _ = vc.load_corpus(a.data_dir)
    client = tg.Client(model=a.model, key_file=a.key_file, batch=a.batch)
    built = build_map(vocab, client.score, a.model)
    save_map(a.out, built, vocab_digest(os.path.join(a.data_dir, "vocab.txt")))
    print(json.dumps({k: v for k, v in built.items() if k != "by_first"},
                     ensure_ascii=False))
    print(f"wrote {a.out}: {len(built['by_first'])} first tokens, "
          f"cost ≈ ${client.cost_usd(price_in_for(a.model)):.4f}", file=sys.stderr)
    return 0


def price_in_for(model):
    """Input price per 1M tokens (wmk-glide/kb-inference-providers.md §1.7)."""
    return {"Qwen/Qwen3.5-9B": 0.17, "openai/gpt-oss-120b": 0.15}.get(model, 0.20)


if __name__ == "__main__":
    sys.exit(main())
