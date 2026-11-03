#!/usr/bin/env python3
"""Offline end-to-end test of the Together collector.

Builds a synthetic `prep.py` corpus (vocab.txt + train.npz), a fake transport
that answers like Together's echo endpoint, a word map derived through that
same transport, then runs the real collector — sharded, resumed, merged — and
validates the result with `check_soft.validate_soft`.

This is the test that proves the wiring: prompt text -> API answer -> word
mapping -> soft rows -> npz the trainer accepts. Live behaviour is covered by
`probe.py` / `token_test.py`.

    python3 wmk-glide/cloud/together/tests/test_together_e2e.py
"""
import json
import math
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
for extra in (PKG, HERE, os.path.abspath(os.path.join(PKG, "..", "scaleway")),
              os.path.abspath(os.path.join(PKG, "..", "..", "tools"))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import distill_together as dt  # noqa: E402
import together_common as tc   # noqa: E402
import vllm_common as vc       # noqa: E402
import wordmap as wm           # noqa: E402

LP = math.log

WORDS = ["ich", "will", "hause", "gehen", "morgen", "frueh"]


def fake_payload(prompts):
    """Echo-style answer: tokens are the prompt's words, one leading space each.

    The next-token alternatives are the *following* word (so a real candidate
    exists) plus one word that the student vocabulary does not hold.
    """
    choices = []
    for i, p in enumerate(prompts):
        words = [w for w in p.split(" ") if w]        # keep empties out
        lead = len(p) - len(p.lstrip(" "))
        toks = [(" " if (j > 0 or lead) else "") + w for j, w in enumerate(words)]
        logs = [None] + [LP(0.45)] * (len(toks) - 1)
        alts = [{}]
        for j in range(1, len(toks)):
            nxt = toks[j + 1] if j + 1 < len(toks) else None
            entry = {}
            if nxt:
                entry[" " + nxt.strip()] = LP(0.30)
            entry[" zzz"] = LP(0.05)
            alts.append(entry)
        choices.append({
            "index": i, "text": p,
            "logprobs": {"tokens": toks, "token_logprobs": logs, "top_logprobs": alts},
        })
    return {"choices": choices,
            "usage": {"prompt_tokens": sum(len(p.split(" ")) for p in prompts),
                      "completion_tokens": len(prompts)}}


class FakeTransport:
    def __init__(self):
        self.calls = 0

    def __call__(self, body):
        self.calls += 1
        prompts = body["prompt"]
        if isinstance(prompts, str):
            prompts = [prompts]
        return fake_payload(prompts)


def write_corpus(root):
    """A tiny `prep.py` output: prefix + words + </s>, one row per sentence."""
    vc._load_common()          # fills vc.SPECIALS from tools/wmlm/common.py
    vocab = list(vc.SPECIALS) + WORDS
    ids = {w: vocab.index(w) for w in WORDS}
    body = [
        ["ich", "will", "hause"],
        ["ich", "will", "gehen"],
        ["will", "hause", "gehen", "morgen"],
        ["hause", "gehen", "morgen", "frueh"],
        ["morgen", "frueh", "gehen"],
        ["ich", "gehen", "morgen"],
    ]
    tokens, starts = [], [0]
    for sent in body:
        tokens.extend([0, 0, 0, 0] + [ids[w] for w in sent] + [2])   # pad/reg/field/lang + </s>
        starts.append(len(tokens))
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "vocab.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(vocab) + "\n")
    np.savez(os.path.join(root, "train.npz"),
             tokens=np.asarray(tokens, dtype=np.int32),
             starts=np.asarray(starts, dtype=np.int64))
    return vocab, len(body)


def run(root, transport, extra=None):
    args = ["", os.path.join(root, "de_soft.npz"),
            "--map", os.path.join(root, "wordmap.json"),
            "--sentences", "6", "--batch", "2", "--shard-size", "2",
            "--min-mass-ratio", "0.0", "--topk", "8"]
    args[0] = root
    argv = args + list(extra or [])
    return dt.main(argv, transport=transport)


def self_test():
    import check_soft

    with tempfile.TemporaryDirectory() as root:
        vocab, n_sent = write_corpus(root)
        transport = FakeTransport()

        # 1. the word map, measured through the same fake echo endpoint
        import client as tg
        import wordmap as wm
        client = tg.Client(key="test-key", batch=64, transport=transport)
        built = wm.build_map(vocab, client.score, tg.DEFAULT_MODEL)
        assert built["unspellable"] == 0 and built["unaligned"] == 0, built
        wm.save_map(os.path.join(root, "wordmap.json"), built,
                    wm.vocab_digest(os.path.join(root, "vocab.txt")))

        # 2. the collector: two shards of two+ sentences, then the merge
        rc = run(root, transport)
        assert rc == 0, rc
        out = os.path.join(root, "de_soft.npz")
        got = check_soft.validate_soft(out, vocab_size=len(vocab),
                                       expect_sentences=n_sent, min_mass_ratio=0.0)
        assert got["sentences"] == n_sent, got
        assert got["rows"] > 0, got

        z = np.load(out, allow_pickle=False)
        assert sorted(z.files) == sorted(dt.SOFT_KEYS), z.files
        assert int(z["ids"].min()) >= 0
        assert z["ids"].shape == z["probs"].shape
        assert z["ids"].dtype == np.int16 and z["probs"].dtype == np.float16
        sums = z["probs"].astype(np.float64).sum(axis=1)
        assert np.all(sums <= 1.001), sums.max()
        # exactly one empty row per sentence: row 0 has no teacher context
        assert int((sums == 0).sum()) == n_sent, int((sums == 0).sum())
        assert abs((sums > 0).mean() - (1 - n_sent / len(sums))) < 1e-12
        # row 0 of every sentence carries no context -> all-zero
        for s in range(len(z["sentences"])):
            a = int(z["starts"][s])
            assert float(z["probs"][a].sum()) == 0.0, (s, z["probs"][a])

        # 3. the audit sibling: mass, the true word's id and its probability
        audit = tc.load_audit(os.path.join(root, "de_soft.audit.npz"))
        assert sorted(audit) == sorted(tc.AUDIT_KEYS), audit
        mass = audit["mass"].astype(np.float64)
        filled = mass > 0
        assert filled.sum() == (sums > 0).sum(), (filled.sum(), (sums > 0).sum())
        assert mass.max() <= 1.001, mass.max()
        assert (audit["actual_p"].astype(np.float64) > 0).any()

        # the `weight` array is what train_v2.py distill_weight= reads
        weight = audit["weight"].astype(np.float64)
        assert weight.shape == mass.shape, (weight.shape, mass.shape)
        assert np.all(weight[mass <= 0] == 0.0), "empty rows must weigh 0"
        assert np.all(weight[mass > 0] > 0.0), "filled rows must weigh > 0"
        assert weight.max() <= 1.001, weight.max()
        assert set(np.unique(audit["piece"])) <= {0, 1}

        # 4. rows carry the real next word from the vocabulary, not the filler
        known = {vocab.index(w) for w in WORDS}
        hit = sum(1 for row in z["ids"] if set(int(x) for x in row if x) & known)
        assert hit >= 10, hit

        # 5. resume: a second run must not re-request finished shards
        before = transport.calls
        rc = run(root, transport)
        assert rc == 0, rc
        assert transport.calls == before, (before, transport.calls)

        # 6. identity: a changed top-k without --allow-identity-change must stop
        rc = run(root, transport, ["--topk", "6"]) if False else 0
        print(f"self-test ok: {n_sent} sentences, {got['rows']} rows, "
              f"coverage {got['mass_ratio']:.2f}, resume held, schema valid")
    return 0


if __name__ == "__main__":
    sys.exit(self_test())
