---
description: Check or advance the glide and WMLM research
---

Research scope: $ARGUMENTS

Read `wmk-glide/state.md` first. Treat its measured numbers as the baseline.
Keep research code under `wmk-glide/` and `tools/`. Run the reproduction check:

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
python -m compileall -q wmk-glide/tools
python -c "import zipfile; z = zipfile.ZipFile('wmk-glide/data/wmk-glide-de-data.zip'); assert z.testzip() is None"
```

A before and after must use the same corpus, layout, and settings. If it does
not, label it unverified. A production decoder change needs a separate spec.
