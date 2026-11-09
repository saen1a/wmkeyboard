---
title: "Clipboard system"
description: "How WM Keyboard captures, stores, and pastes clips, and why Android has no replaceable clipboard provider."
sidebar:
  order: 8
---

WM Keyboard's clipboard tool is a history and a paste surface on top of Android's
system clipboard. It is not a replacement for the clipboard service. This page
shows the components, the data flow, and the platform boundary, including what
that boundary means on a Samsung Galaxy S26 Ultra running One UI.

## System overview

| Actor | Role |
|---|---|
| Foreground app | Puts clips on the system clipboard and pastes from it through `ClipboardManager`. |
| Android clipboard service | Runs inside `system_server`, owns the one primary clip, and enforces who may read it. |
| WM Keyboard IME service | A default input method when selected. It listens for clip changes, feeds the history, and pastes clips into the focused field. |
| Clipboard panel and tools | Compose UI for search, pinning, tagging, editing, entity chips, link previews, and rich media. |
| One UI clipboard | Samsung's vendor history, stored by Samsung Keyboard. It is separate from both the AOSP clipboard and the WM Keyboard history. |

The important split is between three stores:

1. **The system clipboard** is the single `ClipData` in `system_server`. Every
   app's normal copy and paste goes through it.
2. **The WM Keyboard history** is the app-private JSON store under
   `filesDir/clipboard/history.json`, with copied images under
   `filesDir/clipboard/images/`.
3. **The Samsung clipboard history** is One UI data owned by Samsung Keyboard.
   WM Keyboard has no public API for it.

WM Keyboard can be the default keyboard. It cannot be the default clipboard
provider, because Android has no such role.

## System diagram

```text
                        +--------------------------------------+
                        |           Foreground app             |
                        |  copy: setPrimaryClip(ClipData)      |
                        |  paste: getPrimaryClip()             |
                        +------------------+-------------------+
                                           |
                                           v
                        +--------------------------------------+
                        | Android clipboard service            |
                        | system_server                        |
                        | one primary ClipData                 |
                        | read gate: focused uid or default IME|
                        +------------------+-------------------+
                                           |
                     onPrimaryClipChanged  |  getPrimaryClip()
                                           v
                        +--------------------------------------+
                        | WM Keyboard IME service              |
                        | WMKeyboardService                    |
                        | listener + paste handlers            |
                        | ClipboardWriteGate: every write      |
                        +------------------+-------------------+
                                           |
                    +----------------------+----------------------+
                    |                                             |
                    v                                             v
      +-----------------------------+               +-----------------------------+
      | ClipboardStore              |               | InputConnection             |
      | clipboard/history.json      |               | commitText / commitContent  |
      | clipboard/images/           |               |                             |
      +-----------------------------+               +-----------------------------+

      +--------------------------------------------------------------+
      | One UI clipboard history                                     |
      | Samsung Keyboard data, for example ClipItem.db               |
      | Not readable or writable through the Android SDK             |
      +--------------------------------------------------------------+
```

## Architecture

The clipboard code is split across four layers.

### Presentation

`ClipboardFields.kt` holds the panel cells: search, entity chips, history,
grid or list switch, and the clip editor. `KeyboardScreen.kt` mounts the panel
for `PanelMode.CLIPBOARD`. `ClipboardPanelHost` and the panel layout system
decide where each cell is drawn. The panel reads `KeyboardUiState.clipboardItems`
and sends every action back to the service.

### Application service

`WMKeyboardService` is the coordinator. It owns the clipboard listener, the
settings gates, the paste routing, the password sweep, and the interaction with
other features such as the suggestion strip, the AI reply tool, Send, and KDE
Connect.

`ClipboardWriteGate` is the one write path for keyboard-originated system
clipboard writes: panel copies, tool copies, clean-text write-back, Clear, and
Undo restores. It marks a clip sensitive when the caller says so, lets
`KeyboardClipboard` keep a private copy in memory, and stamps a short-lived
self-write token from `SelfWriteLedger` so the listener can tell the keyboard's
own write apart and not record it twice. An architecture test fails a new
direct `setPrimaryClip` or `clearPrimaryClip` call under `feature/ime`.

A few controllers, such as the gallery, music, Send, and share paths, still read
the system clipboard directly. Their writes go through `ClipboardWriteGate` as
well, so sensitivity and self-write handling keep one owner.

### Domain

