# wmkeyboard agent router

Owner: the repository maintainer. Update this file when a build, test, or
layout change makes a command below wrong.

## Commands

Run from the repository root, or from the worktree you are editing.

```sh
./gradlew assembleIntlDebug        # build every UI language
./gradlew assembleEnDebug          # build English UI
./gradlew assembleEnDebug -Pwmkb.enableFdroid=true
./gradlew unitTests -Pwmkb.skipBenchmarks=true   # JVM suite
cargo test --release --manifest-path native/wm-engine/Cargo.toml
./gradlew staticAnalysis           # detekt + Android Lint, slow
./gradlew :tools:architecture:test
(cd docs && npm ci && npm run check)
```

Single test: `./gradlew :app:testIntlDebugUnitTest --tests '<class>'`.

## Conventions

- JDK 17+ to launch Gradle. CI uses JDK 21 and Android `compileSdk 37`.
- Flavor names are `intl` and `en`; task names capitalize them.
- Use `unitTests`, not a flavored test task: `:app` carries the `languages`
  flavor and the library modules do not.
- `src/main` compiles against both `src/google` and `src/nogoogle`. The F-Droid
  build is the only one that compiles the stubs, so a stub must mirror the
  `src/google` API.
- The Rust engine stays Android-free; the JNI bridge owns the Android boundary.
- Native gates live in `native/gates.json`, one list for Gradle and the shell.
- Worktrees under `.kilo/worktrees/` are separate checkouts. Run a command in
  the worktree whose branch you are testing.
- Prompts, agents, skills, and commit messages are English and ASCII. The
  `wmk-glide/` research notes may be German; agents still reply in English.
- Do not touch `fastlane/play-service-account.json`, keystores, `.env*`, or
  `local.properties`.

## Verification

- Done means the commands that match the change exit 0 and the plan review is
  clean. Evidence is the command and its exit code, not a summary.
- Full gate: `python -m pip install 'PyYAML>=6'` once, then
  `python scripts/verify-agent-pack.py`, plus the matching build and test
  commands above. CI runs the same gate in `.github/workflows/agent-pack.yml`.
- Skipped work is unverified. Say so instead of implying a pass.

## Pointers

- Agent rules: `.kilo/agents/` (generated from `packs/wmkeyboard/agents.yaml`)
- Skills: `.kilo/skills/` (library canon plus project skills)
- Prompts: `prompts/`
- Library canon: `vendor/agent-prompts/` (never edit)
- Adoption record: `packs/wmkeyboard/README.md`
- CI gates: `.github/workflows/ci.yml`
- Docs contract: `docs/CONTENT_GUIDE.md`
- Glide state: `wmk-glide/state.md`
- Native plan: `native/RUST_NEON_PLAN.md`
