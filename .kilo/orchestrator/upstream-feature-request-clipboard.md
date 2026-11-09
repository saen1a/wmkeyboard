# Upstream feature request draft

Template source: `.github/ISSUE_TEMPLATE/feature_request.yml`
Do not publish without operator review.

## Title

`[FEAT]: Harden clipboard secret handling and centralize the write path`

## Description

WM Keyboard's clipboard history is useful, but today a copied password or code
is treated too close to an ordinary clip. A sensitive clip can reach the normal
history snapshot, the platform clipboard preview, an Android or settings backup,
the suggestion strip, or a link-preview request. The code also writes the
clipboard from many call sites, which makes it hard to prove that every write
has the same sensitivity and self-write policy.

This is an architecture proposal, not a request to replace Android's clipboard.
Android owns the clipboard in `system_server`; no app can become its provider.
The proposal keeps the keyboard as the default IME and makes the keyboard-owned
history and write path strict.

### Proposed invariants

1. Sensitive text is never written to `clipboard/history.json`.
2. Sensitive text, images, files, folders and URIs are not retained in the
   persistent history.
3. Every keyboard-originated clipboard write goes through one gate that sets
   `EXTRA_IS_SENSITIVE` when required.
4. A retained secret lives in process memory only and is cleared on expiry,
   screen-off, service destruction or process death.
5. No secret appears in search, suggestion chips, entity chips, link previews,
   logs or diagnostics.
6. Auto Backup and Device Transfer cannot see the clipboard history.
7. Sync and ConfigBackup validate the clipboard bundle per item before merging;
   a crafted bundle cannot inject a secret, a path or a duplicate id.
8. The IME remains the only process that owns the history and the write path.

### Proposed implementation

- `ClipboardWriteGate` as the one IME write path.
- `SelfWriteLedger` for the keyboard's own write-backs and Undo restores.
- `SecretMemoryStore` for memory-only sensitive text.
- `ClipboardSyncSanitizer` as the raw-JSON import boundary.
- Hard caps for text, HTML, images and snapshots.
- Path-level writer lock for the IME and sync/ConfigBackup.
- Content-free capture and autofill diagnostics.
- `FLAG_SECURE` for password fields, incognito and secret panels.
- Standard inline autofill; the keyboard never receives credential content.

### Alternatives considered

- Encrypted secret vault: more persistence than this refactor needs; deferred.
- Dedicated clipboard process: same-UID process is not a security boundary;
  an isolated process cannot access the clipboard or app storage.
- Foreground service for permanent capture: battery, notification, service-type
  and Play-policy cost; not justified without measured missing clips.
- Isolated parser: only useful for untrusted HTML/image parsing; the current
  clipboard stores, rather than renders, HTML.
- Replacing the Android clipboard: impossible for a normal app.

## Additional Information

### Evidence from the prototype

- Local JVM/Robolectric tests cover the store, sanitizer, secure-window
  predicate, inline classifier, API 34 file path, API 36 clipboard behavior and
  manifest/backup audit.
- API 36 emulator `FLAG_SECURE` instrumentation passed for a password field.
- Release APK audit found no debug-only fake autofill fixtures.
- The fake inline-provider chip test is blocked on API 36: the emulator creates
  an `AutofillSession` before the IME window is visible, so the fill request
  carries no inline spec. It is recorded as blocked, not as a pass.
- Real Bitwarden, Proton Pass, passkey and Galaxy S26/One UI rows are
  unexecuted. They need licensed APKs/test vaults and One UI hardware or a
  cloud device farm.
- Repository-wide `staticAnalysis` and the full native-engine suite are
  currently red independently of this work.

### Documentation

- [Clipboard overview](/development/clipboard/)
- [Architecture](/development/clipboard/architecture/)
- [Runtime](/development/clipboard/runtime/)
- [Data and state](/development/clipboard/data-and-state/)
- [Security](/development/clipboard/security/)
- [Decisions](/development/clipboard/decisions/)
- [Testing](/development/clipboard/testing/)
- [Operations](/development/clipboard/operations/)

### Suggested review split

1. Secret store, sensitive flag and write gate.
2. Store hardening, caps and sync sanitizer.
3. Diagnostics and emulator test harness.
4. Documentation and ADRs.

### Questions for maintainers

- Is memory-only secret retention the right product default, or should the
  project keep a short-lived encrypted vault?
- Should the project accept the `NEVER_SAVE` default for sensitive clips?
- Is the forward-only Auto Backup exclusion acceptable, with a release note that
  invalidates pre-upgrade backups?
- Which provider/One UI evidence would the project require before merging?
- Should the fake inline-provider harness live in the repository while the API
  36 chip test remains blocked?
