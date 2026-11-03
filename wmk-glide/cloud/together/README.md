# Together AI as the German teacher — scripts and contract

Folder for the **API** teacher path: pull soft targets for the word-level
`.wmlm` student from a hosted model on Together AI, in the shape
`tools/wmlm/train.py` / `train_v2.py` already consume.

Everything here is the twin of [`../scaleway/`](../scaleway/): same corpus
selection, same prompt text, same four-array npz, same shard/merge discipline.
The transport and the *width* differ, and those differences are the content of
this folder.

Measured endpoint facts (2026-11-03, `probe.py`, `Qwen/Qwen3.5-9B` and
`openai/gpt-oss-120b`; details in
[`../../kb-inference-providers.md`](../../kb-inference-providers.md) §2b/§2c):

| Fact | Value |
|---|---|
| prompt log-probs | only via `/v1/completions` + `echo: true` |
| alternatives per position | **5, hard cap** (`logprobs: 20` → HTTP 400 `range [{max:5,min:0}]`) |
| `top_logprobs` order | **unordered** (11 of 233 positions sorted) → rank from the logprob |
| actual token's logprob | always present (`token_logprobs`), i.e. **+1 candidate per position** |
| repetition | cannot widen: identical requests, `temperature`/`n`/`seed`/`top_p` → bit-identical |
| `logit_bias` | applies to generation only → no suppression rounds (151k of ~152k ids biased, prompt unchanged) |
| token ids | not exposed (`return_tokens_as_token_ids` ignored, no `/v1/tokenize`) |
| array prompts | yes: 1000 prompts per request, **498 sentences/s**, 150k ≈ 5 min, ≈ $0.31 |
| chat endpoint | no prompt log-probs; closed path |

## Files

| File | What it does |
|---|---|
| `client.py` | batched scoring: array prompts, retries with backoff, UA (Cloudflare `403 code 1010`), cap enforcement, per-choice alignment checks, cost accounting; transport injectable for tests |
| `together_common.py` | target construction: candidates = 5 alternatives ∪ actual token, multi-token chains, exact `p(true word)` per row (+ injection), `mass`, per-row weights. `--self-test` |
| `wordmap.py` | measures the **teacher-token → student-word** map through the API itself (`prompt " wort"` → echoed tokens), so no local tokenizer version can disagree with the teacher |
| `distill_together.py` | sharded collector: `run.json` identity, resume, `.sha256`, `failures.jsonl`, merge, validation; `--temperature`, `--weight-mode`. `--self-test` (offline end-to-end) |
| `token_test.py` | corpus-level sanity: mean NLL, top-1 (argmax), top-k hits, captured mass on `out/de_lm` sentences |
| `probe.py` | endpoint probe: width, echo alignment, argmax agreement; modes `chat`, `repeat`, `breadth` |
| `model_ab.py` | model comparison on the 200 A/B sentences: NLL, top-1, width, candidate mass, word-spell rate; writes JSON + markdown |
| `tests/test_together.py` | 21 offline unit tests (client, targets, weights, audit sibling) |
| `tests/test_together_e2e.py` | synthetic `prep.py` corpus + fake transport → real collector → `check_soft.validate_soft` |

```bash
cd wmk-glide/cloud/together
python3 tests/test_together.py          # unit
python3 tests/test_together_e2e.py      # end to end, no network
python3 probe.py --self-test            # classifier fixtures

# which model should be the teacher? (200 German sentences, both classes)
python3 model_ab.py --models Qwen/Qwen3.5-9B,openai/gpt-oss-120b \
        --out ../../artifacts/out/ab_together.json
```

`model_ab.py` also reports the three ways a Together model can be unusable —
`non-serverless` (every base model), `batch_prompts_not_supported` (gRPC
backends; the client then falls back to one prompt per request) and a broken
echo (no prompt log-probs at all). See
[`../../together-teacher-plan.md`](../../together-teacher-plan.md) §6.

## What a row contains

Row `k` of a sentence is the teacher's distribution after word `k-1`
(row `0` is empty, `soft_mask.py fill` owns it), exactly as `distill.py` writes
it. Per row the collector emits:

* `ids`/`probs` — up to `--topk` (default 8) student ids, renormalised over
  the kept candidates: the four-array contract stays untouched.
* `mass` (sibling `<out>.audit.npz`) — the teacher probability the row
  actually captured **before** renormalisation, i.e. `1 − residual`.