`ClipboardStore` is the history model. It stores `ClipItem` records with a
`ClipKind` of `TEXT`, `HTML`, `LINK`, `IMAGE`, `FILE`, `FOLDER`, or `VIDEO`.
It also owns expiry, the unpinned entry cap, pinning, ordering, tagging,
editing, detach and reattach for Undo, and search matching. Related pure logic
lives beside it: `ClipCopyRules`, `ClipSensitivity`, `ClipLinks`, `ClipEntities`,
and `PhoneFormats`.

`KeyboardClipboard` is a small process-wide object for private text copies.
When private mode is on, a copy made through `KeyboardClipboard.copy` stays in
memory and never reaches the system clipboard. The service is told through
`onPrivateCopy`, so the history can record it outside incognito. Incognito
records nothing.

`ClipboardSyncSanitizer` is the untrusted-bundle boundary for ConfigBackup and
the Sync devices path. It accepts only complete, non-sensitive text, HTML, and
link items within the store's hard caps, drops one crafted or corrupt item on
its own instead of failing the whole restore, and never carries a local secret
forward.

`SecretMemoryStore` is the memory-only home for sensitive clips. It has no
file, no images directory, no pin, no tags, and no search index. `ClipboardStore`
owns one instance and merges its items into the list the panel and paste paths
read, so the persistence boundary stays separate without a second UI model.

### Platform and persistence

The platform seam is `android.content.ClipboardManager`, `ClipData`, and
`InputConnection`. Persistence is a JSON snapshot through `SnapshotFile`, not a
database. The store saves asynchronously and keeps the last snapshot ordering so
two saves from different threads do not land out of order.

`FakeAutofillService` in `app/src/debug` is a debug-only inline provider for the
emulator test `InlineAutofillEmulatorTest` (T6). It returns one deterministic
chip and never holds a real credential; it proves the chip plumbing, not
passkey behaviour.

## Architecture diagram

```text
+--------------------------------------------------------------------------------+
| Presentation                                                                   |
| ClipboardFields.kt  KeyboardScreen.kt  ClipboardPanelHost  PanelLayoutHost      |
| - panel cells, search, grid/list, editor, entity chips                          |
+------------------------------------+-------------------------------------------+
                                     | callbacks and KeyboardUiState
                                     v
+--------------------------------------------------------------------------------+
| Application service                                                            |
| WMKeyboardService                                                              |
| - OnPrimaryClipChangedListener                                                 |
| - capture gates: history, incognito, password field, sensitive handling        |
| - paste: text, code, image, file, folder, entity                               |
| - ClipboardWriteGate: the one keyboard-originated write path                   |
| - SelfWriteLedger: one-shot tokens for the keyboard's own writes               |
| - password purge, undo, bump, suggestion chip, AI reply, Send, KDE Connect    |
+----------------+--------------------------------------+------------------------+
                 |                                      |
                 v                                      v
+----------------------------------+   +-------------------------------------------+
| Domain                           |   | Platform                                  |
| ClipboardStore                   |   | ClipboardManager / ClipData               |
| ClipItem, ClipKind               |   | InputConnection.commitText                 |
| ClipCopyRules, ClipSensitivity   |   | InputConnectionCompat.commitContent        |
| ClipLinks, ClipEntities          |   | FileProvider                               |
| ClipboardSyncSanitizer           |   | UsageStatsManager (optional source app)    |
| KeyboardClipboard                |   | FakeAutofillService (debug builds only)    |
+----------------+-----------------+   +-------------------------------------------+
                 |
                 v
+--------------------------------------------------------------------------------+
| Persistence                                                                    |
| filesDir/clipboard/history.json                                                |
| filesDir/clipboard/images/                                                     |
| SecretMemoryStore: process memory only, never in a file or backup              |
| SnapshotFile: async encode and ordered writes                                  |
+--------------------------------------------------------------------------------+
```

## Capture path

The service registers the listener in `onCreate` and removes it in `onDestroy`.
While the input method service process is alive, every system clipboard change
reaches the listener.

1. An app calls `ClipboardManager.setPrimaryClip`.
2. `system_server` updates the primary clip and calls the registered listeners.
3. `WMKeyboardService` reads the clip through `ClipboardManager`. That read
   succeeds only while WM Keyboard is the default IME or has input focus.
4. The listener checks whether the device is unlocked and the keyguard is gone.
   The history is credential-protected, so neither direct boot nor the lock
   screen exposes it.
