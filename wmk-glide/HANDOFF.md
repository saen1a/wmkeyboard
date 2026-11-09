# German WMLM — Handoff (29.10.2026)

Worktree: `G:\C0ding\git\wmkeyboard-wmlm`
Branch: `wmlm-de-research`, based on `de-glide` (`693f8062e`).
Nothing is committed or pushed; the worktree contains the copied research
tree, the new `artifacts/` directory and this file.

## Stand

> **Release identity:** canonical in `state.md` §2.7 and the upstream
> `data/de/de_context.md` (published G6P 90k, `4fe6...`, G7 PASS +0.73 vs 2M).
> The local artifact below is the earlier Phase 1 model (`e921...`); the data
> card records the CC BY-NC / OpenSubtitles notice.

Das erste deutsche Modell ist trainiert, exportiert und gemessen:

| | |
|---|---|
| Modell (lokal, Phase 1) | `wmk-glide/artifacts/models/de_context.wmlm` |
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
   warten. **Together-API** liefert prompt-Logprobs, aber **live gemessen
   genau 5** Alternativen (03.11.2026; `logprobs: 20` → HTTP 400, deshalb war
   der alte 1-Eintrag/422/403-Lauf ungültig; Qwen3.5-9B und gpt-oss-120b je
   5/5). 5 < 10 → für Soft-Targets untauglich, Grund jetzt belegt.
   **Scaleway** nur nach einem 100-Satz-A/B; **kein größerer Schüler** (d288
   ohne Gewinn); **Englisch entfernen** ist kein Hebel. **Together-Pfad ist
   gebaut** (`cloud/together/`: Collector, Wort-Map, Probe, Tests) — 8-wide
   mit `mass`-Gewichtung, Entscheidung per A/B
   ([`together-teacher-plan.md`](together-teacher-plan.md)).

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

Stand: Release-Identität und alle Messwerte stehen kanonisch in
`state.md` §2.7 und `data/de/de_context.md` (veröffentlicht G6P 90k `4fe6…`,
G7 PASS +0.73 vs 2M). Das lokale `e921…` ist das frühere Phase-1-Modell;
seine Werte stehen in §2.7. d288/6/896 brachte keinen Gewinn und ist
verworfen. Die 150k Soft-Targets liegen unter wmk-glide/artifacts/out/.

Der App/Harness-Gap ist geschlossen: `ContextModel.scoresSpelled` +
`lmScoresSpelled` im JNI, der Glide-Blend bewertet nur die ersten 8–16
Kandidaten damit, Referenz ist der erste finite Score, Konstanten 0,5/5,0;
der Harness nutzt dieselbe Referenz. Neu gemessen: 77,40/83,42 (150k) und
78,48/84,85 (mit Komposita). Offen ist nur die neue Android-`.so` und die
Gerätemessung.

Entscheidung: **1M Basis + 200k Chat = 1,2M Soft-Targets**. Basis
stratifiziert 440k Tatoeba + 560k News; +200k aus dem Tatoeba-Rest (oder
OpenSubtitles, falls das Chat-Heldout es verlangt) → 640k Chat / 560k News
(53/47). Dedupliziert, bestehendes 20k-Heldout ausschließen, Chat-Heldout
getrennt halten. Kosten bei Qwen3.8-27B/Chutes ~2,4–2,9 $; gemessen
8 Worker/Retries ~5,8 Tage, 4 Worker ~7,9 Tage (16/32 nur Burst).
Schüler 30k Steps ~6,3 h. 1,78M nur, wenn 1,2M noch
deutlich gewinnt. Danach neuer Schüler/Export und dieselbe
Glide-/Tipp-Messung.

**1,2M-Korpus gebaut:** `corpora/de_1m_200k_chat.tsv`, 1.200.000 Zeilen,
640k Tatoeba/Chat + 560k News (53,3/46,7), 0 Heldout-Leaks,
SHA256 `882cdd3137d071e1684dda79b746377caead6fb9a2d5c20690a2a0c20d8f9976`.
Der Chutes-Concurrency-Test ist ebenfalls gelaufen: 4 Worker sauber
(1,75 Sätze/s), 8 mit Retries ~2,40/s, 16 mit Retries **0/100** (429).
Damit ist der 1,2M-Lauf ~5,8–7,9 Tage, **nicht 1–2 Tage** und nicht
schneller als lokal (~4,4 Tage).

