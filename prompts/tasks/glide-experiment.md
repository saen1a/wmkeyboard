# Task: glide experiment

## Question

<one measurable question, for example: does a language profile raise top-1 on
the FUTO German corpus without lowering English>

## Baseline

- Corpus: <name, size, layout>
- Settings: <the shipped defaults or the named profile>
- Number: <the value in wmk-glide/state.md, with its section>

## Change

- Artifact: <patch, script, or parameter sweep>
- Scope: `wmk-glide/**` and `tools/**`; a production change needs a separate
  spec against `native/wm-engine/**`.

## Acceptance

- [ ] The same corpus, layout, and settings are used for both arms.
- [ ] The before, after, and delta are recorded with the command that produced
      them.
- [ ] A negative result is recorded as a negative result.
- [ ] The change is reproducible from a clean checkout.

## Verification

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
python -m compileall -q wmk-glide/tools
python -c "import zipfile; z = zipfile.ZipFile('wmk-glide/data/wmk-glide-de-data.zip'); assert z.testzip() is None"
```

## Halt

Stop when the corpus is not available, when the harness cannot reproduce the
baseline, or when the comparison would use a different corpus or settings.

## Handoff

Report to the requesting session. Research does not edit the production decoder.
