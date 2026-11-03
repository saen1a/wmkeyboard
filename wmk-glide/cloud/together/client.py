#!/usr/bin/env python3
"""Together AI completions client for prompt scoring (teacher pulls).

One job: turn a list of prompt strings into per-position teacher
distributions, batched, retried and validated. Everything the pipeline
needs to know about the endpoint is encoded here so that no script
re-discovers it:

* `logprobs` is **hard-capped at 5** (measured 2026-11-03: `logprobs: 20`
  is `HTTP 400 "Validation error: range [{max: 5, min: 0}]"`,
  `docs(wmk-glide)` commit a0c4de52d). `logprobs=0` still returns
  `token_logprobs` (the *actual* token's probability) but no alternatives.
* `echo: true` scores **every** prompt token, so `p(actual token)` is
  available for 100 % of positions even when it is outside the returned
  top-5. Candidates per position are therefore `top_logprobs ∪ {actual}`,
  at most 6.
* `top_logprobs` is an **unordered** JSON object (11 of 233 positions came
  back sorted). Rank must come from the logprob, never from list position.
* `prompt` may be an **array**: one `choices` entry per prompt, `index == i`,
  `choices[i].logprobs.tokens` are the tokens of prompt `i`. Measured
  throughput 498 sentences/s at 1000 prompts per request.
* With **array** prompts `usage.prompt_tokens` is the *sum over the batch*,
  not a per-choice count: for a batch of 16 it reported `3` after integer
  division in the first version of this client, which silently truncated
  every prompt. The per-choice prompt length is therefore measured from the
  response itself (`prompt_len`), and `usage` is only used for cost.
* `logit_bias` does **not** apply to prompt positions (151k of ~152k ids
  biased to -100 left prompt log-probs bit-identical), so no suppression
  trick can widen the support.
* `temperature`, `n`, `seed`, `top_p` do not change prompt log-probs.
* A default `urllib` User-Agent is rejected by Cloudflare with
  `HTTP 403 error code: 1010`; this client always sends its own.

No secret ever touches disk here: the key comes from `TOGETHER_API_KEY` or
from `--key-file` (read once, kept in memory).
"""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.together.xyz/v1/completions"
CHAT_ENDPOINT = "https://api.together.xyz/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
MAX_LOGPROBS = 5          # hard cap, see module docstring
USER_AGENT = "wmk-glide-together/2"

# Status codes worth another attempt. 400 (bad parameter), 401/403 (auth),
# 402 (no balance) and 404 (no such model) are permanent.
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class TogetherError(RuntimeError):
    """A request that will not succeed by retrying (or ran out of retries)."""

    def __init__(self, message, status=None, body=""):
        super().__init__(message)
        self.status = status
        self.body = body


def resolve_key(key=None, key_file=""):
    """`key` argument, else `TOGETHER_API_KEY`, else the first line of the file."""
    if key:
        return key.strip()
    env = os.environ.get("TOGETHER_API_KEY", "").strip()
    if env:
        return env
    if key_file:
        try:
            with open(key_file, encoding="utf-8") as f:
                got = f.readline().strip()
        except OSError as e:
            raise TogetherError(f"cannot read key file: {e}") from e
        if got:
            return got
        raise TogetherError(f"key file {key_file} is empty")
    raise TogetherError(
        "no API key: set TOGETHER_API_KEY or pass --key-file "
        "(keys stay outside the repo)"
    )


class Choice:
    """One prompt's answer, positions indexed the way the API indexes them.

    `tokens[p]` is the prompt's token at position p, `logs[p]` its logprob
    (`None` at p = 0), `alts[p]` the returned alternatives as
    `{token: logprob}`. `ci` is the request chunk this answer belongs to.
    """

    __slots__ = ("tokens", "logs", "alts", "prompt_tokens", "text", "ci")

    def __init__(self, tokens, logs, alts, prompt_tokens, text="", ci=""):
        self.tokens = tokens
        self.logs = logs
        self.alts = alts
        self.prompt_tokens = prompt_tokens
        self.text = text
        self.ci = ci

    def distribution(self, p):
        """Candidates at position p: returned alternatives plus the actual
        token. At most `MAX_LOGPROBS + 1` entries, unordered."""
        out = dict(self.alts[p]) if p < len(self.alts) else {}
        if p < len(self.tokens) and p < len(self.logs):
            lp = self.logs[p]
            if lp is not None:
                out[self.tokens[p]] = lp
        return out

    def __repr__(self):
        return (f"Choice(prompt_tokens={self.prompt_tokens}, "
                f"tokens={len(self.tokens)})")


def prompt_len(tokens, prompt):
    """How many of `tokens` are the prompt (echo shape), measured.

    The echoed tokens reconstruct the prompt character for character, so the
    prompt ends where the joined tokens first equal it. Returns `None` when
    the response does not reproduce the prompt (a hard error for the caller:
    a misaligned row is worse than a missing one).
    """
    acc = ""
    for i, t in enumerate(tokens):
        acc += t
        if acc == prompt:
            return i + 1
        if not prompt.startswith(acc):
            return None
    return None


