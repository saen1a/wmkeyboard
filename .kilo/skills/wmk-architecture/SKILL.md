---
name: wmk-architecture
description: Respect WM Keyboard's module layering and house rules. Use before adding a module, moving a class across modules, changing a build flag, or editing a src/google surface.
---

# WM Keyboard architecture

## Layers

`settings.gradle.kts` is the authority. The intended direction is one-way:

- `core/config` carries the build flags and API keys.
- `core/common` holds shared utilities.
- `core/*` feature areas sit above those.
- `feature/*` sit above `core/settings`; `feature/ime` is the keyboard runtime.
- `app` composes the modules and the Play dynamic features.
- `tools/dictc` and `tools/architecture` are build-time or test-only.

Nothing points upward. A new dependency that reverses an edge needs an
explicit decision, not a workaround.

## House rules

- `tools/architecture` is a Konsist suite for rules the compiler cannot see:
  F-Droid stand-ins, key-grid recomposition, dictionary compiler inputs.
- `config/detekt/detekt.yml` is the curated detekt ruleset. `staticAnalysis`
  runs detekt with type resolution plus Android Lint.
- `native/gates.json` drives the native gates, the Play feature modules, the
  dynamic features, and the ProGuard keeps. Add a gate to that file, not to
  four separate lists.

## Commands

```sh
./gradlew :tools:architecture:test
./gradlew staticAnalysis
./gradlew :app:checkDexMethodsEnFast
```

`checkDexMethodsEnFast` guards the ART limits: no method of 10,000 or more dex
instructions, and no frame over 3 KB in the slow interpreter. A compile pass
does not prove either.

## Traps

- `src/main` must compile against both `src/google` and `src/nogoogle`. A name
  used by `src/main` has to exist on both sides. The F-Droid assemble is the
  only build that compiles the stubs.
- A `src/nogoogle` file with no `src/google` file at the same path is drift.
- A Play-only dynamic feature module must not be included when the Play channel
  is off; it cannot resolve its own `featureName`.
- Konsist scopes production sources to `app/src`, `core`, `feature`, and
  `tools`. Session worktrees under `.kilo/worktrees/` are separate checkouts,
  not source of the module you are testing.

## Done means

- `./gradlew :tools:architecture:test` exits 0.
- `./gradlew staticAnalysis` exits 0 for a detector-visible change.
- For a native-gate change, the matching `assemble*Debug` still packages and
  the F-Droid variant still compiles.