5. The listener checks the history setting, incognito, and password-field
   capture. A secure copy can still be kept masked when the user chose the
   short-lived handling.
6. The clip is classified:
   - text or HTML: `add` or `addHtml`
   - image URI: bytes are copied into app storage, then `addImage`
   - file, folder, or video URI: only the URI, name, MIME type, and size are
     kept, then `addUri`
   - a URI owned by the keyboard's own `FileProvider`: skipped to avoid a
     duplicate
7. Copy rules and optional tracker removal run before the history keeps the
   text. If the user asked for it, the cleaned text goes back to the system
   clipboard.
8. Source tracking can attach the foreground app through `UsageStatsManager`.
   This is opt-in and best effort.
9. The store saves the history and publishes the new list to the UI.
10. The new clip can also feed the suggestion strip, the AI reply tool, Send
    link detection, or KDE Connect.

```text
App            system_server        WMKeyboardService         ClipboardStore
 | setPrimaryClip |                       |                        |
 |--------------->|                       |                        |
 |                | onPrimaryClipChanged  |                        |
 |                |---------------------->|                        |
 |                |                       | gate: unlock, history, |
 |                |                       | incognito, password    |
 |                |                       | classify and tidy      |
 |                |                       |----------------------->|
 |                |                       | add / addHtml /        |
 |                |                       | addImage / addUri      |
 |                |                       | save + publish         |
 |                |                       |<-----------------------|
```

## Paste path

`onClipboardItemTapped` is the main entry point. The panel, the paste chip, the
entity strip, and the history rows all end there or in a closely related
handler.

| Clip kind | What the keyboard does |
|---|---|
| Text, HTML, link | Commits the text into the focused field with `InputConnection.commitText`. A bare one-time code can be typed digit by digit instead. |
| Image | Sends the app-owned file through `InputConnectionCompat.commitContent`. If the field does not accept the MIME type, the image is offered through the gallery fallback or put on the system clipboard. |
| File, video | Sends the source URI through `commitContent` when the field accepts it. Otherwise the URI goes back to the system clipboard with a toast. |
| Folder | Types the folder name and puts the folder URI on the system clipboard, because a text field has no way to accept a folder. |
| Entity chip | Pastes only the code, phone number, link, or place. It can either type the fragment or copy it as its own clip, depending on the setting. |

After a paste the service can delete a clip from a password field, move the
clip to the top, put it back on the system clipboard, and close the panel. The
delete path also clears the system clipboard when it still holds the removed
clip. Text matches by its stored text. A file matches by its URI. A picture
matches when it was the newest clip and the clipboard holds a URI.

## Storage and limits

`ClipboardStore` is bounded in three independent ways:

- unpinned clips expire after the configured number of hours, default 24
- the newest unpinned clips are kept up to the configured cap, default 100
- retained secrets expire on a separate leash, default 5 minutes; the default
  handling is **never save**

Sensitive clips are not in `history.json` at all. They live in
`SecretMemoryStore`, process memory only. They are cleared when the screen turns
off (`ACTION_SCREEN_OFF` to `onDeviceLocked`), on expiry, when the service is
destroyed, and on process death; switching the handling to **never save** clears
them as well. Pinning does not keep a secret. An ordinary unlock or panel reload
keeps a live secret and republishes it. A history clear by an external writer
that deletes or empties `history.json` drops the secrets too, through
`ClipboardStore.clearFromExternal`.

The normal history file and images directory are excluded from Android Auto
Backup and Device Transfer in `data_extraction_rules.xml` and `backup_rules.xml`;
the explicit ConfigBackup and sync paths strip secrets too.

:::caution[Forward-only backup exclusion]
The backup exclusion applies only to backups made after this change. A backup
created before it can still contain clipboard text, including sensitive text,
so replace or invalidate that backup. The release note for this change records
the rollout instruction.
:::

Pinned clear clips are exempt from the normal history expiry and cap. The
per-clip text length can also be capped. Only the history is capped; the system
clipboard itself is not changed.

The store is a JSON snapshot, so a clip's text, HTML, tags, source app, pin,
position, and preview metadata all travel together. Image bytes live in the
app's own directory and are deleted when their clip is removed, expires, or is
discarded after Undo.

## Privacy gates

