# Scaleway H100 runbook — German WMLM 1.2M / 2M teacher run

Working area for the German teacher pass on **one Scaleway H100 80 GB**
(`H100-1-80G`, `fr-par-2`, ~€2.88775/h with block storage and flexible IP,
billed per minute). The session prompt is
[`../../NEXT-SESSION-PROMPT.md`](../../NEXT-SESSION-PROMPT.md).

Status 30.10.2026: **Phase -1 (2M corpus) done**, **full chain executed once on
a rented `L40S-1-48G`** (72 min, ≈1.8 €, terminated) — gate, 10k distill,
student, export, harness build and evaluation all ran; the bugs it exposed
are fixed (see the smoke section). A second short run measured the
**teacher A/B 27B vs 9B vs 4B** on a fixed sentence set (27 min, ≈0.66 €,
terminated; results in the Open items and `wmlm-training-plan.md` §1.3).
**Still open:** the big 1.2M/2M teacher pass, waiting for H100 stock.

## Files

| File | What it does |
|---|---|
| `prepare_2m.py` | builds/verifies the 2M mix (dedup, heldout-safe, manifest, SHA) |
| `vllm_common.py` | shared prompt/offset/top-k bridge, byte-compatible with `tools/wmlm/distill.py` + patch 0005 (`--self-test`) |
| `distill_vllm.py` | sharded vLLM collector: checkpoint per shard, resume, retries, failure JSONL, `--retry-failures` |
| `benchmark_quick.py` | Phase 0a throughput gate, FP8 only, 60 s measurement |
| `benchmark_prompt_logprobs.py` | 100 chat + 100 news sentences, BF16 vs FP8, top-1/top-8/NLL, agreement |
| `run_distill_1m2.sh` | pass 1 (`attempts=3`) → pass 2 failures (`attempts=10`) → merge → `check_soft.py` |
| `prep_train_eval.sh` | `prep.py` → 30k student steps (resumable) → export → typing/glide measurement |
| `setup_h100.sh` | checks GPU/CUDA/disks, venv, vLLM, model download to `/data/models`, writes `/data/env.sh` |
| `transfer.sh` | rsync up/down/check; models stay on the box unless `MODELS=1`; never logs secrets |
| `teardown.sh` | down → verify every artifact hash → only then allow `--terminate` (writes `artifacts/teardown-verified`) |
| `cloud-init.yaml` | minimal, secret-free cloud-init (no driver/vLLM/model work) |
| `credentials.example.env` | template for `C:\Users\saenta\.scw\wmlm-h100.env` |
| `_e2e_distill_test.py` | offline end-to-end test of the collector (fake engine, no GPU) |

`_e2e_distill_test.py` is a development test, not a run tool; run it with
`python3 _e2e_distill_test.py` before touching the collector.

## Selected instance (fixed, verified live 29.10.2026)

- **H100-1-80G**, zone **PAR-2 / `fr-par-2`** — the only zone that offers it.
- 24 vCPU, 240 GB RAM, 1× H100 PCIe 80 GB (HBM2e, 2 TB/s), up to 10 Gbps,
  block storage + local NVMe scratch, **billed per minute**, list price
  "from €2.86/GPU/hour".
- **Ubuntu Noble GPU OS 13 (Nvidia)**: Ubuntu 24.04 based, NVIDIA driver,
  Docker and the NVIDIA Container Toolkit preinstalled. Do **not** install
  apt NVIDIA drivers.
- Scratch on H100 GPU OS is a local NVMe volume mounted at `/scratch` and
  is **wiped on stop/delete**. Put the HF cache and temporary files there
  only if `/data` gets tight; every final artifact goes to `/data` (block)
  or is downloaded immediately.
- Budget: `MAX_BUDGET_EUR=50` default, stop at >12 h without a gate.
- **Stock (30.10.2026, `scw instance server-type list zone=fr-par-2`)**: the
  H100-1-80G was **out of stock** (also in `pl-waw-2`; `fr-par-1` does not
  offer it). L40S-1-48G (€1.46988/h) was the only single-GPU option with
  stock. It is a fallback for the 1.2M run only: measured 59.45 prompts/s, ~0.6× an H100 at 100/s,
  and 48 GB cannot hold the BF16 reference (55 GB), so Phase 0b's BF16/F8
  A/B is impossible there. Verified image UUID for
  `Ubuntu Noble GPU OS 13 (Nvidia)`: `741cfd27-a822-4c82-b80f-973b562743ad`.
  Re-check stock before creating anything; `scw`'s default zone here is
  `fr-par-1`, so always pass `zone=fr-par-2`.

