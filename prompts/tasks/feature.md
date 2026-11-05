# Task: feature

## Goal

<one sentence: the user-visible behaviour after the change>

## Scope

- In: <paths and modules>
- Out: <paths and modules that must not change>
- One writer per shared surface. No parallel edits to the same files.

## Acceptance

- [ ] <observable behaviour, including the field or screen>
- [ ] <unchanged behaviour that must still hold>
- [ ] <F-Droid variant still compiles, if the change touches a Google surface>

## Verification

```sh
cargo test --release --manifest-path native/wm-engine/Cargo.toml
./gradlew unitTests -Pwmkb.skipBenchmarks=true --stacktrace
./gradlew :tools:architecture:test
```

Add the matching `assemble*Debug` and `./gradlew staticAnalysis` when the change
touches build logic or detector-visible Kotlin.

## Halt

Stop and report with at most three questions when:

- the acceptance criteria are not decidable from the request;
- a shared surface needs a second writer;
- the change needs a new native dependency or a new gate;
- the F-Droid stand-in path has no obvious match.

## Handoff

Implement, then hand the diff and the evidence to `review-lead`. The operator
owns Push.