Clipboard data is credential-protected. Before the first unlock there is no
history file, and while the keyguard is up the published history is empty. The
panel opens only when `isClipboardAccessible()` is true, which means the user
is unlocked and the keyguard is gone. Hiding the toolbar and the clipboard
panel on the lock screen is a separate setting, **Hide the toolbar and the
clipboard on the lock screen**, and it is off by default.

Retained secrets are cleared when the screen turns off, not by the hide-on-lock
setting. An ordinary unlock republishes the live list and keeps a secret that
has not expired. A history file deleted or emptied by an external writer is a
clear: it drops the secrets with the rest of the history.

Capture and paste have their own gates:

- incognito with clipboard capture paused stops capture, but does not stop the
  panel from opening
- a password field stops ordinary capture; the masked short-lived handling can
  still keep the clip
- a clip the copying app marked sensitive follows the configured handling; the
  default is never save, and any retained secret is memory-only
- a sensitive image or file is not retained at all
- pinning never keeps a secret
- after a password paste, the clip is deleted and the system clipboard is
  cleared when it still holds that clip
- a private copy never reaches the system clipboard

Private copies are a separate mechanism for text routed through
`KeyboardClipboard.copy`, which covers the keyboard's own copy, cut, panels,
and tools that use that helper. With `clipboard.privateCopies` on, or incognito
with its private clipboard option on, such a copy stays in
`KeyboardClipboard.held` instead of going to the system clipboard. The history
records it outside incognito; incognito records nothing. Other keyboard paths,
such as the gallery, music, Send, and share actions, also write the system
clipboard, through `ClipboardWriteGate`, so they still reach One UI's
system-level history. For the text path, private mode is what keeps a keyboard
copy away from that history.

## Platform boundary

### Android owns the clipboard

`ClipboardManager` is an interface to a service, not a pluggable provider. The
service lives in `system_server`, and the platform exposes no third-party
clipboard role. There is no setting and no intent that makes an ordinary app
the system clipboard.

The public API already says who may read it: `getPrimaryClip()` and
`hasPrimaryClip()` return `null` or `false` when the caller is neither the
default IME nor the app with input focus. The AOSP `ClipboardService` implements
that rule with an `isDefaultIme` check before it checks window focus. This is
why a keyboard can read clips while another app is in front, and why an
ordinary background app cannot.

WM Keyboard uses exactly that hook. Its manifest declares an
`InputMethodService` with `android.permission.BIND_INPUT_METHOD`, and its
service registers a clipboard listener in `onCreate`. Selecting WM Keyboard as
the default keyboard grants the package the default IME identity. Nothing in
the app can grant more than that.

### What default IME does not give

Being the default IME does not make the app the clipboard's owner or its
permanent recorder. The listener belongs to a service process. If Android kills
that process, the listener is gone until the service starts again. If the user
switches to another keyboard, the listener may still be registered, but the
read fails because WM Keyboard is no longer the default IME or focused. The
history is therefore best effort, not a guarantee that every copy on the device
is captured.

The store also cannot see copies made before the listener was registered. It
sees the current primary clip only when it reads the clipboard, not a sequence
of past clips that the system kept.

### One UI and Samsung Keyboard

Samsung's One UI adds a vendor clipboard history. On current Galaxy devices the
Samsung Keyboard package is `com.samsung.android.honeyboard`, and its clipboard
history lives in app-private files such as `ClipItem.db`. Samsung has described
the history as managed at system level, and reports show that it can continue to
fill while a third-party keyboard such as Gboard is the default.

That history is not the AOSP clipboard. WM Keyboard cannot read it, import it,
write to it, or replace it. Making WM Keyboard the default keyboard changes
which keyboard is drawing keys and which package gets default-IME clipboard
access. It does not remove Samsung's vendor history or its settings.

On a Galaxy S26 Ultra the default keyboard lives under **Settings > General
management > Keyboard list and default > Default keyboard**. The Samsung
clipboard is cleared from Samsung Keyboard's clipboard button, or from the
clipboard Edge panel. Removing or disabling Samsung's clipboard services is a
vendor-level change made outside the app, typically with ADB. It is not part of
WM Keyboard's supported setup, and it can affect Samsung features or updates.

Android itself also clears the primary clip after a timeout on Android 13 and
later, one hour by default. That clears the AOSP clipboard, not Samsung's
history. The two must not be confused.

## Feasibility

