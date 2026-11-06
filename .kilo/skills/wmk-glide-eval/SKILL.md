---
name: wmk-glide-eval
description: Run or extend the German glide and context-model research. Use for wmk-glide measurements, WMLM training, swipe-CTC experiments, or before claiming an accuracy number.
---

# WM glide and context-model research

## Read first

- `wmk-glide/state.md` is the measured state and the reproduction index. Start
  there, not at a blog post or a summary.
- `wmk-glide/README.md` maps every artifact and tool.
- `wmk-glide/experiments-followup.md` records what was tested and rejected.
- `tools/wmlm/README.md` is the context-model training recipe.
- `tools/swipe-ctc/README.md` is the geometry-conditioned CTC encoder.

The research notes are partly German. That is data. Agent output stays English.

## Harness

- `native/wm-engine/examples/glide_beam_eval.rs` - the beam eval harness.
- `native/wm-engine/examples/ctc_glide_eval.rs` - the CTC encoder eval.
- `native/wm-engine/examples/typing_eval.rs` - the tap harness.
- `wmk-glide/tools/harness.patch` - the patch that adds `COLS`, `ALL`, `DUMP`,
  `RESULTS`, `SHAPES` to the beam harness.
- `wmk-glide/patches/` - the app patches against the recorded upstream commit.

## Reproduction commands

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
python -m compileall -q wmk-glide/tools
python -c "import json; json.load(open('wmk-glide/data/wmk-settings-de-optimized.wmconfig.json', encoding='utf-8'))"
python -c "import zipfile; z = zipfile.ZipFile('wmk-glide/data/wmk-glide-de-data.zip'); assert z.testzip() is None"
```

The per-experiment commands and their corpora are in `wmk-glide/state.md`.
Copy the command from there instead of reconstructing it.

## Measurement rules

- A before and after must use the same corpus, layout, and settings. Otherwise
  it is two unrelated numbers.
- "Top-1 success per stroke" is the headline metric. Name the corpus and the
  list size with it.
- In-sample gains from a blend are not device gains. Say which one you measured.
- A number with no artifact in `wmk-glide/` or a missing command in `state.md`
  is unverified. Do not promote it into a summary.

## Scope

- Research code stays under `wmk-glide/**` and `tools/`.
- A production decoder change needs a separate spec against
  `native/wm-engine/**` and the `wmk-native-engine` agent.
- Never overwrite an artifact that a `state.md` section pins.