Sources read for this runbook:

- GPU quickstart (instance/image selection, "Ubuntu Noble GPU OS 13"):
  <https://www.scaleway.com/en/docs/gpu/quickstart/>
- GPU offer + specs (24 vCPU / 240 GB / 80 GB HBM2e / PAR-2 only):
  <https://www.scaleway.com/en/h100/> and
  <https://www.scaleway.com/en/choose-the-right-gpu/>
- GPU pricing, per-minute billing: <https://www.scaleway.com/en/pricing/gpu/>
- Scratch storage on H100: <https://www.scaleway.com/en/docs/gpu/how-to/use-scratch-storage-h100-instances/>
- Docker on GPU instances: <https://www.scaleway.com/en/docs/gpu/how-to/use-gpu-with-docker/>
- CLI basics: <https://www.scaleway.com/en/docs/instances/api-cli/creating-managing-instances-with-cliv2/>
  and <https://www.scaleway.com/en/docs/instances/api-cli/cli-cheatsheet/>
- Image catalogue: <https://www.scaleway.com/en/docs/instances/reference-content/images-and-instantapps/>
- Object Storage (optional transfer path): <https://www.scaleway.com/en/docs/object-storage/>

### Image and zone verification (run before creating anything)

```bash
scw init            # access key, secret key, project, zone fr-par-2
scw instance image list zone=fr-par-2 | grep -i "GPU OS 13"
scw instance server list zone=fr-par-2
```

Record the **exact image UUID** and the instance ID in the run log. If
`H100-1-80G` is not offered in `fr-par-2`, **stop and report**; do not
switch GPU type or zone without asking.

Creating the instance is allowed with the CLI from
`SCW_ACCESS_KEY`/`SCW_SECRET_KEY`/`SCW_DEFAULT_PROJECT_ID`, but only after
the price and zone are confirmed, and only `H100-1-80G` in `fr-par-2`.
If the CLI flags do not match `scw instance server create --help`, use the
console wizard from the quickstart link instead of guessing flags.

## Credentials

One file **outside the repo**:
`C:\Users\saenta\.scw\wmlm-h100.env`, copied from
[`credentials.example.env`](credentials.example.env) and filled in. It is
never committed, never echoed, and never part of a prompt or log.

Required keys: `SCW_ACCESS_KEY`, `SCW_SECRET_KEY`, `SCW_DEFAULT_PROJECT_ID`,
`SCW_DEFAULT_ORGANIZATION_ID`, `SCW_DEFAULT_ZONE=fr-par-2`,
`SCW_INSTANCE_TYPE=H100-1-80G`, `SCW_INSTANCE_ID`, `SCW_INSTANCE_IP`,
`SCW_SSH_USER=root`, `SCW_SSH_KEY_PATH`, `MAX_BUDGET_EUR=50`, optional
`HF_TOKEN`.
`cloud/scaleway/.gitignore` excludes `*.env`, `*.key`, `*.pem`, `id_*`,
`*_ed25519`, `data/`, `out/`.

The H100 scripts read these only as environment variables
(`set -a; . /path/to/wmlm-h100.env; set +a`) or through `scw`; nothing in
this directory parses the file.

`scw` 2.65.1 honours these variables directly — no
`~/.config/scw/config.yaml` is needed, and `scw init` is optional. Verified
30.10.2026: with all five set the CLI reaches the API; without
`SCW_DEFAULT_ORGANIZATION_ID` it stops at "Organization ID is required"
(`scw config get …` only reads the config *file*, so use an API command to
test the environment path).

### SSH key for the instance

Generated 29.10.2026 (ed25519, **no passphrase** — `ssh -i` is used
unattended from the run scripts; the key is single-purpose and lives outside
the repo):