| Goal | Possible | How |
|---|---|---|
| Make WM Keyboard the keyboard used for typing | Yes | Android's default input method setting |
| Replace Android's system clipboard | No | `system_server` owns it; no third-party provider role |
| Read the current system clip while another app copies | Yes, with a limit | Default IME package, while the IME service process is alive |
| Record every copy on the device permanently | No | Process lifetime and default-IME status are not guaranteed |
| Read Samsung Keyboard's clipboard history | No | App-private One UI data, no public API |
| Write directly into Samsung Keyboard's history | No | Same boundary |
| Stop Samsung's history from the app | No | Only a vendor-level change outside the app |
| Keep the keyboard's own text copies off the system clipboard | Yes | `clipboard.privateCopies` or incognito's private clipboard, through `KeyboardClipboard.copy` |

The practical conclusion is that WM Keyboard can be the system-wide keyboard and
can offer a system-wide *history* for most copies, but it cannot be the
system-wide *clipboard provider*. That role belongs to Android, and on Samsung
devices a second vendor history sits beside it.

## Checking a device

The active input method is visible from a shell:

```sh
adb shell settings get secure default_input_method
adb shell dumpsys input_method | grep mCurId
```

The first command shows the selected component. The second shows the input
method the system is currently using. For WM Keyboard the component contains
the app's package name and the `WMKeyboardService` class.

A quick functional check:

1. Copy text in another app, for example a browser address bar.
2. Open WM Keyboard's clipboard panel.
3. Confirm the clip appears.
4. Switch the default keyboard to Samsung Keyboard, copy something else, then
   switch back and confirm what WM Keyboard can and cannot see.

The second half is the important one on a Samsung device: a clip may be in
Samsung's history without ever reaching WM Keyboard's history, and the other
way round.

## Source map

| Concern | Location |
|---|---|
| IME declaration | `app/src/main/AndroidManifest.xml`, the `WMKeyboardService` service node |
| Service class | `feature/ime/.../ime/WMKeyboardService.kt`, `WMKeyboardService` |
| Listener registration | `WMKeyboardService.onCreate` |
| Listener removal | `WMKeyboardService.onDestroy` |
| Clipboard access gate | `WMKeyboardService.isClipboardAccessible` |
| Lock clear | `WMKeyboardService.onDeviceLocked` |
| Capture listener | `WMKeyboardService.clipboardListener` |
| Private copy recording | `WMKeyboardService.recordPrivateCopy` |
| History store construction | `WMKeyboardService.attachPersonalStores` |
| Store settings | `WMKeyboardService.configureClipboardStore` |
| Paste entry point | `WMKeyboardService.onClipboardItemTapped` |
| Image commit | `WMKeyboardService.commitImageClip`, `commitImageFile` |
| File commit | `WMKeyboardService.commitFileClip` |
| System clipboard clear after delete | `ClipboardWriteGate.clear` |
| Password paste purge | `WMKeyboardService.purgeAfterPasswordPaste` |
| Clipboard write gate | `feature/ime/.../ime/ClipboardWriteGate.kt`, `ClipboardWriteGate` |
| Self-write tokens | `feature/ime/.../ime/SelfWriteLedger.kt`, `SelfWriteLedger` |
| Sync and backup sanitizer | `core/content/.../clipboard/ClipboardSyncSanitizer.kt`, `ClipboardSyncSanitizer` |
| Secret memory store | `core/content/.../clipboard/SecretMemoryStore.kt`, `SecretMemoryStore` |
| External history clear | `ClipboardStore.clearFromExternal` |
| Clipboard settings model | `core/settings/.../settings/SettingsRepository.kt`, `ClipboardSettings` |
| Private copies setting | `ClipboardSettings.privateCopies` |
| History model | `core/content/.../clipboard/ClipboardStore.kt`, `ClipboardStore` |
| Private in-memory clipboard | `feature/ime/.../ime/KeyboardClipboard.kt`, `KeyboardClipboard` |
| Panel UI | `feature/ime/.../ime/ui/ClipboardFields.kt`, `ClipboardField` |
| Backup exclusion rules | `app/src/main/res/xml/data_extraction_rules.xml`, `backup_rules.xml` |
| Debug fake autofill provider | `app/src/debug/.../FakeAutofill.kt`, `FakeAutofillService` |

## Password-manager matrix

The keyboard never receives chip content. These are device checks, not JVM
tests; record the result in the code Review.