def _parse_alts(entry):
    """`{token: logprob}` from either JSON shape, non-finite dropped."""
    out = {}
    if isinstance(entry, dict):
        items = entry.items()
    elif isinstance(entry, list):
        items = ((x.get("token"), x.get("logprob")) for x in entry if isinstance(x, dict))
    else:
        items = ()
    for tok, lp in items:
        if tok is None or not isinstance(lp, (int, float)):
            continue
        if lp != lp or lp in (float("inf"), float("-inf")):   # NaN/inf
            continue
        out[tok] = float(lp)
    return out


class Client:
    """Batched prompt scoring against `/v1/completions`.

    `transport(body_dict) -> dict` is the HTTP hop; tests replace it, so
    nothing here needs the network to be exercised.
    """

    def __init__(self, model=DEFAULT_MODEL, key=None, key_file="", logprobs=MAX_LOGPROBS,
                 batch=128, timeout=180, retries=4, backoff=1.0, transport=None,
                 stats=None):
        if not 0 <= logprobs <= MAX_LOGPROBS:
            raise TogetherError(f"logprobs must be 0..{MAX_LOGPROBS}, got {logprobs}")
        self.model = model
        self.key = resolve_key(key, key_file)
        self.logprobs = logprobs
        self.batch = max(1, int(batch))
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self.backoff = backoff
        self._transport = transport or self._http
        self.stats = stats if stats is not None else {
            "requests": 0, "prompts": 0, "prompt_tokens": 0,
            "completion_tokens": 0, "retried": 0, "chunks": 0,
        }

    # ---------------------------------------------------------------- http
    def _http(self, body):
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf-8", "replace")
            raise TogetherError(f"HTTP {e.code}: {payload[:300]}", e.code, payload) from e
        except urllib.error.URLError as e:
            # timeouts and connection resets are transient; wrapped so the
            # retry loop can tell them from the permanent ones above.
            raise _Transient(f"transport error: {e}") from e

    def _call(self, body):
        """One chunk with retries. Returns the parsed payload."""
        delay = self.backoff
        last = None
        for attempt in range(self.retries + 1):
            try:
                payload = self._transport(body)
                self.stats["requests"] += 1
                return payload
            except _Transient as e:
                last = TogetherError(str(e))
            except TogetherError as e:
                if e.status not in RETRY_STATUS:
                    raise
                last = e
            if attempt < self.retries:
                self.stats["retried"] += 1
                time.sleep(delay + random.random() * 0.25 * delay)
                delay *= 2
        raise TogetherError(f"giving up after {self.retries + 1} attempts: {last}",
                            getattr(last, "status", None))

    # ---------------------------------------------------------------- api
    def score(self, prompts, chunk_ids=None):
        """Score every prompt; returns one `Choice` per prompt, in order."""
        prompts = list(prompts)
        out = []
        for start in range(0, len(prompts), self.batch):
            chunk = prompts[start:start + self.batch]
            cid = "" if chunk_ids is None else str(chunk_ids[start // self.batch])
            payload = self._call({
                "model": self.model,
                "prompt": chunk,
                "max_tokens": 1,
                "temperature": 0,
                "echo": True,
                "logprobs": self.logprobs,
            })
            out.extend(self._parse(payload, chunk, cid))
            self.stats["chunks"] += 1
        self.stats["prompts"] += len(prompts)
        return out

    def score_one(self, prompt):
        return self.score([prompt])[0]

    def _parse(self, payload, prompts, chunk_id):
        n_prompts = len(prompts)
        choices = payload.get("choices")
        if not isinstance(choices, list):
            raise TogetherError(f"no choices in response: {str(payload)[:200]}")
        if len(choices) != n_prompts:
            raise TogetherError(
                f"expected {n_prompts} choices, got {len(choices)} "
                f"(array prompts unsupported or truncated)"
            )
        usage = payload.get("usage") or {}
        self.stats["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        self.stats["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        out = []
        for i, c in enumerate(choices):
            if "index" in c and c["index"] != i:
                raise TogetherError(f"choice {i} carries index {c['index']}: out of order")
            lp = c.get("logprobs")
            if not isinstance(lp, dict) or "token_logprobs" not in lp:
                raise TogetherError(
                    f"choice {i}: no legacy logprobs (no token_logprobs); "
                    "echo not honoured"
                )
            tokens = lp.get("tokens") or []
            logs = lp.get("token_logprobs") or []
            alts = [_parse_alts(e) for e in (lp.get("top_logprobs") or [])]
            # A one-token prompt (" ich") is legal and is exactly what the
            # word map sends; it simply has no scoreable position. Callers
            # that need positions check the length themselves.
            if len(tokens) < 1:
                raise TogetherError(f"choice {i}: empty token list")
            n = prompt_len(tokens, prompts[i])
            if n is None:
                raise TogetherError(
                    f"choice {i}: the echoed tokens do not reproduce the prompt "
                    f"({''.join(tokens)[:60]!r} vs {prompts[i][:60]!r}); "
                    "a misaligned row is worse than a missing one"
                )
            out.append(Choice(tokens, logs, alts, n, c.get("text") or "", chunk_id))
        return out

    # -------------------------------------------------------------- report
    def cost_usd(self, price_in, price_out=0.0):
        return (self.stats["prompt_tokens"] * price_in
                + self.stats["completion_tokens"] * price_out) / 1_000_000


class _Transient(Exception):
    """Internal: a failure worth retrying."""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        from together_common import self_test as common_self_test  # noqa: PLC0415

        common_self_test()
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
