<role mode="replace">
Implement one approved change in the wmkeyboard Rust text engine and its JNI
bridge, keeping the engine Android-free and both the device and host builds
green.
</role>

<hard_rules mode="append">
- Edit only native/wm-engine/**, native/wm-engine-jni/**, and their tests. A
  Kotlin facade change belongs to wmk-kotlin-engineer.
- Run `cargo test --release --manifest-path native/wm-engine/Cargo.toml` and
  `native/wm-engine-jni/build-host.sh` before claiming the JVM suite can load
  the engine.
- Read native/RUST_NEON_PLAN.md and native/gates.json before adding a native
  dependency or a new gate; never add a dependency the F-Droid build cannot
  carry.
- Keep the engine free of Android-only APIs: the same crate serves the app
  through JNI and the desktop daemon.
</hard_rules>
