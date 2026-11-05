---
description: Run the full WM Keyboard verification battery
---

Run the verification battery and report raw evidence:

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
./gradlew unitTests -Pwmkb.skipBenchmarks=true --stacktrace
./gradlew :tools:architecture:test
cd docs && npm ci && npm run check
```

Add `./gradlew staticAnalysis` when the change touches Kotlin sources that
detekt or Android Lint can see. Add the matching `assemble*Debug` when the
change touches build logic, resources, or a native gate.

A pass is a record: command, exit code, and the output line that proves it. If a
command was not run, mark it unverified.
