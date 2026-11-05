#!/usr/bin/env python3
"""Compare Together models as teacher candidates on the same German sentences.

Answers the only question that matters before a corpus pass: *which* of the
available serverless models gives a usable prompt distribution for our
word-level student — and how good is that distribution.

For every model it measures, on the 200 sentences the earlier local 4B/9B/27B
A/B used (`wmk-glide/artifacts/out/ab_sentences.tsv`):

| metric | why |
|---|---|
| `ok` / error | does `/v1/completions` + `echo` + `logprobs` work at all for this model family |
| `width_*` | alternatives per position (Together caps at 5; 0 means no top sets) |
| `echo_aligned` | the response reproduces the prompt (misalignment would silently shift every row) |
| `mean_nll` | teacher quality on our corpus (lower is better) |
| `top1_argmax` | share of positions where the actual token is the teacher's argmax |
| `mass_mean` | probability the returned candidates carry per position |
| `word_rate` | share of the corpus' word types the model spells as **one** token — the mapping rate the student's KD depends on |
| `tokens_per_word` | mean tokens per word (multi-token words need the chain, and cost more) |

The numbers are directly comparable to `artifacts/out/ab_3way.json`
(local `Qwen3.5-4B-Base`, `Qwen3.5-9B-Base`, `Qwen3.8-27B-FP8`), which reports
`mean_nll`, `top1_mass` and `soft_rows` on the same file.

    python3 model_ab.py --models Qwen/Qwen3-4B-Base,Qwen/Qwen3.5-9B \\
        --out ../../artifacts/out/ab_together.json
    python3 model_ab.py --self-test
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for extra in (HERE, os.path.abspath(os.path.join(HERE, "..", "scaleway"))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import client as tg  # noqa: E402
import together_common as tc  # noqa: E402

DEFAULT_SENTENCES = os.path.abspath(os.path.join(
    HERE, "..", "..", "artifacts", "out", "ab_sentences.tsv"))

# Base models first: a distillation teacher should be as close to the raw
# distribution as possible, and Together types those as `language`.
DEFAULT_MODELS = [
    "Qwen/Qwen3-4B-Base",          # same family/size as the local reference teacher
    "Qwen/Qwen3-8B-Base",
    "Qwen/Qwen3-14B-Base",
    "Qwen/Qwen3-30B-A3B-Base",
    "google/gemma-3-27b-pt",
    "Qwen/Qwen3.5-9B",             # post-trained, 5-wide confirmed
    "openai/gpt-oss-120b",
    "zai-org/GLM-5.3-Flash",
    "zai-org/GLM-4.5-Air-FP8",
    "deepseek-ai/DeepSeek-V4.1-Flash",
]

PRICE_IN = {"Qwen/Qwen3.5-9B": 0.17, "openai/gpt-oss-120b": 0.15,
            "zai-org/GLM-5.3-Flash": 0.15, "zai-org/GLM-4.5-Air-FP8": 0.20,
            "deepseek-ai/DeepSeek-V4.1-Flash": 0.30}


def load_sentences(path, limit=0):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            rows.append((parts[0], parts[2]))
    return rows[:limit] if limit else rows


def word_forms(sentences, max_words=0):
    """German words to spell-test, most frequent first."""
    counts = {}
    for _, text in sentences:
        for w in text.split():
            w = w.strip(".,!?;:\"'()").lower()
            if w and w.replace("-", "").isalpha():
                counts[w] = counts.get(w, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    words = [w for w, _ in ordered]
    return words[:max_words] if max_words else words


def score_model(client, sentences, words):
    """Token-level metrics + spell rate for one model. No exceptions escape."""
    out = {"sentences": len(sentences), "words": len(words)}
    t0 = time.time()
    prompts = [text for _, text in sentences]
    try:
        answers = client.score(prompts)
    except tg.TogetherError as e:
        out.update({"ok": False, "error": str(e)[:200]})
        return out

    rows = top1 = missing = misaligned = 0
    nll, masses, widths = 0.0, [], []
    classes = {}
    for (cls, text), ch in zip(sentences, answers):
        if "".join(ch.tokens[:ch.prompt_tokens]) != text:
            misaligned += 1
            continue
        st = tc.sentence_audit(ch.tokens, ch.logs, ch.alts, ch.prompt_tokens)
        c = classes.setdefault(cls, {"rows": 0, "nll": 0.0, "top1": 0.0})
        rows += st["rows"]
        missing += st["missing"]
        if st["mean_nll"] is not None:
            nll += st["mean_nll"] * st["rows"]
            c["nll"] += st["mean_nll"] * st["rows"]
        if st["top1"] is not None:
            top1 += st["top1"] * st["rows"]
            c["top1"] += st["top1"] * st["rows"]
        c["rows"] += st["rows"]
        for p in range(1, min(ch.prompt_tokens, len(ch.tokens))):
            cand = tc.candidates(ch.tokens, ch.logs, ch.alts, p)
            if cand:
                widths.append(len(cand))
                masses.append(sum(math.exp(v) for v in cand.values() if math.isfinite(v)))
    out.update({
        "ok": True,
        "positions": rows,
        "missing_logprobs": missing,
        "misaligned": misaligned,
        "mean_nll": (nll / rows) if rows else None,
        "top1_argmax": (top1 / rows) if rows else None,
        "width_mean": (sum(widths) / len(widths)) if widths else None,
        "width_min": min(widths) if widths else None,
        "mass_mean": (sum(masses) / len(masses)) if masses else None,
        "by_class": {k: {"rows": v["rows"],
                         "mean_nll": (v["nll"] / v["rows"]) if v["rows"] else None,
                         "top1_argmax": (v["top1"] / v["rows"]) if v["rows"] else None}
                     for k, v in classes.items()},
    })

    # spelling: how many words are a single teacher token
    single, total, tokens = 0, 0, 0
    if words:
        try:
            spells = client.score([" " + w for w in words])
        except tg.TogetherError as e:
            out["spell_error"] = str(e)[:200]
            spells = []
        for ch in spells:
            n = ch.prompt_tokens
            if n <= 0:
                continue
            total += 1
            tokens += n
            single += 1 if n == 1 else 0
    out["word_rate"] = (single / total) if total else None
    out["tokens_per_word"] = (tokens / total) if total else None
    out["seconds"] = round(time.time() - t0, 1)
    out["prompt_tokens"] = client.stats["prompt_tokens"]
    out["cost_usd"] = round(client.cost_usd(PRICE_IN.get(client.model, 0.30)), 5)
    return out


def fmt(v, digits=3):
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def table(results):
    head = ("| model | ok | width | NLL | top-1 | mass | word% | tok/word | $ |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for model, r in results.items():
        if not r.get("ok"):
            lines.append(f"| `{model}` | **no** | – | – | – | – | – | – | – |")
            continue
        lines.append(
            f"| `{model}` | yes | {fmt(r['width_min'])}–{fmt(r['width_mean'],1)} | "
            f"{fmt(r['mean_nll'])} | {fmt(r['top1_argmax'])} | {fmt(r['mass_mean'])} | "
            f"{fmt((r['word_rate'] or 0) * 100, 1)} | {fmt(r['tokens_per_word'], 2)} | "
            f"{fmt(r['cost_usd'], 2)} |")
    return head + "\n".join(lines) + "\n"


def self_test():
    class C:
        def __init__(self, model="fake"):
            self.model = model
            self.stats = {"prompt_tokens": 0}
        def score(self, prompts):     # noqa: D401 - stub
            raise tg.TogetherError("boom", 400)
        def cost_usd(self, p, o=0.0):
            return 0.0

    sents = [("chat", "ich will nach hause"), ("news", "der zug faellt aus")]
    r = score_model(C(), sents, ["hause"])
    assert r["ok"] is False and "boom" in r["error"], r

    class Good(C):
        def score(self, prompts):
            out = []
            for p in prompts:
                toks = [(" " if i else "") + w for i, w in enumerate(p.split())]
                out.append(type("Ch", (), {
                    "tokens": toks, "prompt_tokens": len(toks),
                    "logs": [None] + [math.log(0.5)] * (len(toks) - 1),
                    "alts": [{}] + [{" q": math.log(0.2)}] * (len(toks) - 1)})())
            return out
    r = score_model(Good(), sents, ["hause", "zug"])
    assert r["ok"] and r["positions"] == 6, r
    assert abs(r["mean_nll"] + math.log(0.5)) < 1e-9, r
    assert r["word_rate"] == 1.0 and r["tokens_per_word"] == 1.0, r
    assert set(r["by_class"]) == {"chat", "news"}, r
    assert "| model |" in table({"fake": r})
    print("self-test ok: error path, metrics, spell rate, table")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--sentences", default=DEFAULT_SENTENCES)
    ap.add_argument("--limit", type=int, default=0, help="0 = all 200")
    ap.add_argument("--max-words", type=int, default=0, help="0 = every word type")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        self_test()
        return 0

    sentences = load_sentences(a.sentences, a.limit)
    words = word_forms(sentences, a.max_words)
    print(f"{len(sentences)} sentences, {len(words)} word types", file=sys.stderr)
    results = {}
    for model in [m.strip() for m in a.models.split(",") if m.strip()]:
        print(f"… {model}", file=sys.stderr)
        try:
            client = tg.Client(model=model, key_file=a.key_file, batch=a.batch)
        except tg.TogetherError as e:
            results[model] = {"ok": False, "error": str(e)}
            continue
        results[model] = score_model(client, sentences, words)
        if not results[model].get("ok"):
            print(f"   {results[model].get('error', '')[:120]}", file=sys.stderr)

    payload = {"sentences_file": os.path.abspath(a.sentences),
               "sentences": len(sentences), "word_types": len(words),
               "models": results}
    print(table(results))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        tmp = a.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, a.out)
        print(f"wrote {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
