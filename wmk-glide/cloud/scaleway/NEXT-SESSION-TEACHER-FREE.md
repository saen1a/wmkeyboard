# Prompt: lehrerfreies Training — bestmögliches Ergebnis ohne neue GPU

Du übernimmst die deutsche WMLM-Arbeit im wmkeyboard-Fork. Ziel dieser
Session ist **nicht** ein neuer Cloud-Lauf, sondern ein vollständig
geplanter, implementierter, auditierter und lokal verifizierter Pfad zu
einem besseren Schüler — **ohne neuen Teacher-Pass und ohne neue GPU-Miete**.

Arbeitsort: `G:\C0ding\git\wmkeyboard-wmlm` (Branch `wmlm-de-research`).
Die Artefakte liegen dort unter `wmk-glide/artifacts/`, nicht im Worktree.

## Zuerst lesen

1. `wmk-glide/HANDOFF.md`
2. `wmk-glide/wmlm-training-plan.md` (§1.3, §4, §7)
3. `wmk-glide/artifacts/README.md`
4. `wmk-glide/cloud/scaleway/README.md`
5. `wmk-glide/cloud/scaleway/NEXT-SESSION-H100.md` (was im H100-Lauf passiert ist)
6. Dieses Dokument vollständig, inklusive der Messwerte unten.

## Ausgangslage (gemessen, nicht geschätzt)

**Gesicherte Assets (lokal, SHA-verifiziert):**

| Datei | Größe | Inhalt |
|---|---:|---|
| `artifacts/out/de_soft_1m2.npz` | 623 MB | 1.199.989 Sätze, 12.956.013 Zeilen, top-24 |
| `artifacts/out/de_soft_2m.npz` | 1.027 MB | 1.979.982 Sätze, 21.378.590 Zeilen, top-24 |
| `artifacts/out/de_lm_2m/` | 181 MB | `train.npz` 1.980.000 Sätze / 40.556.654 Tokens, `vocab.txt` 24.576, `heldout.npz` 20k |
| `artifacts/models/de_context_1m2.wmlm` | 10,86 MB | d256/6/4/768/ctx40, 30k Steps |
| `artifacts/models/de_context_2m.wmlm` | 10,86 MB | d256/6/4/768/ctx40, 90k Steps |
| `artifacts/out/eval_1m2/`, `eval_2m/` | klein | typing + glide + comp3 |
| `artifacts/out/audit_soft.json`, `audit_signal.json` | klein | Daten-Audit dieser Session |

Die beiden Soft-Target-Dateien sind **verschachtelt** (gleiche geseedete
Permutation; 2M enthält 1,2M).

**Ergebnisse (identischer Harness, 2.588 Wischer / 500 Tipp-Fälle):**

| Metrik | 4B/150k | 27B/1,2M@30k | 27B/2M@90k |
|---|---:|---:|---:|
| Glide 150k top-1/top-4 | 77,40/83,46 | 76,82/83,38 | 77,28/83,46 |
| Glide comp3 top-1/top-4 | 78,48/84,89 | 77,94/84,89 | 78,48/84,85 |
| Tippen LM top-1/top-3 | 62,00/79,40 | 63,80/78,60 | 62,20/78,60 |
| Nächstes Wort top-1/top-3 | 14,92/24,46 | 15,05/25,40 | 16,80/27,55 |
| Heldout-ppl (gleicher Split) | n. v. | 74,8 | **68,0** |

`n. v.` = nicht vergleichbar: der 150k-Wert 76,7 stammt von einem anderen
Heldout. **Vergleiche niemals Perplexitäten über verschiedene Korpora.**

**Statistische Auflösung (wichtig):** Bei n=2.588 sind ±1,2 pp, bei n=500
±3,1 pp Zufallsbreite. Alle Glide-/Typing-Deltas haben |z| < 1,2; sie sind
**nicht signifikant**. Für 1 pp braucht es ~27.800 Wischer bzw. ~37.000
Tipp-Fälle. Jede Aussage „Modell A ist besser“ braucht künftig gepaarte
Tests (McNemar) mit Item-Dumps.

**Audit-Befunde (Kern dieser Session):**

