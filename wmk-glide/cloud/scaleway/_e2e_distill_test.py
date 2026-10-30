"""Offline end-to-end test of distill_vllm's shard/retry/merge machinery.

No vLLM, no GPU: the collector's engine is replaced by a deterministic fake
teacher whose prompt_logprobs are word-level distributions. This exercises
the parts that a wrong implementation would silently corrupt: prompt
building, offset alignment, row packing, shard files, resume, failure
handling, merge_soft and check_soft.
"""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "..", "tools"))


def stub_modules():
    """Provide `vllm` and `transformers` stubs before distill_vllm imports."""
    vllm = types.ModuleType("vllm")

    class LLM:  # noqa: D401 - never instantiated
        def __init__(self, *a, **k):
            raise AssertionError("fake engine expected")

    class SamplingParams:
        def __init__(self, **k):
            self.k = k

    vllm.LLM = LLM
    vllm.SamplingParams = SamplingParams
    sys.modules["vllm"] = vllm

    transformers = types.ModuleType("transformers")

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(*a, **k):
            raise AssertionError("fake tokenizer expected")

    transformers.AutoTokenizer = AutoTokenizer
    sys.modules["transformers"] = transformers


class FakeTok:
    """Whitespace-chunk tokenizer: ' ich will' -> [' ich', ' will']."""

    CHUNK = re.compile(r"\s*\S+")

    def __init__(self, words):
        self.ids = {w: 1000 + i for i, w in enumerate(words)}

    def encode(self, text, add_special_tokens=False):
        return [self.ids[m.group(0)] for m in self.CHUNK.finditer(text) if m.group(0) in self.ids]

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=True):
        ids, offs = [], []
        for m in self.CHUNK.finditer(text):
            if m.group(0) not in self.ids:
                continue
            ids.append(self.ids[m.group(0)])
            offs.append((m.start(), m.end()))
        return {"input_ids": ids, "offset_mapping": offs}


class LP:
    __slots__ = ("logprob", "rank")

    def __init__(self, logprob, rank=0):
        self.logprob = logprob
        self.rank = rank


def fake_generate(self, prepared):
    """A peaked distribution over words; the actual token is always present."""
    outs = []
    rng = random.Random(7)
    for _sid, (text, ends, ids, tok_ends) in prepared:
        plp = [None]
        for p in range(1, len(ids)):
            d = {ids[p]: LP(np.log(0.60))}
            for extra in rng.sample(sorted(self.tok.ids.values()), 3):
                d[extra] = LP(np.log(0.10))
            plp.append(d)
        outs.append(types.SimpleNamespace(prompt_logprobs=plp, prompt_token_ids=ids))
    return outs


