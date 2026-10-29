# KB: Kontext-Blend — OOV-Abdeckung, Kandidatenpool, Typing-Pfad

Stand: 29.10.2026. Ergänzt [`state.md`](state.md) §2.7 und
[`HANDOFF.md`](HANDOFF.md). Der Issue-Entwurf für Upstream liegt in
[`issue-context-blend-oov.md`](issue-context-blend-oov.md); hier steht die
Evidenz, die nicht in ein GitHub-Issue passt.

## 0. Kurzfassung

- Der Glide-Blend ist jetzt auf demselben Pfad wie der Harness:
  `scoresSpelled` → JNI `lmScoresSpelled` → `Session::logprob` (Liste oder
  Piece-Produkt), Referenz = erster finiter Score, 0,5/5,0. Das schließt den
  App/Harness-Gap: **+1,36** top-1 auf 150k, **+0,97** mit Komposita.
- Der **Typing-Pfad hat denselben OOV-Bug** wie die Glide-App vorher:
  `blendGlideContextModel` ist gefixt, `blendContextModel` (Kotlin) und
  `Predictor` (Rust) brechen bei einem OOV-Führer weiter ab. Ein lokaler
  Prototyp zeigt: Führer nur per Pieces scoren = **+0,20** top-1, Top-4-OOV =
  **+0,60**, alle Kandidaten = **+1,00**, aber 10× `suggest`-Zeit.
- Der Glide-Pool ist ein zweiter, kleiner Hebel: 16 statt 8 Kandidaten =
  **+0,11** top-1 / **+0,24** top-4 (150k) und **+0,07** / **+0,24**
  (Komposita), bei doppeltem Decode/Score-Aufwand. Adaptive Verbreiterung ist
  die sinnvolle Form.
- Die Start-Piece-Abdeckung ist eine stille Grenze: **20,5 %** der gültigen
  150k-Wörter und **19,6 %** der 591k-Komposita sind mit dem aktuellen
  `pieces_of` nicht spellbar, weil am Wortanfang nur ganze Wörter als Pieces
  existieren (`gib`: kein `g`/`gi`-Wortstück, aber `##g`/`##i`/`##b`). Ein
  Continuation-Fallback deckt 99,99 % ab, brachte auf FUTO aber keinen
  Top-1/Top-4-Gewinn; die saubere Lösung ist ein Alphabet-Seed im Vokabular.

## 1. Ist-Stand im Code

| Pfad | Funktion | Score | Referenz | Abbruch bei OOV-Führer |
|---|---|---|---|---|
| Glide (Kotlin) | `SuggestionEngine.blendGlideContextModel` | `ContextModel.scoresSpelled` → `lmScoresSpelled` → `Session::logprob` | erster finiter Score | nein (seit 29.10.) |
| Typing (Kotlin) | `SuggestionEngine.blendContextModel` | `ContextModel.scores` → `lmScores` → `logprob_listed` | `scores[leader]` | **ja** (`SuggestionEngine.kt:3333-3334`) |
| Typing (Rust) | `Predictor::lm_blend` | `lm_logprob` → `logprob_listed` | `leader.and_then(lm_logprob)` | **ja** (`predict.rs:1301-1303`) |
| Gate/Revise | `ContextModel.gateView` / `revise` | `lmGateView` / `lmRevise` | – | nein; spelt bereits Pieces |

Der Glide-Pfad bewertet nur die ersten `GLIDE_DEEP_POOL = 16` Kandidaten
(ordinär 8, `GLIDE_RERANK_POOL = 8`). `scores()` bleibt der billige
Lookup-Pfad für den ganzen Strip; `scoresSpelled()` ist der teurere Pfad für
die Handvoll Glide-Kandidaten.

Modell: `de_context.wmlm`, d256/6/768, ctx 40, Vokabular 24.576, 10,86 MB,
SHA256 `e9212c5d…`. Der Vokabel-Header enthält 1.572 `##`-Pieces; der Rest
sind Wörter und Spezialtokens.

## 2. Messungen

### 2.1 Glide: Lookup-only gegen Piece-Spelling

2.588 FUTO-Wischer, deutsches Profil `COLS=11 FREQ=0.5 GAP=2.0`,
`WEIGHT=0.5 CAP=5`, 2.294 Züge mit Vorgängerwort. „Alte App“ simuliert
`logprob_listed` + Führer-Referenz; „neu“ ist der ausgelieferte Pfad.