| Befund | Wert |
|---|---:|
| Zeilen ohne Target (erstes Wort jedes Satzes, `k=1`-Bug im Generator) | 9,38 % |
| Ziel-Token ist Subword-Piece → kann nie in Top-24 stehen | 15,3 % |
| Top-24-Recall bei Klartext-Wörtern | 96,4 % |
| Top-1-Accuracy bei Klartext-Wörtern | 24,3 % |
| Zeilen mit ≤3 Kandidaten (Renormierungsrauschen) | 2,54 % |
| Zeilenmasse | exakt 1,0 → `probs = v/total`, Tail verworfen |
| Permanente Teacher-Fehler (2M) | 18 (0,0009 %), alle „sentence too short“ |
| High-NLL akzeptiert (2M-Stufe) | 729 (0,037 %) |

**Trainingskurven:** 1,2M@30k war **nicht konvergiert** (77,7 → 74,8 zwischen
25k und 30k). 2M hatte den Bestwert bei **85k** (67,5), bei 90k 68,0.
`best.pt` ist der 85k-Checkpoint.

**Lokale Hardware:** Ryzen 9 3900X (24 Threads), 32 GB RAM,
**Radeon RX 9060 XT (RDNA4, gfx1201)**. DirectML getestet: synthetisch
3,17 Steps/s mit den echten Modellmaßen; echter `train.py` **ohne**
Distill-Loss 1,75 Steps/s; **mit** Distill-Loss Crash:
`DirectML scatter doesn't allow partially modified dimensions` (Backward von
`torch.gather` in `distill_loss`, `tools/wmlm/train.py:88`).

## Harte Regeln dieser Session

1. **Keine GPU-Miete.** Kein Scaleway, kein Cloud-Anbieter. Alles lokal
   (CPU oder 9060 XT) planen, bauen, testen, auditieren.
2. **Kein Teacher-Neulauf.** Die vorhandenen Soft-Targets sind das Asset.
   Ein Neulauf ist nur als *optionaler, klar bepreister Vorschlag* am Ende
   erlaubt (Entscheidung durch den Nutzer).
3. **Nichts committen/pushen**, solange der Plan nicht auditiert ist.
   Keine Secrets, keine Binaries >5 MB.
4. **Keine unbelegten Zahlen.** Jede Behauptung mit Datei:Zeile oder Messung.

## Auftrag

Baue den vollständigen Plan **und** die dafür nötigen Artefakte für ein
bestmögliches Schüler-Ergebnis ohne Lehrer-Neulauf. Nutze dafür die
autonome, orchestrierte Subagent-Pipeline

**research → plan → implement → audit → fix → verify → finalize**

mit klaren Übergabeverträgen (siehe unten). Jede Stufe liefert ein
Artefakt, das die nächste Stufe als Eingabe bekommt; keine Stufe darf die
vorherige überspringen.

### A) Research (breit, belegt)

1. **Zielstruktur der Destillation.** Recherchiere und belege:
   - top-k-Destillation mit renormiertem Tail: Effekte auf Kalibrierung und
     Generalisierung; Alternativen (Tail-Masse als „other“-Klasse,
     unnormalisiertes KL, temperature-scaled KD, CE+KD-Mischung).
   - Umgang mit OOV/Subword-Zielen: Piece-Targets, Spelling-Korrektur,
     Maskierung statt falscher Targets.
   - Erstes Wort / Satzanfang als Target: wie andere Pipelines das lösen.
2. **Lehrerfreie Verbesserungen.** Systematisch prüfen, was ohne neuen
   Teacher geht: Maskierung, Gewichtung, Alpha/Share-Sweep, LR/Steps,
   Batch/ctx, Vokabular/Pieces, Datenmischung, Curriculum, Self-Distillation,
   EMA/Checkpoint-Averaging, Quantisierung des Schülers.
3. **9060 XT (live recherchieren, nicht raten).** Aktueller Stand (2026) zu:
   - PyTorch + ROCm unter WSL2 für gfx1201: supported? Welche ROCm-Version,
     welche Wheel-URL, welche Kernel-/Treibervoraussetzungen?
   - `torch-directml`: aktuelle Version, unterstützte Ops, Workarounds für
     `gather`/`scatter`-Backward (z. B. `take_along_dim`, `index_select`,
     One-Hot-Matmul), Performance char- und modellabhängig.
   - ONNX Runtime DirectML als Trainingsbackend (geht das? Grenzen).
   - Alternative: CPU-Training mit `torch.compile`/oneDNN, Threading,
     bf16; realistische Steps/s.
   - Jede Quelle mit URL und Datum; keine Blogposts als einzige Grundlage.
4. **Messmethodik.** Wie man mit kleinen n trotzdem belastbar vergleicht:
   gepaarte Tests, Bootstrap-CIs, Item-Dumps im Harness, Power-Analyse.

