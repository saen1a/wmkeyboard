# Clipboard matrix test plan

Status: Plan, PlanReview clean, awaiting operator go.
Scope: local JVM/Robolectric tests, static APK/manifest audits, and emulator instrumentation for the clipboard and autofill matrix.

## Goal

Add a no-physical-Samsung-device test matrix that closes the protocol, configuration, backup and API-level risks of the clipboard refactor with local JVM/Robolectric tests plus emulator instrumentation, without claiming Samsung One UI coverage. The pre-flight probe is `emulator -list-avds` plus `sdkmanager --list_installed`; missing emulator, image or cmdline-tools is a HALT, not an assumption.

## Scope boundaries

- in scope: pure JVM contract tests, Robolectric API-36 tests, manifest/backup/APK audits, a test-only fake autofill provider, emulator instrumentation for Android 16 and 17, and an emulator/manual matrix for Bitwarden, Proton Pass and passkeys.
- in scope, narrowly: extracting testable pure functions only: the inline-suggestion classifier, the secure-window predicate, and one `ClipboardSyncSanitizer` after explicit operator authorization.
- out of scope: Galaxy S26 Ultra and Samsung One UI vendor clipboard behavior, production cloud device-farm setup, real Proton Pass redistribution, and any other production behavior change.

## Request coverage

R9 and R10 are cross-cutting process constraints. Every other request item maps to exactly one unit.

| Request item | Unit | Why |
|---|---|---|
| R1: test inline-autofill budgets, lanes and no chip content | T1 | T1 is the pure inline-classifier contract suite. |
| R2: audit the merged manifest, backup rules and SDK levels | T2 | T2 owns the static configuration audit. |
| R3a: test the existing restore boundary against a legacy snapshot | T3 | T3 covers the behavior that exists today. |
| R3b: test a new pure sync/ConfigBackup sanitizer | T3B | T3B owns the sanitizer extraction and crafted-bundle tests. |
| R4: test the `FLAG_SECURE` decision without a window | T4 | T4 extracts and tests the secure-window predicate. |
| R5: run API-36 Robolectric coverage for clipboard and direct boot | T5 | T5 owns API-36 JVM tests. |
| R6: test a fake inline provider on an emulator | T6 | T6 owns the fake provider and its instrumentation test. |
| R7: test `FLAG_SECURE`, direct boot and backup on an emulator | T7 | T7 owns the emulator runtime checks. |
| R8: record real Bitwarden, Proton Pass and passkey behavior on an emulator | T8 | T8 is the emulator/manual real-app matrix. |
| R9: use the PlanReview, Implement, Review, Fix, Verify loop | T1, T2, T3, T3B, T4, T5, T6, T7, T8 | The loop governs every unit. |
| R10: keep Samsung One UI evidence separate from local claims | T8 | T8 records the external/manual boundary explicitly. |

## Units

| Unit | Acceptance | Verification | Owner |
|---|---|---|---|
| T1 | MUST: a pure classifier over source/type/budgets is extracted and `InlineAutofill.split` delegates to it; MUST: zero budgets, autofill/platform lanes, 6+3 caps and unknown sources are tested; MUST: the test passes no chip content; SHOULD: the exact budget constants are named | `./gradlew :feature:ime:testDebugUnitTest` | wmk-kotlin-engineer |
| T2 | MUST: the audit binds the IME service node and fails on `android:process` or `isolatedProcess`; MUST: it checks `directBootAware`, `method.xml` `supportsInlineSuggestions`, no `ACCESS_LOCAL_NETWORK` while target is 36, backup rules excluding `clipboard`, and targetSdk 36; MUST: compileSdk 37 is read from `app/build.gradle.kts` as a named source check; SHOULD: the merged APK is also audited | `./gradlew :app:testIntlDebugUnitTest` | wmk-kotlin-engineer |
| T3 | MUST: the existing restore path drops sensitive items and items whose kind lacks its required path; MUST: a corrupt snapshot is deleted; MUST: an external reload merge and delete are covered; SHOULD: no production change is made for this unit | `./gradlew :app:testIntlDebugUnitTest` | wmk-kotlin-engineer |
| T3B | MUST: `ClipboardSyncSanitizer` is extracted only after operator authorization; MUST: it takes the raw `JsonElement`/text before typed decode and validates each item, so missing id/timestamp is a per-item drop, not a whole-file failure; MUST: crafted bundles with `sensitive`, `imagePath`, `uriString`, `fileName`, `linkPreview`, missing id/timestamp, oversized text or a secret shape are dropped; MUST: benign text survives; MUST: the sanitizer and its tests live in `core/content`; SHOULD: it is pure and Android-free | `./gradlew :core:content:testDebugUnitTest` | wmk-kotlin-engineer |
| T4 | MUST: the secure-window predicate is true for a password field, incognito and a clipboard panel holding a secret; MUST: it is false for a clear field and a clear panel; SHOULD: the predicate is pure and unit-tested without a Window | `./gradlew :feature:ime:testDebugUnitTest` | wmk-kotlin-engineer |
| T5 | MUST: API-36 tests use `@Config(sdk = [36])` in the feature test source set and cover the sensitive flag, clipboard extras and the device-protected palette context; MUST: the run fails loudly if the 36 jar is unavailable rather than silently using 34; SHOULD: API-34 tests remain green | `./gradlew :feature:ime:testDebugUnitTest` | wmk-kotlin-engineer |
| T6 | MUST: a test-only `AutofillService`/`InlineSuggestionsService` returns deterministic inline chips; MUST: the instrumentation test asserts lane budgets and a locked-vault empty response; MUST: no real credential is used; SHOULD: the fake provider is debug-test only. This proves chip plumbing, not passkey behaviour | `./gradlew :app:connectedIntlDebugAndroidTest` | wmk-kotlin-engineer |
| T7 | MUST: the emulator test reads the `FLAG_SECURE` window attribute with `dumpsys window` or a documented in-process service seam, not a blank-screenshot assertion; MUST: `bmgr`/backup inspection shows `clipboard/` excluded, with the static backup-rules check as the fallback when no transport is configured, recorded as static evidence rather than device-proven; MUST: a named manual locked-boot procedure is recorded; SHOULD: run on API 36 and 37 images | `./gradlew :app:connectedIntlDebugAndroidTest` | wmk-kotlin-engineer |
| T8 | MUST: the matrix document `docs/src/content/docs/development/clipboard.md` contains Bitwarden Inline/Popup, Proton Pass Inline/Popup, locked vault, passkey and incognito rows; MUST: the matrix states which rows are emulator, cloud or Samsung-only; MUST: `review-lead` verifies the document, not the author; MUST: the locked-vault row uses a throwaway test account or a simulated locked provider, never a real vault; SHOULD: no real credential is used; SHOULD: the docs build passes (`npm run check`) | `docs/src/content/docs/development/clipboard.md` | wmk-release-engineer |

