# Chutes support report: Qwen3.8-27B prompt_logprobs corrupted

**To:** Chutes support / Token Factory team
**Subject:** `prompt_logprobs` for `Qwen/Qwen3.8-27B-TEE` are silently corrupted (vLLM MTP #53488)

## Summary

`POST https://llm.chutes.ai/v1/completions` with
`model=Qwen/Qwen3.8-27B-TEE`, `prompt_logprobs=20`, `max_tokens=1`,
`temperature=0` returns **HTTP 200 with wrong prompt-logprob vectors** most
of the time. This is not a request problem; it matches vLLM issue **#53488**
(MTP speculative decoding overwrites the hidden states used for
`prompt_logprobs`) and its fix **PR #53520**.

## Reproduction

Prompt:

```text
ich will nach Hause gehen und morgen früh
```

Ten identical requests, position 1 (the token after `ich`):

| Run | Top-1 | Actual ` will` |
|---:|---|---|
| 1 | `mehr` | rank 70,733, logprob −12.47 |
| 2 | `mehr` | wrong |
| 3 | `mehr` | wrong |
| 4 | **` habe`** | **plausible** |
| 5–10 | `mehr`, `七七`, `ools`, `培`, `ァ` | wrong |

The tokenizer used for the check is the official Qwen3.8-27B tokenizer
(same 248,044-token vocab). The prompt and token IDs are correct; only the
returned distribution is wrong.

A 100-sentence run (50 German chat + 50 news sentences) against this
endpoint gave **top-1 3.6 %** and **NLL ≈ 1e36** — clearly corrupted, not
model quality.

Sometimes the same request returns HTTP 400
`Out of range float values are not JSON compliant: nan`; that is the visible
form of the same bug.

## Request

Please either:

1. disable MTP/speculative decoding for `Qwen/Qwen3.8-27B-TEE`, or
2. update the vLLM build to include **PR #53520** (snapshot target hidden
   states before the drafter).

Then I can validate with 20 sentences and use the model for a 1.2M-sentence
German distillation. Until then the prompt-logprob output is unusable, even
though HTTP success rates look high.

## Notes

- `prompt_logprobs` is required; generated-token `logprobs` is not enough.
- The same corruption appears on `/v1/chat/completions`.
- Qwen3.5-397B/Qwen3.6-27B are SGLang on Chutes and do not expose prompt
  logprobs over the OpenAI gateway, so they are not an alternative.
