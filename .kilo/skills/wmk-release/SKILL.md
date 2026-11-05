---
name: wmk-release
description: Prepare a WM Keyboard release note, changelog, or store metadata. Use before a version bump, a GitHub release, an F-Droid update, or a Play listing change.
---

# WM Keyboard release

## Read first

- `release-notes/README.md` - one file per `wmkb.versionName`, named
  `<version>.md`, written in `###` sections.
- `gradle.properties` - `wmkb.versionName` and the version code live here.
- `.github/workflows/release.yml` - the release build and the F-Droid parity
  checks.
- `fastlane/metadata/android/en-US/` - the Play listing and per-version
  changelogs.
- `fdroid/` and `play/` - the store-specific metadata and marketing pipeline.

## What a release note contains

- The issue links the release actually closes or moves forward.
- The user-visible change, in the same voice as the app.
- No internal plan IDs, no unverified performance claim, no promise that a
  device build does not keep.
- The fallback is `fastlane/metadata/android/en-US/changelogs/<versionCode>.txt`.
  Use it for a bug-fix release; write a `release-notes/<version>.md` for
  anything larger.

## Commands

```sh
./gradlew unitTests -Pwmkb.skipBenchmarks=true --stacktrace
cd docs && npm run check
```

`scripts/changelog-abi-copies.sh` and `scripts/mirror-releases-to-r2.sh` are
release-time helpers. Read them before running; they move artifacts and are not
part of a normal check.

## Traps

- Never touch `fastlane/play-service-account.json`, keystores, `.jks`, `.p12`,
  `.pem`, or `.env*`. They are ignored on purpose. Report a missing secret
  instead of fabricating a build.
- The F-Droid build compiles `src/nogoogle` and carries no Google library.
  A change that needs an ML Kit API needs a stand-in first.
- F-Droid and the GitHub releases share a signing key from 0.5.10 on. An update
  across a different key is not installable.
- A release note is prose, not a changelog dump. Do not paste commit subjects.

## Done means

- The unit suite and the docs check exit 0.
- The note names the version, the user-visible changes, and the linked issues.
- No secret, no local path, and no unverified number appears in the note.