| | |
|---|---|
| private | `C:\Users\saenta\.ssh\wmlm-h100_ed25519` (ACL: only `saenta` + SYSTEM/Administrators) |
| public | `C:\Users\saenta\.ssh\wmlm-h100_ed25519.pub` |
| fingerprint | `SHA256:hlAbPiTKGMyFq4DuJOCBffF/CTX1QnIEwdkZdRVIC1U` |
| comment | `wmlm-h100@saenta` |

`SCW_SSH_KEY_PATH` in `wmlm-h100.env` points at the private key.

Register the **public** key in the Scaleway project before creating the
instance (only the public key leaves this machine):

```bash
# CLI (verified against https://cli.scaleway.com/iam/, `scw iam ssh-key create`)
scw iam ssh-key create name=wmlm-h100 \
  public-key="$(cat ~/.ssh/wmlm-h100_ed25519.pub)"
scw iam ssh-key list name=wmlm-h100

# Console alternative: Account > SSH keys > Add SSH key, paste the .pub line.
```

When the instance is created (console wizard or CLI), pick `wmlm-h100` as
the SSH key. Verify the first login and the host fingerprint, then check:

```bash
ssh -i "$SCW_SSH_KEY_PATH" -o IdentitiesOnly=yes root@"$SCW_INSTANCE_IP" \
  'nvidia-smi -L; df -h /data /scratch'
```

Rotate after the run: disable/delete the key in Scaleway
(`scw iam ssh-key list name=wmlm-h100`, `scw iam ssh-key delete <id>`) and
delete the local pair if it is no longer needed. Never copy the private key
into the repo or onto the instance.

## Corpus: 2M prepared (Phase -1, done)

`wmk-glide/artifacts/corpora/de_2m_mix.tsv` — **2,000,000 unique rows**,
**1,066,000 chat (53.3 %) / 934,000 news (46.7 %)**, SHA256
`a3b7cd04b8b98ecca82d01c3f4bb87ee10969103b249e8c7e2f6770f296fa61c`.

| Piece | Rows |
|---|---:|
| `de_all.tsv` Tatoeba DE (chat, `1/1`), after dedup + 3–40-word filter | 764,297 |
| OpenSubtitles DE v2018 mono (chat top-up) | 301,703 |
| Leipzig News 2023 (`2/0`), sampled | 934,000 |
| held-out rows dropped from `de_all.tsv` | 18,063 |
| held-out rows dropped from OpenSubtitles | 558,441 |
| held-out leaks in the result | **0** |
| duplicate texts | **0** |

The held-out comparison runs through `tools/wmlm/common.py`'s `tokenize`,
the same function `prep.py` and the engine use: `heldout.tsv` is stored
tokenized (lower case, no punctuation, `<num>`), so a plain lower/whitespace
key misses almost every sentence. The first build used such a key and leaked
17,406 held-out rows while `--verify` still reported 0; both the build and
`--verify` now share the tokenized key, and an independent re-check of the
built file finds 0 leaks.

Build and verify:

```bash
python3 prepare_2m.py \
  --all ../../artifacts/corpora/de_all.tsv \
  --heldout ../../artifacts/data/heldout.tsv \
  --extra-chat ../../artifacts/corpora/opensubtitles_de_v2018.txt.gz \
  --out ../../artifacts/corpora/de_2m_mix.tsv --seed 0

python3 prepare_2m.py --verify ../../artifacts/corpora/de_2m_mix.tsv \
  --heldout ../../artifacts/data/heldout.tsv --expect-rows 2000000
```

The manifest next to the file (`de_2m_mix.tsv.manifest.json`) records
sources, filter, drop counters, seed and SHA. `de_1m_200k_chat.tsv` is
untouched.

`prep.py` on the 2M mix (1:21 min, 2.4 GB RSS on this machine):

```bash
# prep.py opens seed_words with plain open(), so decompress the .gz first
zcat wmk-glide/artifacts/data/de_aosp.txt.gz > /tmp/de_aosp.txt
python3 tools/wmlm/prep.py wmk-glide/artifacts/corpora/de_2m_mix.tsv wmk-glide/artifacts/out/de_lm_2m \
  vocab=24576 pieces=2048 ctx=40 seed_words=/tmp/de_aosp.txt heldout=20000
# -> train.npz 1,980,000 sentences / 40,556,654 tokens, heldout 20,000, coverage 84.70 %
```