## Ownership and order

One writer for the test and extraction work: `wmk-kotlin-engineer`. T8 is a separate manual/emulator verification owner, `wmk-release-engineer`, verified by `review-lead`. No two units edit the same test file at the same time.

1. `T1` - one writer: `wmk-kotlin-engineer`; pure inline-classifier extraction and contract tests first.
2. `T2` - one writer: `wmk-kotlin-engineer`; static configuration audit next.
3. `T3` - one writer: `wmk-kotlin-engineer`; existing restore-boundary tests.
4. `T3B` - one writer: `wmk-kotlin-engineer`; sanitizer extraction only after explicit operator authorization.
5. `T4` - one writer: `wmk-kotlin-engineer`; secure-window predicate extraction and test.
6. `T5` - one writer: `wmk-kotlin-engineer`; API-36 Robolectric tests after T1-T4.
7. `T6` - one writer: `wmk-kotlin-engineer`; fake provider instrumentation after T1 and T5.
8. `T7` - one writer: `wmk-kotlin-engineer`; emulator runtime checks after T4 and T6.
9. `T8` - one writer: `wmk-release-engineer`; real-app and One UI boundary after T6-T7; reviewed by `review-lead`.

## Risks and halts

| Risk | Halt path | Operator question |
|---|---|---|
| No emulator, system image or cmdline-tools is installed | HALT before T6 and T7; run `emulator -list-avds` and `sdkmanager --list_installed` first | Install the emulator and API 36/37 images, or accept local-only tests? |
| Robolectric 4.17 has no API-36 or exact compileSdk-minor `android-all` jar | HALT before T5 | Download the exact jar, or move T5 to an emulator? |
| Extracting `ClipboardSyncSanitizer` is a production change not yet authorized | HALT T3B | Authorize one pure sanitizer extraction, or keep only the existing restore tests? |
| Android 17 system image is unavailable | HALT T7 API-37 portion | Run API 36 only, or keep API 37 as a static audit? |
| Proton Pass APK cannot be obtained or tested under its licence | HALT T8 Proton rows | Use the fake provider only, or approve a licensed test APK? |
| Bitwarden or a passkey provider cannot be installed on the emulator | HALT T8 Bitwarden/passkey rows | Use the fake provider only, or approve an emulator/manual provider build? |
| Instrumentation cannot run before first unlock | HALT the pre-unlock T7 assertion | Keep direct boot as a named manual procedure, or use a dedicated locked-boot harness? |
| Samsung One UI/S26 cannot be reproduced locally | HALT the S26 claim | Use Samsung Remote Test Lab, Firebase Test Lab, or a manual user test? |
| Test-only autofill service activation needs shell/adb privileges | HALT T6 | Use an emulator with test automation privileges, or keep the provider manual? |
| Emulator CI is slow or flaky | HALT the CI gate | Make the emulator job optional, or require it on release branches? |

## Ready gate

No test code or production extraction is written until the PlanReview verdict is clean. The loop then runs:

Plan -> PlanReview -> Implement one unit -> Review -> Fix -> Verify -> stop at Ready for Push.