| Provider | Mode | Android | Expected | Status |
|---|---|---|---|---|
| Bitwarden | Inline | 11, 13, 16, 17 | Username/password chips appear in the autofill lane. | Not executed; no licensed APK/test vault in the worktree. |
| Bitwarden | Popup | 11, 13, 16, 17 | No inline chip; the manager's own dropdown is the fallback. | Not executed; same blocker. |
| Proton Pass 1.39+ | Inline | 11, 13, 16, 17 | Chips appear; older versions may have no inline path. | Not executed; no licensed APK/test vault in the worktree. |
| Proton Pass 1.39+ | Popup | 11, 13, 16, 17 | No inline chip; the manager's dropdown is the fallback. | Not executed; same blocker. |
| Either | Locked vault | 16, 17 | A locked-vault chip opens the manager; it does not silently fail. | Not executed; no test vault. |
| Either | Passkey field | 16, 17 | The passkey chip opens the system/manager prompt; cancel leaves no stale chip. | Not executed; no passkey provider/test account. |
| Either | Incognito | 16, 17 | Login chips stay available; platform smart replies are closed. | Not executed. |

T7 result: the API-36 emulator `SecureWindowEmulatorTest` passed and proved
`FLAG_SECURE` on the IME window for a password field. T7 `bmgr`/locked-boot
checks remain manual; the static backup-rule test is the fallback. T6 remains
ignored because the API-36 emulator creates the `AutofillSession` before the
IME window is visible.

Only one autofill service can be active. The diagnostic summary contains
counters only; it does not name the active provider or any credential.

## Autofill diagnostics

`ClipboardDiagnostics` counts requests, responses, raw suggestions, each lane,
successful inflations and withdrawals. It never stores text, chip labels or
credential values. `DebugLog.d("autofill", ClipboardDiagnostics.summary())`
writes the counters at debug level and is safe to attach to a support report.

The first inline request after a cold start uses the last resolved chip palette
from `SharedPreferences`; only three ARGB colours are stored, never any chip
content. The reporter updates the cache whenever the board resolves a theme.

The same object counts clipboard capture events: attempts, self-write skips,
gate drops, sensitive and sensitive-media drops, stored text/image/file/private,
and aborted text/image captures. It takes no text, label, URI, package name or
credential, and `DebugLog.i("clipboard", ClipboardDiagnostics.summary())` writes
the counters once in `onDestroy`, never on every copy. That is the measurement
used to decide whether background capture is worth a foreground service; the
counters show misses and drops but never their content.

## Android 17 readiness

- `compileSdk` is 37; `targetSdk` remains 36 until the target-37 matrix is run.
- A target-37 bump must also declare `ACCESS_LOCAL_NETWORK` and request it at
  runtime for KDE Connect clipboard sync and other LAN features. Neither is
  done while target is 36; the manifest declaration alone is not sufficient.
- `FLAG_SECURE` protects password fields, incognito and a secret clipboard
  panel. Android 17 deprecates `setContentCaptureEnabled` for target 37.
- Hard text, image and snapshot caps keep the clipboard within Android 17's
  per-app memory limits.
- No per-clip Keystore keys are created; the secret store is memory-only.
- The clipboard panel paste path is checked against the Android 17
  system-context-menu/paste-toast change.
- Universal Clipboard remains a system service; the keyboard listener sees its
  clips but cannot replace the provider.
- Share flows use explicit URI grants; Android 18 removes implicit grants for
  `ACTION_SEND`, `ACTION_SEND_MULTIPLE` and `ACTION_IMAGE_CAPTURE`.

## Platform references

- [ClipboardManager](https://developer.android.com/reference/android/content/ClipboardManager)
  documents the default IME and focus rule on `getPrimaryClip` and
  `hasPrimaryClip`.
- [Secure clipboard handling](https://developer.android.com/privacy-and-security/risks/secure-clipboard-handling)
  covers the sensitive flag and the platform clipboard timeout.
- [AOSP ClipboardService](https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/clipboard/ClipboardService.java)
  shows the default-IME check and the absence of a third-party provider role.
- [Samsung keyboard settings](https://www.samsung.com/us/support/answer/ANS10001592/)
  documents the default keyboard path on Galaxy devices.

## Related pages

- [Clipboard manager](/tools/clipboard/) for the user-facing tool.
- [Incognito and secure fields](/privacy/incognito/) for private copies and
  password handling.
- [Architecture](/development/architecture/) for the module layout.