`prep_train_eval.sh` does the decompression itself (into `mktemp -d`) when
`SEED_WORDS` ends in `.gz`; only the direct `prep.py` call needs the step.

**Licence caveat:** the extra chat source is OpenSubtitles v2018 via OPUS
(CC BY-NC-4.0-style terms, attribution to opensubtitles.org and Lison &
Tiedemann 2016). The project already uses OpenSubtitles for English, but
**NC terms make a shipped model legally unclear** — decide before
publishing a 2M-trained model. `prepare_2m.py --no-extra` builds the
maximum unique set instead and marks the 2M target open.

**Known defect in the 1.2M corpus:** `de_1m_200k_chat.tsv` was built by
`wmk-glide/tools/mix_chat_corpus.py` with the same non-tokenized held-out
key and contains **12,368** held-out rows (measured 29.10.2026). If the 1.2M
path is taken, rebuild it the same way (`prepare_2m.py` with
`--chat 640000 --news 560000`) or measurements on `heldout.tsv` are
contaminated.

## Phase runbook

### 0. Bring-up

```bash
set -a; . /mnt/c/Users/saenta/.scw/wmlm-h100.env; set +a   # on the box: export the same values
ssh -i "$SCW_SSH_KEY_PATH" "$SCW_SSH_USER@$SCW_INSTANCE_IP"
nvidia-smi                                    # expect H100 80 GB, driver from the image
bash wmk-glide/cloud/scaleway/setup_h100.sh --check
bash wmk-glide/cloud/scaleway/setup_h100.sh   # venv + vLLM + Qwen3.8-27B-FP8 into /data/models
. /data/env.sh
```

`setup_h100.sh` refuses nothing on CUDA 13 but warns: the vLLM wheel brings
its own CUDA runtime; if it cannot load, use the vLLM Docker image
(`vllm/vllm-openai`, `--gpus all`, HF cache bind-mount) instead of apt.
It **fails** when `/data` is not a mountpoint (`ALLOW_ROOT_DISK=1` overrides):
otherwise the 28 GB model and every output land on the ephemeral root disk.

`. /data/env.sh` exports `TEACHER_MODEL` (the local `/data/models/...` path)
and `TEACHER_MODEL_ID`. The run scripts prefer the local path, so vLLM does
not download a second copy into the HF cache. It also sets
`VLLM_USE_FLASHINFER_SAMPLER=0`: the GPU OS image has no `nvcc`, and
FlashInfer's sampler JIT would otherwise fail at the first `generate`
(measured on the L40S smoke run). The scripts default to
`max_num_seqs=64` and `max_logprobs=24` for the same reason — Qwen3.8 needs
one Mamba cache block per sequence and vLLM caps logprobs at 20 by default.

### 1. Phase 0a — short throughput gate (first, FP8 only)

```bash
cd /root/wmk                                  # transfer.sh installs the tree here
. /data/env.sh                                # TEACHER_MODEL, VLLM_PY, PATH
export PYTHONPATH=$PWD/tools/wmlm:$PWD/wmk-glide/tools
"$VLLM_PY" wmk-glide/cloud/scaleway/benchmark_quick.py \
  --data wmk-glide/artifacts/out/de_lm_2m --model "$TEACHER_MODEL" \
  --prompts 200 --batch 32 --seconds 60 --out /data/out/bench_quick_fp8.json
```

`--data` is the checkout copy (`wmk-glide/artifacts/...`), not a root
`artifacts/` tree, and `--model` is the local checkpoint from
`setup_h100.sh` — passing the HF id downloads a second 29 GB.

One warm-up batch, then up to 200 prompts or 60 s. `prompt_logprobs=24`,
`max_tokens=1`, no MTP/speculative config, no chat template, no BF16.

| Gate | Action |
|---|---|
| **< 35 prompts/s**, or implausible logprobs | stop, report cost + alternatives (35B-A3B-Base, local 9B Q8, Kolibri 4-bit/2×H100); no further runs |
| **35–100 prompts/s** | take the **1.2M** corpus |
| **≥ 100 prompts/s** and 2M projection **< 6 h / < €20** | take the **2M** corpus (soft targets are reusable) |

