# German WMLM — Handoff (29.10.2026)

Worktree: `G:\C0ding\git\wmkeyboard-wmlm`
Branch: `wmlm-de-research`, based on `de-glide` (`693f8062e`).
Nothing is committed or pushed; the worktree contains the copied research
tree, the new `artifacts/` directory and this file.

## Stand

Das erste deutsche Modell ist trainiert, exportiert und gemessen:

| | |
|---|---|
| Modell | `wmk-glide/artifacts/models/de_context.wmlm` |
| Größe / SHA256 | **10.856.432 Bytes** / `e9212c5d986010c260d2db4d5c4f98820eb7885b6efff80fc49f181f59c8435c` |
| Architektur | d256 / 6 Layer / 4 Heads / ff768 / ctx40 / vocab24576 / `langs ["de"]` |
| Lehrer | `Qwen/Qwen3.5-4B-Base`, 150k Sätze (Tatoeba DE + Leipzig News 2023) |
| Soft-Targets | 1.723.966 Zeilen, **91,3 %** mit Lehrer-Masse |
| Schüler | 30.000 Steps, heldout loss 4,3400, ppl **76,7** |
| Glide 150k, 0,5/5,0 | **77,40 / 83,42** (Baseline 74,15 / 82,92) |
| Glide + 441k Komposita, 0,5/5,0 | **78,48 / 84,85** (Baseline 75,70 / 84,27) |
| Tippen (500 fast, 0,5/5,0) | **60,80 / 76,60** (Baseline 58,40 / 75,60) |
| Tippen (300 fast, 0,2/1,0) | **59,00 / 74,33** (Baseline 56,33 / 74,00) |

Details: `wmk-glide/state.md` §2.7, `wmk-glide/wmlm-training-plan.md`.
Der d288/6/896-Referenzlauf (12,82 MB) war **kein Gewinn** (Glide 77,32,
Tippen 60,40, nur Ppl 74,2) und bleibt ein Research-Artefakt.

## App/Harness-Gap: im Code geschlossen (29.10.2026)

Der gemessene 78,48-Wert war ein **Harness-Wert**. Der Harness bewertete
Glide-Kandidaten schon mit `Session::logprob` (OOV-Wörter in Pieces); die App
nutzte `contextModel.scores` → `lmScores` → `logprob_listed` und bekam für
OOV-Komposita NaN. Beide brachen ab, wenn der erste Kandidat keinen Score
hatte. Behoben:

- **JNI/Kotlin:** neues `lmScoresSpelled` in `native/wm-engine-jni/src/lm.rs`
  (ruft `Session::logprob`, also Liste **oder** Piece-Produkt) und
  `ContextModel.scoresSpelled`. `scores()` bleibt der billige Strip-Pfad.
- **App:** `SuggestionEngine.blendGlideContextModel` bewertet nur die ersten
  16 Kandidaten (`GLIDE_DEEP_POOL`, ordinär 8) mit `scoresSpelled`, nimmt die
  Referenz als **ersten finiten** Score und lässt unlesbare Kandidaten auf
  ihrem Decoder-Score. `rerankGlide` folgt unverändert.
- **Blend:** `GLIDE_LM_BLEND=0.5`, `GLIDE_LM_BLEND_CAP=5.0`.
- **Harness:** dieselbe Referenz (`lps.iter().flatten().find(finite)`), gleiche
  8–16 Kandidaten, `WEIGHT=0.5 CAP=5` als Default.

Neu gemessen (`de_context.wmlm`, 2.588 FUTO-Wischer, deutsches Profil,
`0,5/5,0`), alte App-Simulation (`logprob_listed`, Führer-Referenz) gegen den
neuen Pfad (Piece-Spelling, erste finite Referenz):

| Wortliste | alte App, top-1/top-4 | neue App/Harness, top-1/top-4 | geblendet (von 2.294) |
|---|---:|---:|---:|
| 150k | 76,04 / 83,23 | **77,40 / 83,42** | 1.782 → **2.294** |
| 150k + 441k Komposita | 77,51 / 84,66 | **78,48 / 84,85** | 1.693 → **2.294** |

Die alte App ließ also 512 bzw. 601 Züge mit Vorgängerwort unverblendet, weil
der Top-Kandidat ein OOV-Kompositum war; das sind **+1,36** top-1 auf 150k und
**+0,97** mit Komposita. Der reine Harness-Wert war schon vorher 77,40/78,48 —
der Hebel ist die App-Parität. App-Parität ist auf Code-Ebene hergestellt
(gleiche Funktion, gleiche Referenz, gleiche Kandidatenzahl, gleiche
Konstanten); Kotlin ist hier ohne Android-SDK nicht kompilierbar. Das
JNI-Symbol ist in der unter WSL gebauten `libwm_engine_jni.so` exportiert.
**Offen:** die Android-`.so` neu bauen und den Wert auf dem Gerät nachmessen.
Weitere gemessene Hebel (Typing-OOV-Führer, adaptiver 16-Pool,
Start-Piece-Abdeckung) und der Upstream-Issue-Entwurf:
[`kb-context-blend-optimizations.md`](kb-context-blend-optimizations.md),
[`issue-context-blend-oov.md`](issue-context-blend-oov.md).

## Nächste Schritte

1. **500k Soft-Targets** aus demselben Korpus: 4B lokal ≈ 41 h, oder 9B/Qwen4
   erst nach einem 100-Satz-A/B. Erwartung +0,3–0,6 pp Glide.
2. **32k-Vokabular mit Top-Komposita** (neue Soft-Targets): Modell ≈ 12,9 MB;
   der direkte Komposita-Hebel im Modell.
