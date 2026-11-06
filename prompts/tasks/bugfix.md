# Task: bugfix

## Report

- Symptom: <what the user sees>
- Reproduction: <steps, field type, layout, language>
- Expected: <what should happen>
- Evidence: <log, screenshot, failing test, or commit range>

## Scope

- In: <the smallest module and code path that can cause the symptom>
- Out: refactors, renames, and unrelated cleanups

## Acceptance

- [ ] The reproduction no longer reproduces.
- [ ] A regression test fails before the fix and passes after it, or the report
      explains why a test is not possible.
- [ ] The surrounding behaviour named in the report still holds.

## Verification

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
./gradlew unitTests -Pwmkb.skipBenchmarks=true --stacktrace
```

## Halt

Stop when the symptom is not reproducible, the reproduction needs a device or a
secret you do not have, or the root cause sits in a native library that is
vendored without source. Name the missing input.

## Handoff

One root cause, one fix. Hand the diff and the failing-then-passing evidence to
`review-lead`.