The script writes `prompts_per_s`, prompt tokens/s, batch latency, mean NLL,
top-1 share, missing-actual-token and non-finite counts, plus projections
for 1.2M and 2M at €2.88775/h. It exits 3 below the gate so a `&&` chain
stops. Stop the instance afterwards unless Phase 0b follows immediately.

### 2. Phase 0b — teacher A/B (run it, it costs ~2 min)

The comparison that answers "is the 27B actually better than 4B/9B" must use
**one fixed sentence set**, otherwise every run measures different sentences.
Dump it once (deterministic, seed 0, 100 casual + 100 formal):

```bash
python3 -c "import sys; sys.path.insert(0,'wmk-glide/cloud/scaleway'); \
import vllm_common as vc, benchmark_prompt_logprobs as b; \
v,t,s = vc.load_corpus('wmk-glide/artifacts/out/de_lm_2m'); c,n = b.pick_sentences(v,t,s,100,0); \
b.dump_sentences('wmk-glide/artifacts/out/ab_sentences.tsv', v,t,s,c,n)"
```

Then measure all three teachers on exactly those sentences, in one command
(each model gets its own process; a failing model does not abort the rest):

```bash
/opt/vllm-venv/bin/python wmk-glide/cloud/scaleway/benchmark_prompt_logprobs.py \
  --data wmk-glide/artifacts/out/de_lm_2m \
  --models /data/models/Qwen3.8-27B-FP8,Qwen/Qwen3.5-9B-Base,Qwen/Qwen3.5-4B-Base \
  --sentences-file wmk-glide/artifacts/out/ab_sentences.tsv \
  --per-class 100 --batch 16 --out /data/out/ab_3way.json
```

Output: per class (chat/news) student-projected top-1 mass, top-8 mass and
mean NLL for every model, plus pairwise top-1 agreement and mass deltas.
Those are the same metrics as the historical 4B/9B run
(`kb-teacher-models.md` §4a: 4B 28.43/32.10 top-1, 9B 29.65/34.41).

The extra models are ~26 GB of downloads (≈3 min at 120 MB/s) and ~1 min
load each; the 27B is already on the box from `setup_h100.sh`.

### 3. Phase 2 — 10k soft-target A/B

```bash
TOTAL=10000 LOG=/data/out/teacher_10k.log \
  bash wmk-glide/cloud/scaleway/run_distill_1m2.sh /data/out/de_soft_10k.npz wmk-glide/artifacts/out/de_lm_2m
# student, 3k-5k steps, same data, then heldout/typing/glide
STEPS=4000 SKIP_PREP=1 CORPUS= \
  bash wmk-glide/cloud/scaleway/prep_train_eval.sh /data/out/de_soft_10k.npz \
  wmk-glide/artifacts/out/de_lm_2m /data/out/de_run_10k
```

Only a clear win (~>0.3 top-1) justifies the big run.

### 4. Phase 3 — 1.2M or 2M

```bash
# 2M: the collector reads the corpus prepared upstream (no prep on the box)
bash wmk-glide/cloud/scaleway/run_distill_1m2.sh /data/out/de_soft_2m.npz wmk-glide/artifacts/out/de_lm_2m

# 1.2M: prep once (locally, or on the box with CORPORA=1 so the TSV is there)
SKIP_TRAIN=1 CORPUS=wmk-glide/artifacts/corpora/de_1m_200k_chat.tsv \
  bash wmk-glide/cloud/scaleway/prep_train_eval.sh /data/out/de_soft_1m2.npz \
  wmk-glide/artifacts/out/de_lm_1m2 /data/out/de_run_1m2

bash wmk-glide/cloud/scaleway/run_distill_1m2.sh /data/out/de_soft_1m2.npz wmk-glide/artifacts/out/de_lm_1m2
```

`transfer.sh up` skips the raw corpora by default (`CORPORA=1` to include
them); prep is meant to run locally and only `out/de_lm_*` travels.
`prep_train_eval.sh` reuses `train.npz` only when `prep.json` matches the
corpus hash and the vocab/pieces/ctx settings.

