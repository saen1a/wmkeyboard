# Task: native engine change

## Goal

<the engine behaviour that changes, and for which caller>

## Scope

- In: `native/wm-engine/**`, `native/wm-engine-jni/**`, and their tests
- Out: Kotlin facades, which belong to `wmk-kotlin-engineer`
- One writer. The engine has no parallel-writer exception.

## Acceptance

- [ ] <decoder, transliteration, dictionary, or segmentation behaviour>
- [ ] The engine stays free of Android-only APIs.
- [ ] A native gate or dependency change is recorded in `native/gates.json`
      and does not break the F-Droid build.
- [ ] The public JNI surface either stays source-compatible or carries a
      migration note.

## Verification

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
native/wm-engine-jni/build-host.sh
cargo build --release --locked --manifest-path native/wm-engine-jni/Cargo.toml
```

Then run the JVM suite that loads the host library.

## Halt

Stop when the change needs an upstream dependency the F-Droid build cannot
carry, when the host build cannot load, or when the acceptance number depends on
a corpus that is not in the repository.

## Handoff

Hand the diff, the test names, and the host-build output to `review-lead`.