| Wortliste | alte App top-1/top-4 | neu top-1/top-4 | geblendet |
|---|---:|---:|---:|
| 150k | 76,04 / 83,23 | **77,40 / 83,42** | 1.782 → 2.294 |
| 150k + 441k Komposita | 77,51 / 84,66 | **78,48 / 84,85** | 1.693 → 2.294 |

Der Gap ist **+1,36** bzw. **+0,97** top-1; vorher blieben 512/601 Züge
unverblendet. Die Harness-Zahl selbst war schon vorher 77,40/78,48, weil der
Harness `logprob` benutzte. Die neue Messung bestätigt sie.

### 2.2 Glide: Kandidatenpool 8 / 12 / 16

Gleiche Züge, gleicher Blend, nur `RESULTS` (Decode-Tiefe) geändert:

| Pool | 150k top-1/top-4 | +441k top-1/top-4 |
|---:|---:|---:|
| 8 (heute ordinär) | 77,40 / 83,42 | 78,48 / 84,85 |
| 12 | 77,43 / 83,54 | 78,52 / 84,93 |
| 16 (`GLIDE_DEEP_POOL`) | **77,51 / 83,66** | **78,55 / 85,09** |

Der Gewinn ist klein, aber konsistent; 16 kostet doppelten Decode und doppelte
Score-Berechnung. Eine adaptive Verbreiterung (nur bei kleiner Führer-Lücke
oder hoher Modell-Unsicherheit) sollte den meisten Gewinn zu Kosten von 8
holen. Das ist die geplante Confidence-Gate-Richtung.

### 2.3 Typing: OOV-Führer und Kandidaten-Pieces

500 Fälle, `SCATTER=fast`, deutsches Held-out, `LMBLEND=0.5 LMBCAP=5.0`.
Aktueller Branch-Baseline (nicht die ältere 60,80/76,60 aus dem Handoff — die
Revision ist eine andere; der A/B ist same-run):

| Variante | top-1 | top-3 | suggest (us) | Bemerkung |
|---|---:|---:|---:|---|
| Lookup-only (heute) | 62,00 | 79,40 | 2.540 | Führer-OOV bricht ab |
| Führer per Pieces | 62,20 | 79,60 | 2.847 | billig, +0,20 |
| Top-4-OOV per Pieces | 62,80 | 79,60 | 4.755 | +0,80, ~2× suggest |
| alle Kandidaten per Pieces | **63,00** | **80,00** | 27.378 | +1,00, ~10× suggest |

Die Prototypen lagen nur in `predict.rs` und sind zurückgerollt. Für die App
ist die Führer-Variante der sichere erste Schritt; Top-4 nur mit
Score-Schwelle (z. B. nur OOV-Kandidaten innerhalb von 3 Nats um den Führer).
Alle Kandidaten pro Tastendruck zu spellen ist zu teuer.

### 2.4 Start-Piece-Abdeckung

Greedy-Longest-Match wie `pieces_of` (max. 5 Zeichen pro Stück, max. 6
Stücke), nur alphabetische Wörter mit ≥ 2 Zeichen:

| Liste | gültige Wörter | im Vokabular | per Pieces spellbar | > 6 Stücke | nicht spellbar |
|---|---:|---:|---:|---:|---:|
| `de_150k` | 145.395 | 20.045 (13,8 %) | 95.577 (65,7 %) | 2.260 (1,6 %) | **29.773 (20,5 %)** |
| `de_150k_comp3` | 583.154 | 21.182 (3,6 %) | 447.784 (76,8 %) | 35.962 (6,2 %) | **114.188 (19,6 %)** |

Ursache: `pieces_of` nimmt am Wortanfang nur `start_pieces` (ganze Wörter).
`gib` ist nicht im Vokabular, `g`/`gi` sind keine Startstücke, also `None` —
obwohl `##g`, `##i`, `##b` existieren. Ein Prototyp mit
Continuation-Start-Fallback (`##g` am Anfang) macht 99,99 % spellbar, änderte
auf FUTO aber weder top-1 noch top-4. Die saubere Lösung ist, einzelne
Buchstaben (a–z, äöüß) beim `prep.py`-Lauf als Startstücke zu seeden; das
kostet ~30 Vokabel-Slots und ist Teil des geplanten 32k-Laufs.

