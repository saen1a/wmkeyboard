---
description: Run the WM Keyboard unit and native tests
---

Run the project test gate from the repository root:

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
./gradlew unitTests -Pwmkb.skipBenchmarks=true --stacktrace
```

Report each command, its exit code, and the failing test names. Do not summarise
a failure as "some tests failed"; name the test and the assertion. If a failure
is environmental (missing SDK, stale host library), say which and stop.