`TOTAL=0` (default) collects every sentence of `train.npz`. Shards are
5,000 sentences: valid shards are skipped, a shard resumes from its partial
checkpoint, pass 2 retries only the failures with `attempts=10`, the merge
is atomic, and `check_soft.py` must pass before `.DONE` is written.

Then the student (30k steps) and the measurement:

```bash
bash wmk-glide/cloud/scaleway/prep_train_eval.sh /data/out/de_soft_2m.npz \
  wmk-glide/artifacts/out/de_lm_2m /data/out/de_run_2m
```

### 5. Stop and secure

```bash
bash wmk-glide/cloud/scaleway/transfer.sh down root@$SCW_INSTANCE_IP
bash wmk-glide/cloud/scaleway/transfer.sh check root@$SCW_INSTANCE_IP
scw instance server stop "$SCW_INSTANCE_ID" zone=fr-par-2
```

`transfer.sh` reads `/data` on the box (`REMOTE_ART`, where the run actually
writes), not the repo checkout, and excludes `*.env`/`*.key`/`*.pem` on the
way up. Confirm the `check` hashes before deleting anything.

Block storage keeps billing while the instance is stopped; delete the
volume only after the results are on the local disk and verified, and never
without asking.

### Long-job safety rails

- `run_distill_1m2.sh` caps the pass at `min(MAX_BUDGET_EUR/€2.88775,
  MAX_HOURS)` hours with `timeout`; hitting the cap stops before the merge
  and keeps every valid shard (resume with the same command).
- A shard dir carries `run.json` (corpus, selection, seed, model, top-k).
  Reusing it with different settings is refused unless
  `--allow-identity-change` is passed; growing `--count` is allowed (staged
  runs, see below).
- The merge only runs when no `.INCOMPLETE` shard is left; it also skips
  `*.partial.npz`, and a successful shard drops both markers.
- `prep_train_eval.sh` copies `wmk-glide/experiments/glide_lm_blend_eval.rs`
  into `native/wm-engine/examples/` before the build, because the engine
  only builds examples from its own directory.

### Staged runs (1.2M now, the rest later)

Staging happens **on one fixed `train.npz`**, never by re-running `prep.py`:
the soft targets are indices into that file, and a new corpus means a new
shuffle, so old rows would point at different sentences. The selection is a
fixed permutation (seed) truncated to `--count`, so growing the count only
appends shards and every existing shard keeps its sentence ids. `run.json`
therefore records the count but does not compare it.

`out/de_lm_2m` has 1,980,000 sentences = **396 shards** of 5,000:

```bash
# stage A: first 1.2M sentences (240 shards) — e.g. on the L40S
TOTAL=1200000 bash wmk-glide/cloud/scaleway/run_distill_1m2.sh /data/out/de_soft_2m.npz wmk-glide/artifacts/out/de_lm_2m

# training on what exists (optional, before the rest is collected)
PARTIAL_MERGE=1 bash wmk-glide/cloud/scaleway/run_distill_1m2.sh ...   # merges valid sentences of complete + incomplete shards

# stage B: the remaining ~780k (156 shards) — same command, no --count
bash wmk-glide/cloud/scaleway/run_distill_1m2.sh /data/out/de_soft_2m.npz wmk-glide/artifacts/out/de_lm_2m
```

Stage B skips the 240 valid shards and collects only the rest; the final
merge then needs all 396. `PARTIAL_MERGE=1` writes an npz for the sentences
that are done (train.py simply has teacher mass for fewer sentences), with
the expected count read from the shards themselves.

### Smoke test on a cheaper GPU (L40S)

**First run done 30.10.2026** on `L40S-1-48G` / `fr-par-2`
(`0a498a24-ff75-4c97-800b-1cf420299bc2`, 72 min, ≈ **1.8 €**, terminated).
Measured, not estimated:

| | Value |
|---|---|
| gate (200 prompts, batch 32) | **59.45 prompts/s**, 1,029 prompt tokens/s, 477.9 ms/batch |
| plausibility | NLL 4.28, top-1 share 0.322, top-k width 24.4, missing 0, non-finite 0 |
| projection 1.2M / 2M | **5.61 h** (8.25 € L40S / 16.19 € H100-rate) · **9.34 h** (13.73 € / 26.99 €) |
| distill 10k | 55.8 sentences/s, **107,186 rows, mass 90.6 %**, 0 failures, 10 accepted with high NLL |
| student 2k steps | loss 5.16, heldout ppl 236, export 10.86 MB |
| typing_eval (100) | strip top1 0.57 → 0.59 with LM, next-word top1 0.099 |
| glide 150k / comp3 (blend top1) | 0.7566 / 0.7685 |

These are **plumbing numbers** (10k soft targets, 2k steps), not production
quality. What the run bought, in bugs it caught before the H100:

1. vLLM 0.32 needs `max_num_seqs<=~64` for this model — Qwen3.8 allocates one
   Mamba cache block per sequence, the default 256 does not fit in 48 GB.
2. FlashInfer's JIT sampler needs `nvcc`, which the GPU OS image does not
   have; `VLLM_USE_FLASHINFER_SAMPLER=0` avoids it (and sampling is
   irrelevant at `max_tokens=1`).
3. `prompt_logprobs` is capped at 20 by default; `max_logprobs=24` is needed
   for the top-24 contract.
4. `run_distill_1m2.sh` used `$TOPK` but defined `TOP_K` (`set -u` abort).
5. The staging docs said `COUNT=`, the script reads `TOTAL=`.
6. The harness build needs repo assets outside `native/`:
   `wmk-glide/experiments/glide_lm_blend_eval.rs`, `app/…/assets/dictionaries/`
   and `app/…/assets/avro/` — `transfer.sh up` now ships them.
7. `PARTIAL_MERGE` dropped whole shards on a single failure; it now merges
   the valid sentences. And a mean-NLL excess is a *soft* rejection: retried,
   then accepted (0.08 % of sentences), so shards can finish cleanly.

Purpose: exercise the whole chain once for ~2 € before the H100 run.
Same artifacts, same commands; only `TOTAL`, `STEPS` and the eval scope
shrink.

```bash
scw instance server create type=L40S-1-48G zone=fr-par-2 \
  image=741cfd27-a822-4c82-b80f-973b562743ad name=wmlm-smoke \
  root-volume=block:125GB ip=new \
  cloud-init=@wmk-glide/cloud/scaleway/cloud-init.yaml --wait -o json
# SSH keys are project-wide and are injected automatically.
scw instance server get <id> zone=fr-par-2 -o json | grep -i address

bash wmk-glide/cloud/scaleway/transfer.sh up    root@<ip>   # tools, harness, data, out/de_lm_2m, ab_sentences.tsv
ssh -i "$SCW_SSH_KEY_PATH" root@<ip> 'cd /root/wmk &&
  bash wmk-glide/cloud/scaleway/setup_h100.sh --check &&
  bash wmk-glide/cloud/scaleway/setup_h100.sh && . /data/env.sh &&
  "$VLLM_PY" wmk-glide/cloud/scaleway/benchmark_quick.py \
    --data wmk-glide/artifacts/out/de_lm_2m --model "$TEACHER_MODEL" --seconds 60 \
    --out /data/out/bench_quick.json'

TOTAL=10000 PARTIAL_MERGE=1 bash wmk-glide/cloud/scaleway/run_distill_1m2.sh \
  /data/out/de_soft_smoke.npz wmk-glide/artifacts/out/de_lm_2m
STEPS=2000 SKIP_PREP=1 CASES=100 bash wmk-glide/cloud/scaleway/prep_train_eval.sh \
  /data/out/de_soft_smoke.npz wmk-glide/artifacts/out/de_lm_2m /data/out/de_run_smoke

# Teacher A/B on the fixed sentence set (27B/9B/4B, same projection).
"$VLLM_PY" wmk-glide/cloud/scaleway/benchmark_prompt_logprobs.py \
  --data wmk-glide/artifacts/out/de_lm_2m \
  --models "$TEACHER_MODEL,Qwen/Qwen3.5-9B-Base,Qwen/Qwen3.5-4B-Base" \
  --sentences-file wmk-glide/artifacts/out/ab_sentences.tsv \
  --per-class 100 --batch 16 --out /data/out/ab_3way.json

bash wmk-glide/cloud/scaleway/teardown.sh root@<ip>   # down + verify hashes
# only if it printed "artifacts verified" (writes artifacts/teardown-verified):
bash wmk-glide/cloud/scaleway/teardown.sh root@<ip> --terminate <id>
```