### B) Plan (vollständig, entscheidbar)

Ein Dokument `wmk-glide/plans/teacher-free-plan.md` mit:

1. **Datenaufbereitung** — vollständige Pipeline-Spezifikation:
   - Welche Dateien entstehen (Namen, Schema, Größe, Hash), ausgehend von
     `de_soft_2m.npz` + `de_lm_2m`.
   - Ableitungen: Masken (Piece-Zeilen, leere Zeilen, High-NLL), Gewichte
     (Kandidatenzahl als Masse-Proxy), Split (train/val mit fester Seed),
     ggf. Teilmengen für schnelle Iteration (10k/100k/500k).
   - Regeln gegen Leaks: Heldout unangetastet, keine Überschneidung,
     deterministische Seeds, dokumentierte Ausschlüsse.
   - Prüfsummen und Invarianten (Zeilen, Sätze, Masse, streng steigende IDs).
2. **Trainingsvarianten** — Matrix mit erwartetem Effekt, Kosten (lokal!) und
   Abbruchkriterium. Mindestens:
   - V0 CE-only (Kontrolle, kein Distill)
   - V1 Status quo (alpha 0.5/share 0.5)
   - V2 Piece-Zeilen maskiert
   - V3 Maskiert + Gewichtung nach Kandidatenzahl
   - V4 1,2M mit 60k Steps (Untertrainierungs-Test)
   - V5 alpha/share-Sweep (z. B. 0.3/0.7, 0.7/0.3)
   - V6 2M mit 60k/120k (Plateau-Test)
   - V7 Checkpoint-Averaging/EMA
   - Jede Variante: exakt eine Änderung gegenüber der Referenz.
3. **Evaluationsplan** — wie wir trotz kleiner n entscheiden:
   - Harness um Item-Dumps erweitern (pro Wischer/Tippfall: richtig/falsch),
     McNemar/Bootstrap, Power-Rechnung.
   - Mindestens ein zusätzlicher, domänenferner Test (z. B. eigener
     Heldout-Split aus News vs. Chat getrennt).
4. **9060-XT-Validierungsplan** — konkrete Experimente mit Abbruchkriterien:
   - DirectML: Loss-Workaround bauen, 2.000 Steps, Loss-Kurve gegen CPU
     vergleichen, Steps/s messen.
   - ROCm/WSL: gfx1201-Verfügbarkeit prüfen (`rocminfo`), Docker
     `rocm/pytorch` testen, 2.000 Steps.
   - Entscheidungsregel: Welches Backend wird für welche Experimente genutzt?
5. **Risiko- und Fehlerkatalog** — mit Gegenmaßnahme je Eintrag:
   - Datenfehler (Piece-Ziele, leere Zeilen, Renormierung, High-NLL).
   - Korrelationsfallen: 1,2M ⊂ 2M; Korpusgröße vs. Steps; Register/Feld
     sind 1:1 (chat↔casual, news↔formal); OpenSubtitles nicht trennbar;
     Domänennähe der Eval-Wortliste; ppl nur bei gleichem Heldout.
   - Unklarheiten, die der Nutzer entscheiden muss (Liste, nicht raten).
6. **Kosten-/Zeitplan** lokal vs. optionaler Cloud-Neulauf (nur als Option).

### C) Implement (lokal, ohne GPU-Miete)

Baue die Artefakte, die der Plan verlangt — mindestens:
- `wmk-glide/tools/wmlm/soft_mask.py` (Masken/Gewichte aus dem npz erzeugen,
  deterministisch, mit Invarianten-Checks)
- `wmk-glide/tools/wmlm/train.py`-Erweiterung: optionales `distill_mask=` und
  `distill_weight=` (rückwärtskompatibel, Default = heutiges Verhalten)
- Harness-Item-Dumps + Auswerteskript (`paired_eval.py`)
- 9060-XT-Runner (`wmk-glide/cloud/local/`): DirectML-Workaround,
  Benchmark-Skript, Vergleich gegen CPU
- kleine Testdaten (10k-Zeilen-Slice) für schnelle Iteration
Jede Änderung mit Test, der ohne GPU läuft.

### D) Audit (unabhängig, adversarial)

