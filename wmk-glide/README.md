# WM Keyboard: Glide-Typing Deutsch

Stand: 27.10.2026

Untersuchung des Glide-Decoders von [WM Keyboard](https://github.com/wasi-master/wmkeyboard)
(Version 0.6.3) für schnelles, ungenaues Wischen auf Deutsch. Drei Fragen: **Wie gut liest
der Decoder? Welche Einstellungen helfen? Was müsste die Engine anders machen – ohne sie
auszutauschen?**

> **Einstieg:** [`state.md`](state.md) – Zahlen, Stand und nächste Schritte. Die Analyse
> unten ist der erste Durchgang; ihre Empfehlungen sind im Nachtrag korrigiert.

## Ergebnis in sechs Zeilen

- **2.588 echte deutsche Wischer**, ausgelieferte Einstellungen: **71,4 % Erfolg pro Wisch**
  (Decoder allein, ohne Handmodell, Rerank und persönliches Lexikon).
- **Die sichtbaren Regler sind am Optimum.** Fehlerradien, Sigma und Kandidatenbreite
  brachten keinen Gewinn, teils Verluste. Mehr Regler helfen nicht.
- **Die unsichtbaren Konstanten sind englisch.** Deutsches Profil (`freq_weight` 0.5,
  `gap_weight` 2.0): **+2,9** auf Wikipedia-Deutsch, **+10,6** auf einem Korpus aus seltenen
  Wörtern – und **−1,1** auf Englisch (das ältere Drei-Konstanten-Profil aus §4.2 kostete
  1,7). Also ein Sprachprofil, kein neuer Default.
- **Gelernte Formen wirken:** +2,6 / +2,8. Beides zusammen: **71,4 → 76,6 %**.
- **Lange Wörter sind ein Lexikon-Problem** (Coverage bei 15+ Buchstaben: 36,4 %). Komposita
  in die Wortliste zu generieren scheitert (0 von 216 Zielen); die Fortsetzung im Decoder
  ist der Weg (Obergrenze +4,9).
- **Nachtrag 27.10.:** **Echte Komposita-Liste** (441k beobachtete Wörter aus `de_full`)
  74,15 → **75,70**, mit Join-Guard **75,77** — der größte deutsche Hebel. Kontext-Blend
  70,84 → 80,82 ist in-sample (fair +0,2); das deutsche `.wmlm` ist inzwischen trainiert
  (§2.7), auf dem Gerät ist der Blend bis zur neuen `.so` aber noch nicht aktiv; der
  deutsche n-gram-Pack als Rang-Rerank bringt +0,45. Zahlen und Grenzen:
  [`state.md` §2.6](state.md) und [`patches/`](patches/README.md).
- **Training und Kosten:** Wie man das Modell auf einer RX 9060 XT trainiert (WSL2,
  Lehrerwahl, Token-Abdeckung, Rezept) und was lokal, in der Cloud oder über eine API
  anfällt: [`wmlm-training-windows.md`](wmlm-training-windows.md).

## Dateien

| Datei | Inhalt |
|---|---|
| [`state.md`](state.md) | **Arbeitsstand**: alle belasteten Zahlen, Upstream-Commits, offene Befunde, Reproduktion – der Einstieg für eine neue Session |
| [`issue-966-comment.md`](issue-966-comment.md) | Review-Kommentar zum umgesetzten Upstream-Stand (kurze Fassung) |
| [`issue-966-followup.md`](issue-966-followup.md) | Nachtrag-Kommentar zu #966: Blend, Join-Guard, Komposita-Liste, Tests (offline formuliert) |
| [`issue-german-wmlm.md`](issue-german-wmlm.md) | Feature-Request-Entwurf für ein deutsches `.wmlm` (Trainingsrezept, Datenmengen, Abnahme) |
| [`issue-context-blend-oov.md`](issue-context-blend-oov.md) | Feature-Request-Entwurf für Upstream: OOV-Piece-Scoring im Kontext-Blend, Typing-Führer, adaptiver 16-Pool, per-Sprach-Konstanten |
| [`kb-context-blend-optimizations.md`](kb-context-blend-optimizations.md) | KB zu den Blend-Optimierungen: Code-Pfade, Messungen, Priorität, Risiken, Reproduktion |
| [`experiments-followup.md`](experiments-followup.md) | Nächste Stufe: Halte-Test, Pool, Trigramm, Logit, Komposita-Prior, Kontextquelle — was trägt und was nicht |
| [
gram-analysis.md`](ngram-analysis.md) | N-Gramm-Analyse: Chat-Pack, 4-Gramm, Deckel, Normalisierung — was die Daten tragen |
| [`wmlm-gain.md`](wmlm-gain.md) | Wie viel ein deutsches `.wmlm` bringt: englischer Proxy +4,9 Glide-top-1, Schätzung +3–5 für Deutsch |
| [`wmlm-training-windows.md`](wmlm-training-windows.md) | Trainingsweg für die RX 9060 XT (WSL2), Lehrer-/VRAM-Wahl, Token-Abdeckung, Rezept und Kosten (lokal, Cloud, API) |
| [`wmlm-training-plan.md`](wmlm-training-plan.md) | **Getesteter Plan für diesen Rechner**: WSL/ROCm-Setup, Lehrerwahl (Qwen3.5-4B-Base), Multi-Token-Patch, Korpus, Gates, Zeit/Kosten |
| [`experiments/`](experiments/README.md) | Skripte und Rust-Prototyp der Kontextquelle (Forschungscode) |
| [`analyse-de.md`](analyse-de.md) | Die ausführliche Analyse: Datenbasis, Fehlerklassen, Einstellungs-Empfehlungen, Speicherung der Lerndaten |
| [`issue-tuning-per-language.md`](issue-tuning-per-language.md) | Fertiger Issue-Entwurf für das Upstream-Projekt – Titel, Begründung, alle Messungen, Datensätze, Quellen mit URLs |
| [`data/wmk-glide-de-data.zip`](data/wmk-glide-de-data.zip) | 5,0 MB Messdaten: 2.594 deutsche Züge, beide Layouts, 150k-Wortliste, Harness-Patches, README mit Lizenzen und Reproduktionsbefehl |
| [`data/wmk-settings-de-optimized.wmconfig.json`](data/wmk-settings-de-optimized.wmconfig.json) | Importierbares WMK-Profil: 140 Einstellungen, keine Secrets, Endfehler-Radius auf dem ausgelieferten 2,0 |
| [`tools/decompound.py`](tools/decompound.py) | Komposita-Generator 1: Teil + Fuge + Kopf, nach Teilfrequenz sortiert (gemessen, verworfen) |
| [`tools/decompound2.py`](tools/decompound2.py) | Komposita-Generator 2: nach beobachteter Produktivität aus einem 1,16-Mio-Korpus (gemessen, verworfen) |
| [`tools/shape_seed_bench.rs`](tools/shape_seed_bench.rs) | Benchmark für den Seeding-Index: lineare Suche vs. Quadrat-Schranke vs. Start-Zellen-Bucket |
| [`tools/rerank_eval.py`](tools/rerank_eval.py) | Reranker-Experiment: Bigramm über den Decoder-Pool, Pool-/α-Sweep und Gap-Verteilung |
| [`tools/harness.patch`](tools/harness.patch) | Diff gegen
ative/wm-engine/examples/glide_beam_eval.rs`: Spaltenzahl, Nicht-ASCII, `ALL`, `DUMP`, `RESULTS`, `SHAPES` |
| [`tools/freq_weight.patch`](tools/freq_weight.patch) | Diff gegen
ative/wm-engine/src/glide/mod.rs`: `freq_weight`, Längenprior (Default = ausgeliefertes Verhalten) |
| [`tools/blend_cap_eval.py`](tools/blend_cap_eval.py) | Der ausgelieferte Glide-Blend: `clamp(w·ΔlnP, ±cap)` über den Top-8-Pool, Cap-/Gewichts-Sweep |
| [`tools/synth_layout_eval.py`](tools/synth_layout_eval.py) | Synthetische Züge auf Long-Press-, a–z- und Umlaut-Tasten-Gitter (1.324 Wörter) |
| [`tools/join_oracle.py`](tools/join_oracle.py) | Komposita-Obergrenze: Ziele außerhalb der Liste, die in zwei Listenwörter zerfallen |
| [`tools/wmlm_token_coverage.py`](tools/wmlm_token_coverage.py) | Wie viel Prozent eines Vokabulars `distill.py` als Ein-Token-Wort abbilden kann (`--multi` zeigt die Produktregel); im deutschen Modellvokabular: Qwen2.5 12,8 %, Qwen3.5/Qwen3.8 23,6 %, Kolibri 1 **62,9 %** |
| [`tools/deepinfra_echo_probe.py`](tools/deepinfra_echo_probe.py) | Testet, ob DeepInfra mit `echo=true` Prompt-Logprobs **und** eine breite `top_logprobs`-Verteilung liefert; `--self-test`/`--dry-run` offline, live braucht `DEEPINFRA_API_KEY`. Ergebnis 27.10.: FAIL (nur 1–2 Alternativen) |
| [`tools/nebius_echo_probe.py`](tools/nebius_echo_probe.py) | Derselbe Test für Nebius Token Factory (`echo` + `logprobs`, Qwen3-30B/235B, Qwen3.5-397B); live braucht `NEBIUS_API_KEY` oder `--key-file` |
| [`tools/check_soft.py`](tools/check_soft.py) | Prüft ein `soft.npz`: Schema, NaN/Inf, monotone Sätze, ID-Bereich, Anteil Zeilen mit Lehrer-Masse |
| [`tools/merge_soft.py`](tools/merge_soft.py) | Sticht die 30×5k-Chunks eines langen Lehrer-Passes (`distill.py start=/count=`) zu einem `soft.npz` zusammen; atomar und validiert |
| [`tools/run_teacher_chunks.sh`](tools/run_teacher_chunks.sh) | Idempotenter Overnight-Lauf: 30×5k, `flock`, Per-Chunk-Validierung, Merge, SHA256, `DONE`-Marker |
| [`tools/wmlm-teacher.service`](tools/wmlm-teacher.service) | systemd-Unit für den Lehrer-Pass (`Restart=on-failure`); überlebt die Shell, solange WSL lebt |
| [`tools/together_echo_probe.py`](tools/together_echo_probe.py) | Derselbe Test für Together AI (`echo` + `logprobs` 0–20); Signup funktioniert wieder, Probe bereit |
| [`tools/together_token_test.py`](tools/together_token_test.py) | 100-Satz-Test: prüft, ob das echte nächste Lehrer-Token in den Together-Top-1/Top-8 liegt; read-only, Key nötig |
| [`patches/`](patches/README.md) | Vier App-Patches gegen `22d5020b` (Harness, Blend, Join-Guard, Tests/CI) plus `0005-distill-multitoken` für `tools/wmlm/distill.py`; der Layout-Patch liegt optional in `experiments/` |

## Datengrundlage

| Datensatz | Umfang | Lizenz |
|---|---|---|
| FUTO `swipe.futo.org`, deutsche Züge aus `swipe-5` | 2.594 Ein-Finger-Züge, 11-Spalten-Layout mit `ü ö ä` | MIT |
| HeliBoard Gesture Data Project, Deutsch | 19.249 Datensätze, davon 10.908 Ein-Finger-Züge auf a–z-QWERTZ | CC BY-SA 4.0 |
| FrequencyWords Deutsch | `de_50k`, `de_150k` (Top 150k aus 1.157.685 Zeilen) | MIT |
| FUTO Englisch-Test-Split | 2.129 Züge für die Sprach-Gegenprobe | MIT |

## Reproduzieren

```sh
git clone https://github.com/wasi-master/wmkeyboard
cd wmkeyboard && git checkout 22d5020b
P=<dieses repo>/wmk-glide/patches
for p in 0000-eval-harness 0001-glide-context-blend 0002-compound-join-guard \
         0004-tests-ci; do git apply "$P/$p.patch"; done
# optional, nicht empfohlen: $P/../experiments/german-umlaut-keys.patch
cd native/wm-engine && cargo build --release --example glide_beam_eval
cargo run --release --example glide_beam_eval -- \
    de_swipes.jsonl german.json de_150k.txt

# Deutsches Profil und Englisch-Gegenprobe: eine Tuning-Zeile pro Lauf auf stdin
echo "freq_weight=0.5 gap_weight=2.0" | COLS=11 ALL=1 THREADS=8 \
    ./target/release/examples/glide_beam_eval de_swipes.jsonl german.json de_150k.txt
```

Die Dateien liegen im ZIP unter `wmk-glide/data/`; das ZIP enthält zusätzlich eine
`README.txt` mit Herkunft, Lizenzen und demselben Befehl.

## Stand und Grenzen

- Alle Zahlen sind **Decoder plus gelernte Formen**. Handmodell, N-Gramm-Rerank und das
  persönliche Lexikon der App fehlen im Harness – sie können den Wert nur erhöhen.
- Das HeliBoard-Ergebnis (21,9 %) misst einen absichtlich schweren Korpus: 16 % der Ziele
  sind auf einem a–z-Layout nicht tippbar, 28 % stehen nicht in der Liste, die Ziele sind
  sehr selten. Bei fairem Kandidatenraum liest der Decoder dort **78,5 %** richtig.
- Der Issue-Entwurf ist als **#966** gepostet; der Nachtrag-Kommentar
  (`issue-966-followup.md`) ist noch nicht gepostet. Der vorhandene Token hat im
  Upstream-Repo nur Leserechte.
