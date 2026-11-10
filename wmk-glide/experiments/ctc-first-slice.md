# CTC first slice: FUTO Swipe on German HeliBoard strokes

Observed 2026-11-10. Decision: **NO-GO for the FUTO model as-is.** The tooling
and assets are no longer blockers; the English-trained encoder is 9.21 pp behind
the GlideBeam German profile on the same German strokes.

## What ran

- **Slice:** HeliBoard German `de-1` + `de-2`, a-z single-pointer targets,
  16,081 eligible strokes, 1,000 sampled with seed 20261109 across 76
  keyboard geometries. Word list: `de_aosp.txt.gz`.
- **Emissions:** `native/bench/futo-swipe/emit.py` with the FUTO encoder and
  decoder, per geometry, as the app computes them.
- **CTC decode:** `native/wm-engine/examples/ctc_glide_eval` bare mode (no
  marks, look-ahead or shapes), default `Scoring`, German word list.
- **GlideBeam baseline:** the same group's records/layout with the German
  profile (`freq_weight=0.75 gap_weight=2.0 join_cost=8 join_min_part=4
  join_part_penalty=0.1`), same in-list filter.

Both sides keep the 999 strokes whose word the list holds (one of the 1,000 is
unlisted), so the denominator is identical.

## Result

| Decoder | Top-1 | Top-4 |
|---|---:|---:|
| **GlideBeam, German profile** | **78.78** | **91.49** |
| FUTO CTC (bare, default scoring) | 69.57 | 81.98 |
| Delta | **−9.21 pp** | **−9.51 pp** |

The CTC loses on the aggregate and on the large geometries; it is not a
candidate for a straight swap. The gap is a model/domain gap, not a missing
runtime: the FUTO encoder was trained on English FUTO swipes, and the German
HeliBoard strokes are a different corpus, layout and language.

## Assets (external, not committed)

| Item | Size | SHA-256 |
|---|---:|---|
| `honorable_sturgeon_model_fp32.pte` | 2,649,856 B | `725242ba…` |
| `magic_macaw_model_fp32.pte` | 1,247,468 B | `01eaf16a…` |
| HeliBoard `de-1.gestures.json.zst` | 8,077,930 B | `cb242f53…` |
| HeliBoard `de-2.gestures.json.zst` | 7,516,255 B | `e6f84463…` |
| `de_aosp.txt.gz` | 1,101,134 B | `53588263…` |

Models: `huggingface.co/futo-org/futo-swipe` at
`18328c3042b066952c0936b3771d492fe2ec289a`. Strokes: HeliBoard gesture data,
CC BY-SA 4.0. Host runtime: `executorch` 1.6.0+cpu, `torch` 2.15.0+cpu,
Python 3.14.

## Why the earlier block is closed

The previous note listed ExecuTorch, the FUTO encoder/decoder, the HeliBoard
German archives, the conversion scripts and a pinned baseline as missing. All
five are now resolved:

- ExecuTorch installs for the host Python and loads both `.pte` programs.
- The FUTO weights download at the pinned revision.
- HeliBoard's German archives are public and convert with
  `wmk-glide/experiments/heliboard_slice.py`.
- `native/bench/futo-swipe/emit.py` is the converter; no separate
  `emit_heliboard.py` is needed.
- The baseline is the GlideBeam German profile on the same in-list strokes.

The remaining work is model work: a German-trained encoder or fine-tune, and a
German scoring sweep (`FW`, `LN`, `LB`, `LAC`). That is a training project, not
a blocked toolchain.

## Caveats

- FUTO model weights are under the FUTO Model Weights License 1.0; nothing was
  committed.
- One 1,000-stroke slice; no German training, no per-language CTC scoring
  sweep, no on-device latency.
- The bare decoder is the comparison point; marks/look-ahead/shapes were not
  run because they cannot recover a 9-point model gap.

## Reproduction

```sh
# 1. assets
R=18328c3042b066952c0936b3771d492fe2ec289a
curl -L -o honorable_sturgeon_model_fp32.pte \
  https://huggingface.co/futo-org/futo-swipe/resolve/$R/honorable_sturgeon/model_fp32.pte
curl -L -o magic_macaw_model_fp32.pte \
  https://huggingface.co/futo-org/futo-swipe/resolve/$R/magic_macaw/model_fp32.pte
# HeliBoard de batch_1 de-1/de-2 and data/de/de_aosp.txt.gz, then:
python3 -m pip install --user --break-system-packages executorch torch numpy

# 2. slice (from the repo root)
python3 wmk-glide/experiments/heliboard_slice.py --lang de --alphabet az \
  --out /tmp/slices/de --list /tmp/de_aosp.txt /tmp/de/de-1 /tmp/de/de-2

# 3. emissions, per geometry
cd native/bench/futo-swipe
for g in /tmp/slices/de/g*; do
  python3 emit.py "$g/records.jsonl" "$g/layout.json" /tmp/ctc "/tmp/ctc/$(basename "$g").bin"
done

# 4. CTC vs GlideBeam
cd ../..
python3 wmk-glide/experiments/heliboard_ctc_eval.py \
  --slices /tmp/slices/de --bins /tmp/ctc --list /tmp/de_aosp.txt \
  --ctc target/release/examples/ctc_glide_eval \
  --beam target/release/examples/glide_beam_eval \
  --out /tmp/ctc-de.json
```