**Lokal unterbrechbar:** `run_teacher_1m2.sh` rechnet 240×5k Chunks
idempotent; ein Stop kostet höchstens ~27 min (aktueller Chunk), der Merge
ist atomar. Schüler: `train.py` checkpointet alle 1000 Steps und resume mit
`resume=out/de_run/last.pt`. Details in `wmlm-training-plan.md` §4.3.
**Gaming-Pause:** `systemctl stop wmlm-teacher-1m2` gibt die GPU frei;
`start` macht mit gültigen Chunks weiter. Vorher `rocm-smi` prüfen.

**Lokale Lehrer (A/B 29.10.):** `Qwen3.5-9B-Base` 8-bit gewinnt gegen
4B-Base auf 50 Chat-/50 News-Sätzen: **+1,22/+2,31** top-1,
**+2,46/+2,06** top-8, NLL **−0,18/−0,19**. Speed praktisch gleich
(2,58 vs. 2,69 Sätze/s; 1,2M ~5,4 vs. 5,2 Tage). 8-bit läuft auf ROCm.
Nächster Gate: 10k-Soft-Target-A/B mit 3k–5k Schüler-Steps; dafür
`distill_multi.py` `load8bit` beibringen. Danach Empero Qwen3.8-9B-Distill
und LightOn Qwen3-8B-DE. 27B/35B nur 3–4-bit, riskant. Details:
[`kb-teacher-models.md`](kb-teacher-models.md).

**API-Lehrer (29.10.2026):** Chutes ist die neue erste Wahl, aber **nur
`Qwen/Qwen3.8-27B-TEE`**: vLLM, `allow_logprobs: true`,
`prompt_logprobs: 20`, Qwen-Tokenizer; 1M ≈2–3 $, aber 8 Worker/Retries
~4,8 Tage (4 Worker ~6,6; 16/32 nur Burst). Die stärkere
`Qwen3.5-397B-A17B-TEE` läuft auf **SGLang** und liefert über den
OpenAI-Gateway **keine** Prompt-Logprobs; Qwen3.6-27B genauso, 2.4T/Max
sind extern (404). Together (Cap 5; 29.10. mit `logprobs: 20` → 1 Eintrag/422/
403) und DeepInfra (2 Einträge) sind live durchgefallen. Qwen3.8-27B lief im
korrekten 100-Satz-Lauf **99/100** (98 first try, 1× NaN nach 3 Versuchen),
Chat **99/100** (1× HTTP 502); frühere 1/10-Serien waren lastabhängig. Der NaN-Fehler ist der
bekannte **vLLM-MTP-Bug #53488** (Fix #53520): der Drafter überschreibt
Hidden States vor der Prompt-Logprob-Berechnung, kann auch **HTTP 200 mit
falschen** Werten liefern. **Live bestätigt:** 9/10 Wiederholungen eines
einfachen Prompts lieferten fremde Top-Tokens; das echte ` will` lag auf
Rang 70.733, der 100-Satz-Lauf ergab top-1 3,6 % / NLL 1e36. **Chutes-27B
ist damit kein Lehrer**, bis MTP deaktiviert oder vLLM auf #53520 ist.
Bis dahin: **lokal Qwen3.5-9B-Base 8-bit** (sauber, +1,2/+2,3 top-1,
gleiche Speed). **Kimi-K2.6-TEE** war **20/20 ohne NaN** (~1,2 s), hat aber
den schlechteren Deutsch-Tokenizer (7,3 % Typen / 59,8 % gewichtet vs.
Qwen 11,0 % / 84,6 %; Schüler-Vokabular 10,8 % vs. 23,1 %) und kostet ~10×.
Der frühere „100/100“-Wert war ein Testfehler und ist zurückgezogen.
Probe: [`tools/chutes_echo_probe.py`](tools/chutes_echo_probe.py).
Details: [`kb-inference-providers.md`](kb-inference-providers.md).

Danach in dieser Reihenfolge: 32k-Vokabular mit Top-Komposita (neue
Soft-Targets) → Confidence-Gate/Join-aware Scoring → volle
typing_eval-/Glide-/Telefon-Messung → Veröffentlichung.

Nicht tun: auf Qwen4-Tokenizer warten (gleiche BPE-Familie), Together-API für
Prompt-Logprobs nutzen (Cap 5; der alte 1-Eintrag/422/403-Lauf sendete
`logprobs: 20` und war ungültig),
größeren Schüler trainieren (d288 ohne Gewinn), Englisch aus dem Korpus
entfernen. Scaleway nur nach 100-Satz-A/B. Keine Keys/Secrets committen; kein
Commit/Push ohne Aufforderung. Artefakte und Befehle: wmk-glide/artifacts/README.md.
```
k-glide/artifacts/README.md.
```
committen; kein
Commit/Push ohne Aufforderung. Artefakte und Befehle: wmk-glide/artifacts/README.md.
```
k-glide/artifacts/README.md.
```