* `actual`, `actual_p` — the true word's id and its **exact** teacher
  probability `p(w) = ∏ p(token)`.
* `weight` — per-row KD weight for `train_v2.py distill_weight=`
  (`--weight-mode mass|cand|piece`, default `mass`).
* `--temperature T` softens the teacher as `p^(1/T)` before ranking
  (`plans/student-quality-audit.md` §3.2 suggests 1,5–2,0 for the KD side);
  `mass` deliberately stays the **raw** probability, so the tail signal means
  the same thing at every T.
* `piece` — the row is a word the vocabulary only spells.

Why that matters, in one line each:

* The top-24 pipeline scored **0.0** on the 15.3 % piece rows
  (`audit_signal.json: piece_top24 0.0`); `echo` gives those rows their real
  probability, so the `p_b = 1−α` suppression (`kb-student-architecture-de.md`
  §2) loses its cause.
* The top-24 teacher's mass at width 8 is **85.1 %**, at width 4 **69.6 %**
  (`kb-student-architecture-de.md` §2.1). A 6-wide API row is in that regime,
  so the missing mass has to be *visible*: that is `mass`.

## Run

```bash
cd wmk-glide/cloud/together
KEY=/mnt/c/Users/saenta/.together.key          # never inside the repo

# 1. word map (one-time per model + vocabulary)
python3 wordmap.py /root/wmlm-de/out/de_lm --out /root/wmlm-de/out/wordmap_together.json \
        --model Qwen/Qwen3.5-9B --key-file "$KEY"

# 2. sanity on real sentences
python3 token_test.py --data-dir /root/wmlm-de/out/de_lm --sentences 100 --key-file "$KEY"

# 3. collect (sharded, resumable) + merge
python3 distill_together.py /root/wmlm-de/out/de_lm /root/wmlm-de/out/de_soft_together.npz \
        --map /root/wmlm-de/out/wordmap_together.json --sentences 150000 \
        --shard-size 25000 --batch 256 --weight-mode mass --temperature 1.5 \
        --key-file "$KEY"
```

Then the existing student path, unchanged except for two knobs:

```bash
# word-aware positions (soft_mask derives them from train.npz + the soft file)
python3 wmk-glide/tools/wmlm/soft_mask.py build out/de_lm out/de_soft_together.npz \
        out/de_soft_together.masks --emit-align

# train: no top-k re-truncation of an 8-wide target, mass-weighted KD
python3 tools/wmlm/train_v2.py ... distill=out/de_soft_together.npz \
        distill_topk=0 distill_alpha=0.3 \
        distill_align=out/de_soft_together.masks.align.npz \
        distill_weight=out/de_soft_together.audit.npz
```

`distill_topk=0` is required: with `K>0` the trainer re-truncates *and*
renormalises, which would throw away exactly the mass the collector recorded.
`distill_weight=…audit.npz` works because the sibling carries the key
`weight` that `load_gates` looks for.

## Guard rails

* The soft npz is validated with `wmk-glide/tools/check_soft.py` after every
  shard and after the merge; `--min-mass-ratio` defaults to 0.90 **row
  coverage** (not teacher mass — `check_soft.py` now reports both as
  `row coverage` and `mean row mass`).
* **Expected coverage is lower than the 24-wide cache.** With 6 candidates a
  row is empty whenever none of them is a whole student word; the top-24
  pipeline sat at 90.6 % (9.4 % = row 0 alone). A narrow API row can drop a
  few points more. That is not a defect but a property of the width, and it is
  paid for twice: empty rows get `weight = 0`, and the rows that do carry
  mass keep their real `mass`. Pass a lower `--min-mass-ratio` explicitly
  (e.g. 0.85) rather than discovering a hard gate failure at 2M scale.
* Shards are atomic (`.tmp.npz` + `os.replace`), carry `.sha256`, and are
  skipped when valid and identical to the requested member list.
* `run.json` pins corpus/vocab hashes, model, topk, map, injection and weight
  mode; a changed identity aborts unless `--allow-identity-change`.
* Every response is checked against its prompt (`"".join(tokens) == text`);
  a mismatch is a hard error, never a silent misalignment.
* Failures land in `failures.jsonl`; a failed chunk leaves the shard
  unwritten, so a resume recomputes it instead of shipping a hole.
