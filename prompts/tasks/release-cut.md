# Task: release cut

## Version

- `wmkb.versionName`: <version>
- version code: <code from gradle.properties>
- Channels: <GitHub, F-Droid, Play>

## Note

- File: `release-notes/<version>.md`, `###` sections only.
- Issues that this release closes or moves forward: <links>
- User-visible changes: <list>
- Known limitation that ships with it: <one line or none>

## Store metadata

- Play changelog: `fastlane/metadata/android/en-US/changelogs/<versionCode>.txt`
- F-Droid: the build must compile from source with the `src/nogoogle`
  stand-ins.

## Verification

```sh
./gradlew unitTests -Pwmkb.skipBenchmarks=true --stacktrace
cd docs && npm run check
```

## Halt

Stop when a signing key, the Play service account, or a channel credential is
missing. Report the missing input; never fabricate a signature or a build.

## Handoff

Hand the note, the metadata diff, and the evidence to the operator. Push and
store submission stay with the operator.
