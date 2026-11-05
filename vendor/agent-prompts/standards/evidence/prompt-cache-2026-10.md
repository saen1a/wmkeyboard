# Token and prompt-cache evidence register (2026-10)

Status: evidence record for `standards/prompt-assembly.md` AS-09..AS-12 and
`standards/cache-profiles.json` (1.0.0).

Access date: 2026-10-25. These IDs are local to this register; the existing
prompt register uses S1..S26.

Claim labels:

- `stated` -- the fetched source states the claim.
- `likely` -- secondary source, arithmetic over stated values, or a reasonable
  inference.
- `unverified` -- not confirmed in a primary source this pass.

## 1. What the evidence says

1. **The cache is a prefix cache, not a content cache.** Anthropic computes a
   cumulative hash over tools, system, and messages up to the breakpoint; a
   change at or before the breakpoint produces a different hash. OpenAI requires
   the entire rendered prefix to match. Google and vLLM use the same prefix
   model with different control surfaces (T1, T2, T3, T6).
2. **Order and stability beat wording.** Static content belongs first; tool
   definitions sit near the front and are the most expensive thing to change.
   A timestamp or per-request ID in the prefix defeats the cache even when the
   rest is stable (T1, T2, T7).
3. **Cache economics are asymmetric.** Writes cost more than base input
   (about 1.25x for a short TTL, up to 2x for a long TTL); reads cost about 0.1x.
   A prefix used twice can pay; an unused write is a loss. A prefix below the
   model minimum is never cached (T1, T2, T4).
4. **Append-only history preserves reuse.** Do not edit, reorder, or clean up
   earlier turns; append corrections. Compaction starts a new prefix and must
   be judged on total cost, not hit rate alone (T2, T7, T11).
5. **Mask tools instead of removing them.** A tool-set change invalidates the
   tool and system cache; use stable definitions plus a mask (`tool_choice`,
   `allowed_tools`, deferred loading) where the provider supports it (T1, T2,
   T7).
6. **Progressive disclosure and restorable compression are token levers.**
   Metadata/body/reference layers, file-path memory, and drop-with-a-pointer
   beat irreversible compression. Compression can reduce tokens while
   lowering cache reuse (T7, T11, T13).
7. **Hit rate is diagnostic, not the objective.** Optimize total cost and
   verified-task quality. A change can lower hit rate and still save money
   (T2, T7, T8).
8. **Minimums and multipliers are model-specific and drift.** Treat them as a
   dated configuration, not doctrine. The library pins a profile file with an
   `as_of` and `review_by` date (T1, T2, T3, T4).

## 2. Source register

| ID | Source | Type | Key claim used here | Label |
|---|---|---|---|---|
| T1 | Anthropic, "Prompt caching", accessed 2026-10-25, https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching | vendor doc | Prefix order tools -> system -> messages; cumulative hash; max 4 breakpoints; 5-minute default and 1-hour option; 1.25x/2x writes, 0.1x reads (model exceptions); minima 512/1,024/2,048/4,096 by model; a breakpoint on volatile content never hits | stated |
| T2 | OpenAI, "Prompt caching", accessed 2026-10-25, https://platform.openai.com/docs/guides/prompt-caching | vendor doc | Entire rendered prefix must match; 1,024-token minimum on current models; 1.25x/2.5x writes, 0.1x reads; 30-minute/12-hour TTL; per-machine cache and routing effects; append-only history and stable tools; compaction can reduce hit rate while reducing cost | stated |
| T3 | Google, "Context caching", Gemini API, updated 2026-10-23, https://ai.google.dev/gemini-api/docs/caching | vendor doc | Prefix caching; minima 2,048/4,096; put large common content first; small agent-loop additions may re-process the tail | stated |
| T4 | Google Cloud, "Context cache overview", accessed 2026-10-25, https://cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview | vendor doc | 90% cached-token discount on 2.5+; explicit cache TTL and storage billing; implicit prefix expiry | stated |
| T5 | DeepSeek, "Context caching", accessed 2026-10-25, https://api-docs.deepseek.com/guides/kv_cache | vendor doc | Prefix-only matching, on by default; hit/miss token fields; best-effort, no 100% guarantee | stated |
| T6 | vLLM, "Automatic prefix caching", accessed 2026-10-25, https://docs.vllm.ai/en/stable/design/v1/prefix_caching.html | vendor doc | Block-hash prefix reuse; parent hash + block tokens + extras; only full blocks; deterministic hashing matters across versions | stated |
| T7 | Manus, "Context Engineering for AI Agents: Lessons from Building Manus", 2025-07-18, https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus | vendor engineering | KV-cache hit rate is the top production metric; ~100:1 input:output; timestamps kill cache; append-only context; deterministic serialization; tool definitions near front; mask rather than remove; file system as restorable memory; keep errors | stated |
| T8 | Gim et al., "Prompt Cache: Modular Attention Reuse for Low-Latency Inference", arXiv 2311.04934 / MLSys 2024, https://arxiv.org/abs/2311.04934 | paper | 8x GPU / 60x CPU TTFT improvement from reusable prompt modules | stated |
| T9 | Zheng et al., "SGLang: Efficient Execution of Structured Language Model Programs", arXiv 2312.07104 / NeurIPS 2024, https://arxiv.org/abs/2312.07104 | paper | Up to 6.4x throughput with RadixAttention prefix reuse | stated |
| T10 | Yao et al., "CacheBlend: Fast Large Language Model Serving for RAG with Cached Knowledge Fusion", arXiv 2405.16444 / EuroSys 2025, https://arxiv.org/abs/2405.16444 | paper | 2.2-3.3x TTFT reduction, 2.8-5x throughput with non-prefix KV reuse | stated |
| T11 | Pan et al., "LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression", arXiv 2403.12968 / ACL 2024 Findings, https://arxiv.org/abs/2403.12968 | paper | 2x-5x compression, 1.6x-2.9x end-to-end latency reduction; lossy and task-dependent | stated |
| T12 | Mu et al., "Learning to Compress Prompts with Gist Tokens", arXiv 2304.08467 / NeurIPS 2023, https://arxiv.org/abs/2304.08467 | paper | 26x prompt compression, up to 40% FLOPs reduction; requires fine-tuning the target model | stated |
| T13 | Chroma, "Context Rot", 2025, https://research.trychroma.com/context-rot; "Context Length Alone Hurts LLM Performance Despite Perfect Retrieval", arXiv 2510.05381, https://arxiv.org/abs/2510.05381 | vendor research + preprint | Performance degrades non-uniformly as input length grows, even with perfect retrieval | stated |
| T14 | Gloaguen et al., "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?", arXiv 2602.11988, 2026, https://arxiv.org/abs/2602.11988 | preprint | Context files can add about 20-23% inference cost for a small success gain; repository overviews are a weak use of tokens | stated |

## 3. What this does and does not establish

- It establishes the mechanism and direction: stable static prefix, append-only
  history, stable tools, deterministic serialization, on-demand disclosure, and
  measured cost.
- It does not establish a universal minimum, TTL, or multiplier. Those are
  vendor- and model-specific; `standards/cache-profiles.json` carries a dated
  profile set, not a law.
- It does not establish that a high hit rate improves task success. Hit rate is
  a diagnostic; total cost and verified-task quality are the objectives.
- The library can enforce prefix shape and stability. It cannot measure hit
  rate, cache expiry, or routing without runtime telemetry.
