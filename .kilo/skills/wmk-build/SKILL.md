---
name: wmk-build
description: Build, test and lint WM Keyboard with Gradle. Use when choosing a task, reproducing CI, or a build failure looks like a toolchain or flavor problem rather than a code problem.
---

# WM Keyboard build and test

## Read first

- `README.md`, sections "Builds" and "Build it yourself".
- `.github/workflows/ci.yml` is the source of truth for CI.
- `settings.gradle.kts` for the module list and the channel flags.

## Prerequisites

- A JDK 17 or newer to launch Gradle. CI uses JDK 21.
- The Android SDK with `compileSdk 37`.
- Gradle provisions its own toolchain through Foojay on the first build.

## Commands

Run from the repository root, or from the worktree you are editing.

```sh
./gradlew assembleIntlDebug       # every UI language
./gradlew assembleEnDebug         # English UI only
./gradlew assembleEnDebug -Pwmkb.enableFdroid=true
./gradlew unitTests -Pwmkb.skipBenchmarks=true
./gradlew staticAnalysis          # detekt + Android Lint; 20+ minutes
./gradlew :tools:architecture:test
./gradlew :app:checkDexMethodsEnFast
./gradlew :app:licenseeAndroidIntlRelease
```

CI parity flags:

```sh
WMKB_ENABLE_PLAY_STORE=false WMKB_ENABLE_GMS=false
```

The flag precedence is `-P`, then `local.properties`, then the environment,
then the default.

## Traps

- Use the aggregate `unitTests`, not `testIntlDebugUnitTest`. `:app` carries the
  `languages` flavor and the library modules do not, so no single flavored task
  name reaches both.
- The flavor names are capitalised in task names: `assembleIntlDebug`,
  `assembleEnDebug`. The APK lands under `app/build/outputs/apk/<flavor>/debug/`.
- `-Pwmkb.enableFdroid=true` compiles the `src/nogoogle` stand-ins and drops
  Google's SDKs. It is the only build that compiles them, so an F-Droid failure
  is usually a stub that drifted from `src/google`.
- `staticAnalysis` is slow by design. Do not replace it with the source-only
  `detekt` task and call the gate green.
- Every managed worktree under `.kilo/worktrees/` is a separate checkout. Run
  the command in the worktree whose branch you are testing.

## Done means

- `cargo test --release --manifest-path native/wm-engine/Cargo.toml` exits 0.
- `./gradlew unitTests -Pwmkb.skipBenchmarks=true --stacktrace` exits 0.
- For a UI or build-logic change, the matching `assemble*Debug` task exits 0.
- Paste the command, exit code, and the failing test name when one fails. A
  summary without output is not evidence.
