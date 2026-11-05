---
description: Build one WM Keyboard variant with the right flags
---

Variant: $ARGUMENTS

Pick the task from the request:

- every UI language: `./gradlew assembleIntlDebug`
- English only: `./gradlew assembleEnDebug`
- F-Droid parity: `./gradlew assembleEnDebug -Pwmkb.enableFdroid=true`

Use CI flags `WMKB_ENABLE_PLAY_STORE=false WMKB_ENABLE_GMS=false` unless the
request is explicitly a Play build. Report the task, the exit code, and the APK
path (`app/build/outputs/apk/<flavor>/debug/`). If the build fails in a
`src/nogoogle` stub, say so and route the fix to the Kotlin path.
