#!/usr/bin/env python3
"""Probe Chutes prompt-logprobs with automatic retries and a failure log.

Chutes serves Qwen3.8-27B-TEE through vLLM. Their OpenAPI lists
`prompt_logprobs: N` on `/v1/completions` and returns a `prompt_logprobs`
array per prompt token. That is what `tools/wmlm/distill.py` needs.

The endpoint has an intermittent vLLM/MTP bug: HTTP 400
"Out of range float values are not JSON compliant: nan" (vLLM #53488),
and it can also return HTTP 200 with wrong values. This probe therefore
retries transport/NaN/sparse responses with exponential backoff, validates
the returned distribution, and writes every final failure to a JSONL file
so a later pass can retry only those prompts.

Usage:
    python3 chutes_echo_probe.py --key-file ~/.chutes.key
    python3 chutes_echo_probe.py --sentences 100 --attempts 5
    python3 chutes_echo_probe.py --prompt-file ../artifacts/data/heldout.tsv --sentences 100
    python3 chutes_echo_probe.py --failures-out failures.jsonl
    python3 chutes_echo_probe.py --dry-run

Exit codes:
    0  every prompt returned a usable, wide top-N distribution
    1  at least one prompt failed after all attempts (see --failures-out)
    2  no key (nothing sent)
    3  all requests failed, or a fatal auth/budget/request error
"""
import argparse
import json
import math
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://llm.chutes.ai/v1/completions"
MODEL = "Qwen/Qwen3.8-27B-TEE"
DEFAULT_PROMPTS = [
    "ich will nach Hause gehen und morgen früh",
    "der Zug fährt um acht Uhr vom Hauptbahnhof ab",
    "kannst du mir bitte das Fenster öffnen",
    "wir treffen uns später in der Stadt",
    "das Wetter soll am Wochenende besser werden",
    "er hat den ganzen Tag an dem Projekt gearbeitet",
    "die Kinder spielen im Garten mit dem Ball",
    "ich habe gestern ein interessantes Buch gelesen",
    "bitte schick mir die Datei bis heute Abend",
    "sie wohnt seit drei Jahren in dieser Straße",
    "der Arzt hat mir eine Tablette verschrieben",
    "wir müssen noch Milch und Brot kaufen",
    "das Konzert beginnt leider erst um neun",
    "er kann sehr gut Deutsch und Englisch sprechen",
    "die Firma sucht einen neuen Mitarbeiter",
    "ich freue mich schon auf den Urlaub",
    "der Film war besser als ich erwartet hatte",
    "kannst du das bitte noch einmal erklären",
    "wir haben den Zug leider verpasst",
    "sie hat mir gestern eine Nachricht geschickt",
]


def read_prompts(path, count):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            if path.endswith(".tsv"):
                parts = line.split("\t")
                # heldout.tsv: idx / word_idx / word / sentence
                out.append(parts[3] if len(parts) >= 4 else parts[-1])
            elif path.endswith(".jsonl"):
                try:
                    out.append(json.loads(line)["sentence"])
                except (ValueError, KeyError):
                    continue
            else:
                out.append(line)
            if len(out) >= count:
                break
    return out


def build_request(model, prompt, top_n):
    return {
        "model": model,
        "prompt": prompt,
        "max_tokens": 1,
        "temperature": 0,
        "stream": False,
        "prompt_logprobs": top_n,
    }


def request(url, key, body, timeout):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "wmk-glide-chutes-probe/2",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def validate(resp, min_top, max_nll):
    """Return (stats, None) or (None, reason).

    Position 0 is None by design and is skipped. A short/non-finite/sparse
    distribution is treated as a retryable server failure. If the response
    carries prompt_token_ids, the mean NLL of the actual tokens is checked
    too; that catches gross silent corruption from the MTP bug.
    """
    choice = (resp.get("choices") or [{}])[0]
    pl = choice.get("prompt_logprobs")
    if pl is None:
        pl = resp.get("prompt_logprobs")
    if not pl or not isinstance(pl, list):
        return None, "missing prompt_logprobs"

    ids = choice.get("prompt_token_ids") or resp.get("prompt_token_ids") or []
    if ids and len(ids) != len(pl):
        return None, f"token id length {len(ids)} != logprob length {len(pl)}"
    widths, nll = [], []
    for i, pos in enumerate(pl):
        if pos is None:
            continue
        if not isinstance(pos, dict) or not pos:
            return None, f"bad position {i}"
        widths.append(len(pos))
        for info in pos.values():
            lp = info.get("logprob") if isinstance(info, dict) else None
            if not isinstance(lp, (int, float)) or not math.isfinite(lp):
                return None, f"non-finite logprob at {i}"
        if ids and i < len(ids):
            info = pos.get(str(ids[i]))
            if not isinstance(info, dict):
                return None, f"actual token missing at {i}"
            if isinstance(info, dict):
                lp = info.get("logprob")
                if isinstance(lp, (int, float)) and math.isfinite(lp):
                    nll.append(-lp)

    if not widths:
        return None, "no scored positions"
    if min(widths) < min_top:
        return None, f"width {min(widths)} < {min_top}"
    mean_nll = sum(nll) / len(nll) if nll else None
    if max_nll > 0 and mean_nll is not None and mean_nll > max_nll:
        return None, f"mean NLL {mean_nll:.2f} > {max_nll}"
    return {"widths": widths, "nll": nll, "mean_nll": mean_nll}, None


