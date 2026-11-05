---
name: wmk-languages
description: Work on the language, layout, dictionary, and translation data. Use when adding a language or layout, regenerating a dictionary, importing translations, or changing a native gate's data.
---

# WM Keyboard languages and data

## Layout

- `core/language/` - the language and layout registry, the transliteration
  engines, the dictionary readers, and the engine facade.
- `app/dictionaries-src/` - the source word lists (`en.txt`, `bn.txt`, and the
  per-language files).
- `tools/dictc/` - the host-side dictionary compiler. It shares the app's trie
  and codec sources so the written format cannot drift from the reader.
- `tools/i18n/pull-play-translations.py` - recovers Play's server-side
  translations from a universal APK.
- `tools/emoji/`, `tools/vocab/`, `tools/handwriting/`, and `tools/icon/` -
  the other data generators.
- `scripts/update-*.py` and `scripts/update-*.sh` - upstream data updates.

## Commands

```sh
./gradlew :app:compileBundledDictionaries
./gradlew :tools:architecture:test
python3 tools/i18n/pull-play-translations.py path/to/universal.apk
```

The dictionary compiler runs at build time. Do not hand-edit a generated
`.wmdict`; change the source list and rebuild.

## Rules

- The language registry is data-driven. Add a language or layout to the
  registry, not as a special case in the IME.
- Keep the wide script surface working: Bangla Avro and Khipro, Indic phonetic,
  Arabic and Urdu, Pinyin and Jyutping, kana, Hangul, Vietnamese Telex.
- A layout change needs a real keyboard test. A JSON edit that compiles can
  still put a dead key on the grid.
- Translation imports are keyed against this repo's `values/strings*.xml`;
  never paste a dependency's strings back.
- An upstream data update is a separate commit with its source URL and the
  command that produced it.

## Traps

- `dictionaries-src/` is under `app/`, not the repository root.
- A new native data gate also needs an entry in `native/gates.json`, or the
  packaging and ProGuard lists will not see it.
- F-Droid builds compile the `src/nogoogle` stand-ins; a language feature that
  calls a Google library needs a stand-in.
- Emoji and dictionary catalogs are generated. Read the generator header before
  editing its output.

## Done means

- `./gradlew :app:compileBundledDictionaries` exits 0.
- The architecture suite exits 0.
- The language or layout has a test or a device check that names the script and
  the expected output.