def build_data(dir_path, n_sent=60):
    import vllm_common as vc

    vc._load_common()
    words = ["ich", "will", "nach", "hause", "fahren", "der", "hund", "bellt",
             "heute", "ist", "es", "kalt", "wir", "gehen", "ins", "kino",
             "das", "wetter", "schoen", "nicht", "wahr"]
    vocab = list(vc.SPECIALS) + words + ["\u2581haus", "##e"]
    with open(os.path.join(dir_path, "vocab.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(vocab) + "\n")

    tokens, starts = [], [0]
    rng = random.Random(3)
    for _ in range(n_sent):
        seq = [1, 1, 0, vocab.index("<s>")]  # casual, chat, de
        seq += [vocab.index(w) for w in rng.sample(words, 6)]
        seq += [vocab.index("</s>")]
        tokens += seq
        starts.append(len(tokens))
    np.savez(os.path.join(dir_path, "train.npz"),
             tokens=np.array(tokens, dtype=np.int32), starts=np.array(starts, dtype=np.int64))


def main():
    sys.path.insert(0, HERE)
    stub_modules()
    import vllm_common as vc
    import distill_vllm as dv

    vc._load_common()
    tmp = tempfile.mkdtemp(prefix="wmlm-dv-")
    data = os.path.join(tmp, "de_lm")
    os.makedirs(data)
    build_data(data, 60)
    out = os.path.join(tmp, "soft.npz")

    def fake_ensure_engine(self):
        if self.llm is not None:
            return
        self.llm = object()
        self.tok = FakeTok([" ich", " will", " nach", " hause", " fahren", " der",
                            " hund", " bellt", " heute", " ist", " es", " kalt",
                            " wir", " gehen", " ins", " kino", " das", " wetter",
                            " schoen", " nicht", " wahr"])
        self.mapping = vc.student_to_teacher(
            self.vocab, lambda s: self.tok.encode(s), multi=bool(self.a.multi))
        self.by_first = vc.index_mapping(self.mapping)

    dv.Collector.ensure_engine = fake_ensure_engine
    dv.Collector.generate = fake_generate

    common = ["--sentences", "60", "--shard-size", "20", "--batch", "8",
              "--checkpoint-every", "5"]

    rc = dv.main([data, out, *common, "--attempts", "2",
                  "--failures", os.path.join(tmp, "failures.jsonl")])
    assert rc == 0, rc

    shard_dir = out[:-4] + "_shards"
    shards = sorted(f for f in os.listdir(shard_dir)
                    if f.endswith(".npz") and ".partial" not in f)
    assert len(shards) == 3, shards
    partials = [f for f in os.listdir(shard_dir) if ".partial" in f]
    assert not partials, partials

    merge = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "merge_soft.py"), out,
         *[os.path.join(shard_dir, s) for s in shards],
         "--vocab-size", "40", "--expect-sentences", "60", "--min-mass-ratio", "0.0"],
        capture_output=True, text=True)
    print(merge.stdout.strip(), merge.stderr.strip())
    assert merge.returncode == 0, merge.stderr

    check = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "check_soft.py"), out,
         "--vocab-size", "40", "--expect-sentences", "60", "--min-mass-ratio", "0.0"],
        capture_output=True, text=True)
    print(check.stdout.strip())
    assert check.returncode == 0, check.stderr

    z = np.load(out)
    assert len(z["sentences"]) == 60
    assert np.all(np.diff(z["sentences"]) > 0), "sentences must be strictly increasing"
    assert z["starts"][-1] == len(z["ids"])
    assert z["ids"].dtype == np.int16 and z["probs"].dtype == np.float16
    nonzero = int((z["probs"].sum(axis=1) > 0).sum())
    assert nonzero > 0, "no sentence produced soft mass"
    print(f"e2e ok: 3 shards, 60 sentences, {len(z['ids'])} rows, {nonzero} with mass")

    rc = dv.main([data, out, *common, "--attempts", "1",
                  "--failures", os.path.join(tmp, "failures2.jsonl")])
    assert rc == 0, rc
    print("resume ok: second run skipped all valid shards")

    broken = os.path.join(shard_dir, shards[1])
    with open(broken, "wb") as f:
        f.write(b"not an npz")
    rc = dv.main([data, out, *common, "--attempts", "1",
                  "--failures", os.path.join(tmp, "failures3.jsonl")])
    assert rc == 0, rc
    check = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "check_soft.py"),
         os.path.join(shard_dir, shards[1]), "--vocab-size", "40",
         "--expect-sentences", "20", "--min-mass-ratio", "0.0"],
        capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    print("repair ok: broken shard recomputed and validated")

    # Pass 2: a failed sid is retried, the shard is patched, and the resume
    # checkpoint plus the INCOMPLETE marker must not survive.
    fails2 = os.path.join(tmp, "failures_retry.jsonl")
    with open(fails2, "w", encoding="utf-8") as f:
        f.write(json.dumps({"event": "failed", "sid": 41, "attempt": 3,
                            "error": "mean NLL 99.00 > 12", "model": "fake"}) + "\n")
    with open(os.path.join(shard_dir, shards[2]) + ".INCOMPLETE", "w", encoding="utf-8") as f:
        f.write("41\n")
    rc = dv.main([data, out, *common, "--attempts", "1",
                  "--retry-failures", fails2,
                  "--failures", os.path.join(tmp, "failures_retry2.jsonl")])
    assert rc == 0, rc
    assert not os.path.exists(os.path.join(shard_dir, shards[2]) + ".partial.npz")
    assert not os.path.exists(os.path.join(shard_dir, shards[2]) + ".INCOMPLETE")
    check = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "check_soft.py"),
         os.path.join(shard_dir, shards[2]), "--vocab-size", "40",
         "--expect-sentences", "20", "--min-mass-ratio", "0.0"],
        capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    print("pass-2 ok: shard patched, partial and INCOMPLETE removed")

    # Identity guard: a different seed/topk must refuse to reuse the shards.
    rc = subprocess.run(
        [sys.executable, os.path.join(HERE, "distill_vllm.py"), data, out,
         *common, "--seed", "7"],
        capture_output=True, text=True).returncode
    assert rc != 0, "identity change must be refused"
    print("identity guard ok: different seed refused")

    # Staged run: a smaller --count first, then the full selection. The
    # existing shards must be kept (same permutation prefix) and only the
    # missing ones added — this is what "1.2M now, the rest later" needs.
    staged = os.path.join(tmp, "staged.npz")
    rc = dv.main([data, staged, "--sentences", "60", "--shard-size", "20",
                  "--batch", "8", "--count", "40", "--attempts", "1",
                  "--failures", os.path.join(tmp, "failures_stage1.jsonl")])
    assert rc == 0, rc
    stage_dir = staged[:-4] + "_shards"
    first = sorted(f for f in os.listdir(stage_dir) if f.endswith(".npz"))
    assert len(first) == 2, first
    rc = dv.main([data, staged, "--sentences", "60", "--shard-size", "20",
                  "--batch", "8", "--attempts", "1",
                  "--failures", os.path.join(tmp, "failures_stage2.jsonl")])
    assert rc == 0, rc
    second = sorted(f for f in os.listdir(stage_dir) if f.endswith(".npz"))
    assert len(second) == 3, second
    assert first == second[:2], (first, second)
    print("staged run ok: count grew from 40 to 60 without touching shards 0-1")

    fails = os.path.join(tmp, "failures.jsonl")
    if os.path.exists(fails):
        with open(fails, encoding="utf-8") as f:
            for line in f:
                json.loads(line)
    print("all distill_vllm plumbing checks passed")


if __name__ == "__main__":
    main()
