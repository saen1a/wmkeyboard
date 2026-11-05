---
name: wmk-native-engine
description: Work on the Rust text engine and its JNI bridge. Use when touching native/wm-engine, native/wm-engine-jni, a native gate, or when a JVM test cannot load the engine.
---

# WM native engine

## Layout

- `native/wm-engine/` - the pure Rust engine: prediction, glide, transliteration,
  dictionaries, context model, segmentation.
- `native/wm-engine-jni/` - the Android JNI bridge. `build.sh` cross-compiles for
  the device; `build-host.sh` builds the host library the JVM tests load.
- `native/gates.json` - the one list of on-demand native gates. Gradle and
  `native/gates.py` both read it.
- `native/build-lite-libs.sh`, `native/build-fdroid-libs.sh` - the two library
  build paths.
- `native/RUST_NEON_PLAN.md` - the NEON plan and its constraints.

## Commands

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
native/wm-engine-jni/build-host.sh
cargo build --release --locked --manifest-path native/wm-engine-jni/Cargo.toml
```

The Gradle test tasks of the modules that touch the engine run
`build-host.sh` first. If you run a JVM test directly, build the host library
yourself.

## Engine tests that catch real regressions

- `native/wm-engine/tests/glide_join.rs`
- `native/wm-engine/tests/glide_freq_weight.rs`
- `native/wm-engine/tests/glide_long_words.rs`
- `native/wm-engine/tests/segment_eval.rs`

Do not delete or weaken a failing test to make the suite green. Record the
failure and the measurement that explains it.

## Traps

- The engine must stay free of Android-only APIs. The same crate serves the app
  through JNI and the desktop daemon.
- The host build is found by walking up from the test working directory to
  `settings.gradle.kts`, under `native/wm-engine-jni/target/release`. A stale
  library shadows a fresh `cargo build`.
- Adding a native dependency or a gate needs an entry in `native/gates.json`
  and a check that the F-Droid build can make or omit it.
- `target/` and `**/target/` are ignored. Never commit build output.

## Done means

- The Rust test command exits 0.
- `build-host.sh` prints the produced library path and size.
- The JVM module that loads the engine still passes its tests.