Budget: measured **72 min ≈ 1.8 €** on the first run (including four fix
cycles; a clean run is ~50–60 min ≈ 1.4 €). It proves: cloud-init parses,
the vLLM wheel works on the CUDA-13 image, FP8-27B loads on Ada,
`prompt_logprobs` shape/validation, the real Qwen tokenizer mapping,
shard/resume/merge, `check_soft`, prep/train/export and the Rust harness.
It cannot prove the BF16 reference (48 GB) or the H100 timing.

## Cost model

| Item | Value |
|---|---|
| H100-1-80G | €2.8665/h (list "from €2.86/h"), per minute |
| block storage + flexible IP (est.) | €0.02125/h |
| **planning rate** | **€2.88775/h** |
| quick gate (load + 60 s) | ~15–25 min incl. download → **€0.7–1.2** |
| 1.2M at 100 prompts/s | 3.3 h → **~€9.6** |
| 2M at 100 prompts/s | 5.6 h → **~€16** |
| 1.2M at 35 prompts/s | 9.5 h → **~€27** |
| 2M at 35 prompts/s | 15.9 h → **~€46** (over the 12 h rule: stop) |
| student 30k steps (GPU, d256) | ~0.5–1 h |

## Open items

1. **GPU stock** was the blocker all morning; a re-stock on the L40S made the
   teacher A/B possible (30.10., 27 min ≈ 0.66 €, terminated). Only the big
   1.2M/2M run is still waiting for a card.
2. **Teacher A/B measured 30.10.2026** (27B-FP8 / 9B-Base / 4B-Base, 100+100
   fixed sentences, same projection). top-1 chat/news: **35.03/38.30 %** (27B),
   31.29/34.28 % (9B), 29.87/33.07 % (4B); top-8 81.96/85.98 vs 78.61/83.08 vs
   78.47/82.68. The 27B beats the 9B by **+3.74/+4.02 pp** top-1, yet the two
   agree on the top-1 word only 50.2 % of the time. Raw:
   `wmk-glide/artifacts/out/ab_3way.json`; tables in
   `wmlm-training-plan.md` §1.3 and `kb-teacher-models.md` §4a.1.
3. **1.2M on the L40S**: measured 59.45 prompts/s → 5.61 h / **8.25 €** at the L40S rate (16.19 € if you price it at the H100 planning rate; `--eur-per-hour` picks the rate). That is
   above the 35/s gate but below the 100/s "2M" gate, so the 1.2M path is
   the L40S fallback. 2M on the L40S would be 9.34 h / 13.73 € at the L40S rate (over the 6 h
   target, under the 12 h cap).
4. **OpenSubtitles NC licence** decision before publishing a 2M model.
5. `de_lm_2m`'s 20k heldout is drawn by `prep.py` from the mix; the
   shipped 20k heldout (`wmk-glide/artifacts/data/heldout.tsv`) was excluded from
   the corpus, so the published glide/typing baselines stay comparable.
6. **The 1.2M corpus still leaks 12,368 held-out rows** (built by
   `mix_chat_corpus.py` before the key fix). Rebuild it with
   `prepare_2m.py --chat 640000 --news 560000` if that path is taken.
7. **Known accepted risk**: `transfer.sh` uses `StrictHostKeyChecking=accept-new`
   on the first contact with a fresh instance IP (no out-of-band fingerprint
   to compare). Set `SSH_STRICT=1` for repeat runs against a fixed IP once the
   host key is trusted.
8. **Pinning**: the measured stack is vLLM 0.32.0 / torch 2.13.0+cu130 /
   transformers as installed on 30.10.2026. `setup_h100.sh` installs
   unpinned unless `VLLM_SPEC=vllm==0.32.0 TRANSFORMERS_SPEC=transformers==<ver>`
   is passed; `pip-freeze.txt` on the box records what was used.