## 3. Priorität für Upstream

| Prio | Hebel | Evidenz | Aufwand / Risiko |
|---|---|---|---|
| **P1** | Typing-Führer per Pieces scoren, erste finite Referenz | +0,20 top-1, +0,20 top-3, suggest 2.540 → 2.847 us | klein; gleiche Semantik wie Glide |
| **P1** | Glide-Pool adaptiv auf 16 bei Unsicherheit | +0,11/+0,24 (150k), +0,07/+0,24 (Komposita) | mittel; Decode-Kosten, Latenz messen |
| **P1** | Blend-Gewicht/-Cap in `GlideLanguageProfiles` | Deutsch 0,5/5,0; global gesetzt | klein; verhindert Sprachregression |
| **P2** | Start-Piece-Abdeckung (Alphabet-Seed) | 20 % unspellbar; Fallback ohne FUTO-Gewinn | Vokabular/Retrain, 32k-Lauf |
| **P2** | Compound-aware Scoring (Join/Piece-Summe) | 441k-Liste +1,55; Join-Oracle 4,56 % | groß; eigener Entwurf |
| **P3** | Confidence-Gate, ungescorte Penalty, Latenz-Cache | geplant, nicht gemessen | Experiment |

### Was nicht hilft / was vermieden werden sollte

- **Nicht** global 0,5/5,0 für alle Sprachen setzen. Die Konstante ist auf
  Deutsch gemessen; `LM_BLEND`/`LM_BLEND_CAP` sind heute global
  (`SuggestionEngine.kt:2805-2817`). Ein Sprachprofil ist der sichere Weg.
- **Nicht** alle Typing-Kandidaten pro Tastendruck spellen: +1,00 top-1, aber
  `suggest` 2.540 → 27.378 us im Harness; auf dem Telefon schlechter.
- **Nicht** den Continuation-Start-Fallback als Qualitätshebel verkaufen: Er
  schließt die Abdeckung, aber die FUTO-Zahlen bleiben gleich; er ist eine
  Robustheitsmaßnahme, kein gemessener Gewinn.
- **Nicht** den Pool blind auf 16 stellen, ohne die Latenz zu messen; der
  Qualitätsgewinn ist +0,11/+0,07 top-1.

## 4. Reproduktion

```powershell
# Glide, neuer Pfad
$e="native/wm-engine/target/release/examples/glide_lm_blend_eval"
$d="wmk-glide/artifacts"
$env:RESULTS="8"; $env:COLS="11"; $env:THREADS="8"; $env:FREQ="0.5"; $env:GAP="2.0"; $env:WEIGHT="0.5"; $env:CAP="5"
& $e "$d/data/de_swipes.jsonl" "$d/data/german.json" "$d/data/de_150k_comp3.txt" "$d/models/de_context.wmlm"
# Pool 16: RESULTS=16
```

```powershell
# Typing, 500 fast
$t="native/wm-engine/target/release/examples/typing_eval"
$env:CASES="500"; $env:SCATTER="fast"; $env:MODES="base,lm"; $env:SAVINGS="0"; $env:LMBLEND="0.5"; $env:LMBCAP="5.0"
& $t "$d/data/de_150k.txt" "$d/data/heldout.tsv" "$d/models/de_context.wmlm"
```

Hinweis: `heldout.tsv` liegt in `artifacts/data/`, nicht in `out/`; der
Handoff-Befehl mit `out/heldout.tsv` läuft nicht.

## 5. Grenzen

- Kotlin ist hier ohne Android-SDK nicht kompiliert; die JNI-`.so` wurde ohne
  NDK nicht neu gebaut. Gerätelatenz und App-Verhalten sind offen.
- FUTO ist Evaluationsdaten; die 2.588 Züge sind kein Trainingssatz.
- Die Typing-Zahlen sind der Rust-`Predictor`, nicht die Kotlin-App; die
  Richtung ist übertragbar, die absoluten Werte nicht.
- Die Pool- und Typing-Prototypen sind nicht im Baum; sie sind Evidenz für
  den Issue-Entwurf, kein ausgelieferter Code.