Ein separater Audit-Subagent prüft:
- Korrektheit der Masken/Gewichte gegen das npz (Stichproben + Invarianten).
- Ob die Loss-Änderung das Verhalten im Default-Fall **exakt** erhält.
- Ob die Evaluationsstatistik korrekt ist (Power, gepaarte Tests, CIs).
- Ob der Plan Leaks, Zirkelschlüsse oder Korrelationsfallen enthält.
- Ob die 9060-XT-Aussagen belegt sind (Quelle, Datum, Reproduktion).
Ausgabe: Findings mit Datei:Zeile, Schwere, Confidence; `NO_FINDINGS` erlaubt.

### E) Fix + Verify

Behebe alle Audit-Findings mit hoher Confidence. Verifiziere:
- `python -m py_compile` für alle geänderten Python-Dateien
- Unit-Tests ohne GPU (Masken, Gewichte, Loss-Default)
- ein 2.000-Step-Lauf auf CPU mit der 10k-Slice (Loss endlich, ppl sinkt)
- Harness-Dumps + `paired_eval.py` auf den vorhandenen Eval-Daten
- 9060-XT-Reproduktion (DirectML oder ROCm) mit gemessenen Steps/s

### F) Finalize

Liefere:
1. `wmk-glide/plans/teacher-free-plan.md` (final, mit Audit-Vermerk)
2. `wmk-glide/plans/teacher-free-results.md` (was lokal gemessen wurde)
3. Die implementierten Skripte + Tests
4. Eine priorisierte Empfehlung: welche 3 Varianten zuerst, mit erwartetem
   Effekt und lokalem Zeitbedarf; plus **optional** der eine Cloud-Lauf, der
   sich danach lohnt (Kosten, Dauer, Abbruchkriterien).
5. Offene Entscheidungen für den Nutzer (max. 5, präzise formuliert).

## Subagent-Pipeline (verbindlich)

| Stufe | Agent | Eingabe | Ausgabe | Darf nicht |
|---|---|---|---|---|
| research | `explore`/`librarian` + `websearch` | Fragen A1–A4 | `research-notes.md` mit Quellen | implementieren |
| plan | `oracle`/`plan` | Notes + dieser Prompt | `teacher-free-plan.md` | Code ändern |
| implement | `general`/`code` | Plan | Code + Tests | Plan umdeuten |
| audit | `reviewer`/`review-*` | Diff + Plan | Findings-JSON | fixen |
| fix | `code` | Findings | Patches | neue Features |
| verify | `code` + Shell | Patches | Messprotokoll | Findings ignorieren |
| finalize | Hauptagent | alles | Ergebnisdokument | ungeprüfte Zahlen |

Jede Stufe schreibt ihr Artefakt als Datei; die nächste Stufe zitiert es.
Bei Widerspruch zwischen Plan und Befund gilt der Befund, und der Plan wird
korrigiert — nicht umgekehrt.

## Akzeptanzkriterien (Gates)

1. Plan enthält für **jede** Variante: Hypothese, eine Änderung, Messgröße,
   Abbruchkriterium, erwartete Laufzeit lokal.
2. Jede Datenableitung hat ein Schema, einen Hash und einen Invarianten-Test.
3. Loss-Default ist bitgleich zum heutigen Verhalten (Test belegt es).
4. Audit ohne offene High-Confidence-Findings.
5. Lokaler 2.000-Step-Lauf konvergiert (Loss fällt, endlich, keine NaNs).
6. 9060-XT-Aussage ist entweder reproduziert oder ausdrücklich als
   „nicht reproduzierbar“ dokumentiert — mit Quelle und Fehlermeldung.
7. Keine Cloud-Ausgabe, keine GPU-Miete, kein Push.

## Bekannte Fallen (nicht wiederholen)

- **ppl über Korpora vergleichen.** Nur gleicher Heldout ist vergleichbar.
- **„Top-1 35 %“ als Accuracy lesen.** Das war `top1_mass` im A/B.
- **Glide-Deltas <1 pp als Effekt verkaufen.** Das ist Rauschen bei n=2.588.
- **1,2M und 2M als reine Größenvergleiche deuten.** Steps und Epochen
  unterscheiden sich; 1,2M war untertrainiert.
- **Register/Feld als Datenquelle interpretieren.** `chat`↔`casual` und
  `news`↔`formal` sind 1:1; OpenSubtitles ist darin nicht trennbar.
- **Piece-Tokens als „normale“ Ziele behandeln.** Sie können im aktuellen
  Format nie getroffen werden.
- **DirectML-Erfolg aus dem Forward schließen.** Der Backward von `gather`
  scheitert; erst 2.000 echte Steps zählen.