3. **Confidence-Gate** und **Join-aware/Piece-Scoring** für die 441k
   OOV-Komposita; das ist der größte unausgeschöpfte App-Hebel.
4. **Volle Messung:** `typing_eval` 3.000/all, Glide mit Join-Guard,
   Telefon-Latenz; erst dann Katalog/Veröffentlichung.
5. **Qwen4:** Tokenizer bleibt dieselbe BPE-Familie (~248k), kein
   Tokenizer-Sprung; ein Qwen4-27B-Base ist ein Lehrer-Kandidat, kein Grund zu
   warten. **Together-API** ist für Prompt-Logprobs untauglich (GPT-OSS 422,
   Qwen3.5 nur 1 Top-Eintrag, Qwen3.8 403; free Prism zu schwach).
   **Scaleway** nur nach einem 100-Satz-A/B; **kein größerer Schüler** (d288
   ohne Gewinn); **Englisch entfernen** ist kein Hebel.

## Befehle

```powershell
cd G:\C0ding\git\wmkeyboard-wmlm
# Harness bauen (Datei ggf. nach native/wm-engine/examples/ kopieren)
cargo build --release --example glide_lm_blend_eval --manifest-path native/wm-engine/Cargo.toml
```

```powershell
$e="native/wm-engine/target/release/examples/glide_lm_blend_eval"
$d="wmk-glide/artifacts"
$env:RESULTS="8"; $env:COLS="11"; $env:THREADS="8"; $env:FREQ="0.5"; $env:GAP="2.0"; $env:WEIGHT="0.5"; $env:CAP="5"
& $e "$d/data/de_swipes.jsonl" "$d/data/german.json" "$d/data/de_150k_comp3.txt" "$d/models/de_context.wmlm"
```

```powershell
# Tippen (fast, 500 Fälle)
$t="native/wm-engine/target/release/examples/typing_eval"
$env:CASES="500"; $env:SCATTER="fast"; $env:MODES="base,lm"; $env:SAVINGS="0"; $env:LMBLEND="0.5"; $env:LMBCAP="5.0"
& $t "$d/data/de_150k.txt" "$d/out/heldout.tsv" "$d/models/de_context.wmlm"
```

`wmk-glide/artifacts/README.md` lists sizes, hashes and reproduction commands.
`wmk-glide/artifacts/MANIFEST.sha256` has the model/soft/checkpoint hashes.
Large files are intentionally untracked; do not add them without LFS.

## Constraints

- Keine Keys/Secrets ins Repo; `.togetherai.key`/`.deepinfra.key` bleiben außerhalb.
- Kein Commit/Push ohne explizite Aufforderung.
- Die App-Patches `0000`–`0004` vor App-Tests anwenden/prüfen; `0005` ist das
  Trainings-Tool.
- Datenlizenzen: Tatoeba, Leipzig, FUTO, `de_aosp`; Attribution im Datenrepo.
- Die 78,48/84,85 erst als Geräteergebnis zitieren, wenn die neue `.so`
  gebaut und auf dem Gerät gemessen ist; der App/Harness-Gap ist im Code
  geschlossen.

## Fortsetzungs-Prompt

```text
Du setzt die deutsche WMLM-Arbeit im wmk-Fork fort.

Worktree: G:\C0ding\git\wmkeyboard-wmlm
Branch: wmlm-de-research (Basis de-glide, 693f8062e)

Lies zuerst:
- wmk-glide/HANDOFF.md
- wmk-glide/state.md §2.7
- wmk-glide/wmlm-training-plan.md

Stand: Das deutsche d256/6/768-Modell (10,86 MB, SHA256 e9212c5d…) erreicht
im Harness 77,40/83,42 auf 150k und 78,48/84,85 mit 441k Komposita bei
Blend 0,5/5,0; Tippen 60,80/76,60. d288/6/896 brachte keinen Gewinn und ist
verworfen. Die 150k Soft-Targets liegen unter wmk-glide/artifacts/out/.

Der App/Harness-Gap ist geschlossen: `ContextModel.scoresSpelled` +
`lmScoresSpelled` im JNI, der Glide-Blend bewertet nur die ersten 8–16
Kandidaten damit, Referenz ist der erste finite Score, Konstanten 0,5/5,0;
der Harness nutzt dieselbe Referenz. Neu gemessen: 77,40/83,42 (150k) und
78,48/84,85 (mit Komposita). Offen ist nur die neue Android-`.so` und die
Gerätemessung.

Erste Aufgabe: 500k Soft-Targets aus demselben Korpus (4B lokal ≈41 h, oder
9B erst nach einem 100-Satz-A/B), dann neuer Schüler/Export und dieselbe
Glide-/Tipp-Messung.

Danach in dieser Reihenfolge: 32k-Vokabular mit Top-Komposita (neue
Soft-Targets) → Confidence-Gate/Join-aware Scoring → volle
typing_eval-/Glide-/Telefon-Messung → Veröffentlichung.

Nicht tun: auf Qwen4-Tokenizer warten (gleiche BPE-Familie), Together-API für
Prompt-Logprobs nutzen (GPT-OSS 422, Qwen3.5 1 Top-Eintrag, Qwen3.8 403),
größeren Schüler trainieren (d288 ohne Gewinn), Englisch aus dem Korpus
entfernen. Scaleway nur nach 100-Satz-A/B. Keine Keys/Secrets committen; kein
Commit/Push ohne Aufforderung. Artefakte und Befehle: wmk-glide/artifacts/README.md.
```