def classify_http(e):
    """Return (retryable, detail). Reads the body once."""
    body = e.read().decode("utf-8", "replace")
    retryable = e.code in (408, 409, 425, 429, 500, 502, 503, 504)
    low = body.lower()
    if e.code == 400 and ("nan" in low or "out of range float" in low):
        retryable = True
    return retryable, f"HTTP {e.code}: {body[:300]}"


def fetch_one(url, key, model, prompt, top_n, timeout, attempts,
              min_top, max_nll, backoff, backoff_max, jitter, index):
    """Return (attempts_used, stats, None) or (attempts_used, None, error)."""
    last = "unknown"
    for attempt in range(1, attempts + 1):
        t0 = time.time()
        try:
            resp = request(url, key, build_request(model, prompt, top_n), timeout)
            stats, reason = validate(resp, min_top, max_nll)
            if reason is None:
                stats["latency"] = time.time() - t0
                return attempt, stats, None
            last = f"invalid response: {reason}"
            retryable = True
        except urllib.error.HTTPError as e:
            retryable, last = classify_http(e)
        except Exception as e:
            retryable, last = True, f"{type(e).__name__}: {e}"

        print(f"{index:5d} attempt {attempt}/{attempts}: {last}", file=sys.stderr)
        if not retryable:
            return attempt, None, f"fatal {last}"
        if attempt < attempts:
            delay = min(backoff_max, backoff * (2 ** (attempt - 1)))
            delay += random.random() * jitter * delay
            time.sleep(delay)
    return attempts, None, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-file", default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--url", default=ENDPOINT)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--min-top", type=int, default=10)
    ap.add_argument("--max-nll", type=float, default=12.0,
                    help="Reject a row whose mean actual-token NLL is above this; 0 disables")
    ap.add_argument("--attempts", type=int, default=5)
    ap.add_argument("--backoff", type=float, default=0.5)
    ap.add_argument("--backoff-max", type=float, default=20.0)
    ap.add_argument("--jitter", type=float, default=0.25)
    ap.add_argument("--sentences", type=int, default=3)
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--failures-out", default=None,
                    help="Write final failures as JSONL for a later retry pass")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prompts = (read_prompts(args.prompt_file, args.sentences)
               if args.prompt_file else DEFAULT_PROMPTS[:args.sentences])
    if not prompts:
        print("no prompts", file=sys.stderr)
        return 2

    body = build_request(args.model, prompts[0], args.top_n)
    if args.dry_run:
        print(json.dumps({"url": args.url, "body": body}, ensure_ascii=False, indent=2))
        return 0

    key = None
    if args.key_file:
        with open(args.key_file, encoding="utf-8") as f:
            key = f.readline().strip()
    key = key or os.environ.get("CHUTES_API_KEY")
    if not key:
        print("no CHUTES_API_KEY / --key-file; nothing sent", file=sys.stderr)
        return 2

    all_widths, latencies, failures, attempt_hist = [], [], [], {}
    first_try = retried = fatal = 0

    for i, prompt in enumerate(prompts, 1):
        used, stats, error = fetch_one(
            args.url, key, args.model, prompt, args.top_n, args.timeout,
            args.attempts, args.min_top, args.max_nll, args.backoff,
            args.backoff_max, args.jitter, i,
        )
        attempt_hist[used] = attempt_hist.get(used, 0) + 1
        if error:
            fatal += 1
            failures.append({"index": i, "prompt": prompt, "attempts": used, "error": error})
            print(f"{i:5d} FAIL after {used}: {error}", file=sys.stderr)
            continue
        if used == 1:
            first_try += 1
        else:
            retried += 1
        all_widths.extend(stats["widths"])
        latencies.append(stats["latency"])
        mean_nll = stats["mean_nll"]
        nll_txt = f" nll={mean_nll:.2f}" if mean_nll is not None else ""
        print(f"{i:5d} OK attempt={used} tokens={len(stats['widths'])} "
              f"width_min={min(stats['widths'])} width_med={statistics.median(stats['widths']):.1f}"
              f"{nll_txt} lat={stats['latency']:.2f}s")

    if args.failures_out and failures:
        with open(args.failures_out, "w", encoding="utf-8") as f:
            for row in failures:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    ok = all_widths and min(all_widths) >= args.min_top
    print()
    print(f"model={args.model} prompts={len(prompts)} ok={len(prompts)-len(failures)} "
          f"first_try={first_try} retried={retried} failed={len(failures)}")
    print(f"positions={len(all_widths)} min={min(all_widths) if all_widths else 0} "
          f"median={statistics.median(all_widths) if all_widths else 0:.1f} "
          f"max={max(all_widths) if all_widths else 0} "
          f"lat_med={statistics.median(latencies) if latencies else 0:.2f}s "
          f"attempts={dict(sorted(attempt_hist.items()))}")
    if failures and args.failures_out:
        print(f"failures written to {args.failures_out}")
    if failures:
        for row in failures[:10]:
            print(f"  #{row['index']} after {row['attempts']}: {row['error']}")
        return 3 if len(failures) == len(prompts) else 1
    if not ok:
        print(f"NOT USABLE: need width >= {args.min_top} at every position", file=sys.stderr)
        return 1
    print(f"USABLE: prompt_logprobs width >= {args.min_top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
