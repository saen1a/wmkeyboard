# WMK Glide-Typing – Arbeitsstand und Wissen

Stand: 27.10.2026, Nachtrag Reranker-Blend / Join-Guard / Komposita-Liste (Layout optional). Dieses
Dokument ist der Fortsetzungspunkt: was gemessen ist, was offen ist, wo die
Artefakte liegen, und wie man jede Zahl neu zieht. Alles hier ist entweder in
diesem Ordner oder mit einem der Kommandos unten reproduzierbar. Die Änderungen
selbst liegen als Patches gegen `22d5020b` in [`patches/`](patches/README.md).
Der Research-Stand ist auf Forgejo gepusht; ein Upstream-PR ist nicht erstellt, und
neue Upstream-Issues/Kommentare gehen mit dem vorhandenen Token nicht.

## 1. Artefakte

| Datei | Inhalt |
|---|---|
| [`issue-tuning-per-language.md`](issue-tuning-per-language.md) | Der Issue-Entwurf, gepostet als [wasi-master/wmkeyboard#966](https://github.com/wasi-master/wmkeyboard/issues/966) |
| [`issue-966-comment.md`](issue-966-comment.md) | Review-Kommentar zum umgesetzten Stand (kurze Fassung) |
| [`issue-966-followup.md`](issue-966-followup.md) | Nachtrag-Kommentar zu #966: Blend, Join-Guard, Komposita-Liste, Tests — offline formuliert, **noch nicht gepostet** (das Issue #966 selbst ist gepostet) |
| [`issue-german-wmlm.md`](issue-german-wmlm.md) | Feature-Request-Entwurf: deutsches `.wmlm` trainieren/veröffentlichen, mit der Größe des englischen Datensatzes |
| [`experiments-followup.md`](experiments-followup.md) | Nächste Stufe getestet: Halte-Test, breiterer Pool, Trigramm, Cache, Logit, Komposita-Prior, Kontextquelle, Frequenz-Exponent, Diakritika — mit Negativ-Ergebnissen |
| [`ngram-analysis.md`](ngram-analysis.md) | N-Gramm-Analyse: Chat-/Register-Pack +2,71, Trigramm/4-Gramm, Deckel, Normalisierung; Messungen und Prioritäten |
| [`wmlm-gain.md`](wmlm-gain.md) | Wie viel ein deutsches `.wmlm` bringt: englischer Proxy mit dem echten Modell, +4,9 top-1 im Glide, Schätzung +3–5 für Deutsch |
| [`wmlm-training-windows.md`](wmlm-training-windows.md) | Trainingsweg für die RX 9060 XT (WSL2 statt Windows-native), Lehrer-/VRAM-Wahl, Token-Abdeckung, Rezept und Kosten (lokal, Cloud, API) |
| [`experiments/`](experiments/README.md) | Die Skripte dazu (Forschungscode, nicht ausgeliefert) |
| [`analyse-de.md`](analyse-de.md) | Erster Durchgang: Einstellungen, Fehlerklassen, Speicher (mit Nachtrag) |
| [`data/wmk-glide-de-data.zip`](data/wmk-glide-de-data.zip) | 5,0 MB Messdaten: 2.594 deutsche Züge, beide Layouts, 150k-Liste, Patches, Lizenz-README |
| [`data/wmk-settings-de-optimized.wmconfig.json`](data/wmk-settings-de-optimized.wmconfig.json) | Importierbares WMK-Profil (140 Einstellungen, keine Secrets) |
| [`tools/decompound.py`](tools/decompound.py) | Komposita-Generator 1 (nach Teilfrequenz) – gemessen, verworfen |
| [`tools/decompound2.py`](tools/decompound2.py) | Komposita-Generator 2 (nach Produktivität) – gemessen, verworfen |
| [`tools/shape_seed_bench.rs`](tools/shape_seed_bench.rs) | Seeding-Benchmark: linear vs. Quadrat-Schranke vs. Startzellen-Bucket |
| [`tools/rerank_eval.py`](tools/rerank_eval.py) | Reranker-Experiment: Bigramm über den Decoder-Pool, Pool-/α-Sweep, Gap-Verteilung |
| [`tools/blend_cap_eval.py`](tools/blend_cap_eval.py) | Derselbe Pool, aber mit dem ausgelieferten Deckel: `clamp(w·ΔlnP, ±cap)`, Cap-/Gewichts-Sweep |
| [`tools/synth_layout_eval.py`](tools/synth_layout_eval.py) | Synthetische Züge auf Long-Press-, a–z- und Umlaut-Tasten-Gitter; reproduziert §2.5 |
| [`tools/join_oracle.py`](tools/join_oracle.py) | Komposita-Obergrenze: Ziele außerhalb der Liste, die in zwei Listenwörter zerfallen |
| [`tools/wmlm_token_coverage.py`](tools/wmlm_token_coverage.py) | Abdeckungstest für `distill.py`: Ein-Token-Wörter je Lehrer-Tokenizer (Qwen 20,1 %, Gemma 3 4B 32,6 % auf Deutsch) |
| [`tools/build_compound_list.py`](tools/build_compound_list.py) | Baut die 150k-Liste plus 441k echte Komposita aus `de_full.txt` (der größte deutsche Hebel, §2.6.4) |
| [`tools/harness.patch`](tools/harness.patch) | `COLS`, `ALL`, `DUMP`, `RESULTS`, `SHAPES` für `glide_beam_eval` (Stand vor `22d5020b`; der aktuelle Harness steckt in `patches/0000`) |
| [`tools/freq_weight.patch`](tools/freq_weight.patch) | `freq_weight` + Längenprior als Diff gegen `wm-engine` (nur für den Prototyp) |
| [`patches/`](patches/README.md) | Vier Patches gegen `22d5020b`: Harness, Glide-Blend, Join-Guard, Tests/CI. Der Layout-Patch ist optional und liegt in `experiments/`; Anwendungsreihenfolge und Zahlen im README |

## 2. Belastete Zahlen

Alles **Erfolg pro Wisch** (Top-1; ein Wort, das die Liste nicht kennt, ist ein Fehler),
Decoder ohne Handmodell, Rerank und persönliches Lexikon – also Untergrenzen.

### 2.1 Der Decoder, ausgeliefert

| Korpus | Züge | Ergebnis |
|---|---|---|
| FUTO Deutsch (Wikipedia-Sätze, 150k-Liste) | 2.588 | **71,45 %** (Top-4: 82,30 %) |
| HeliBoard Deutsch (seltene Wörter, a–z) | 10.908 | **21,93 %** |
| Englisch (FUTO-Test, gebündelte 17k-Liste) | 2.129 | 81,49 % |

HeliBoard ist kein Decoder-Problem: 16,2 % der Ziele enthalten `ä ö ü ß` (auf a–z nicht
produzierbar), 28 % stehen nicht in der Liste, die Ziele liegen im Median auf Rang 20.714.
Reine Form mit 1.400 Kandidaten: **78,5 %** gegen 88,8 % bei FUTO. Striche sind sogar
präziser (0,15 gegen 0,33 Keybreiten Abstand zur Ideallinie).

### 2.2 Was hilft (gemessen)

| Maßnahme | FUTO de | HeliBoard de | English |
|---|---|---|---|
| Sprachprofil `freq 0.5` + `gap 2.0` | 74,27 (+2,9) | 32,51 (+10,6) | 80,41 (−1,1) |
| gelernte Formen (1 Form/Wort) | 73,96 (+2,6) | 24,77 (+2,8) | – |
| Profil + Formen | **76,55 (+5,1)** | – | – |
| 32 Buchstaben + feinere Abtastung | +0,08 gesamt, **15+ : 21,05 → 23,7 %** | – | – |
| Seed-Index (Startzellen) | 65,7 → 12,0 µs/Abfrage (5,5×) | – | – |

Die 74,27 sind der frühere Lauf; die Nachmessung auf `22d5020b` in §2.6.1 ergibt 74,15.
Die Differenz ist `RESULTS`/Engine-Revision, kein neuer Fehler. Der englische Preis ist
**−1,1** für `freq 0.5` + `gap 2.0`; das ältere Drei-Konstanten-Profil (gap/shape/channel)
kostete **−1,7** (Issue §4.2), weil es zusätzlich `shape_weight` und `shape_channel` bewegt.

### 2.3 Was nicht hilft (negativ gemessen)

| Versuch | Ergebnis |
|---|---|
| Radien weiter (`end` 2,2/2,6, `start` 2,0) | 0 bis −2,5 Punkte |
| `sigma` 0,50/0,60 für ungenaue Hände | nur bei *systematischem* Versatz, den `KeyOffsets` schon lernt; bei Zufallsrauschen −0,8 bis −4,3 |
| Kandidatenbreite `k` 4→8→16→32 | +0,08 Punkte (inert) |
| Längenprior aus Bogenlänge | +0,46 Punkte |
| Komposita in die Wortliste generieren | 0,8–1,7 % echte Wörter, 0/216 bzw. 3/216 Ziele, netto −11 bis −18 Züge |
| Größere Liste statt Komposita | 1,16 Mio: 72,41 % (Oracle 76,31 %; mit deutschem Profil 75,46, §2.6.4) |
| **Komposita im Decoder** (`join_cost 3.0`) | **66,11 / 13,04** – siehe §4.1 |

### 2.4 Der Reranker (gemessen; für Deutsch ohne `.wmlm` inert)

Top-8 je Zug gedumpt, Bigramm-Modell aus den Korpus-Sätzen, neu sortiert mit
`score + α·ln P(w|vorgänger)`. Nur Züge mit Vorgängerwort (n=2.294), Basis **70,84 %**.
Der größte deutsche Hebel ist inzwischen die echte Komposita-Liste (§2.6.4), nicht der
Reranker: ohne deutsches `.wmlm` ist der Score-Blend auf dem Gerät ein No-op (§0b in
[`experiments-followup.md`](experiments-followup.md)).

| Pool | α=1 | α=2 | α=3 |
|---|---|---|---|
| 2 | 78,07 | 78,16 | 78,16 |
| **4** | 82,04 | **82,13** | 82,08 |
| 6 | 82,78 | **83,00** | 82,96 |
| 8 | 82,91 | **83,09** | 83,04 |

- Deckung: richtiges Wort in Top-4 **82,81 %**, in Top-8 **83,77 %** → Pool verbreitern
  bringt höchstens 1 Punkt. Der Kontext ist der Hebel — **wenn ein Modell da ist**; für
  Deutsch fehlt das `.wmlm` (§2.6.1, §0b in `experiments-followup.md`).
- Bei den 317 Fehlschlägen mit Ziel im Pool: Abstand zum Führenden **median 1,32 Nats**
  (Q3 2,39, P90 3,95, max 7,81).
- Der getippte Pfad nutzt `blendContextModel` mit `LM_BLEND_CAP = 1.0`; **1 Nat erreicht
  39,1 % dieser Fehlschläge**, 2 Nats 65,6 %, 3 Nats 82,6 %.
- Der Glide-Pfad nutzte bis zu diesem Patch nur `NgramReranker.rerank` (Rang-Umsortierung,
  `LM_WEIGHT = 0.0`), **nicht** den Score-Blend. Seit §2.6.1 blendet
  `blendGlideContextModel` vor dem Rang-Rerank, Deckel 3,0. Die Tabelle oben ist der
  ungedeckelte Sweep, der die Obergrenze festlegt.

### 2.5 Layout: QWERTZ behalten, Umlaute als Long-Press (eigene Tasten nur optional)

Zwei Messungen auf der Top-20k-Liste (19.446 Wörter, 132 Mio. Token):

1. **Umlaut-Zwillinge.** 242 Wortpaare unterscheiden sich nur durch `ä/ö/ü/ß` und sind
   beide echte Wörter (`wär`/`war`, `schön`/`schon`, `würde`/`wurde`, `hätte`/`hatte`,
   `könnte`/`konnte`, `weiß`/`weiss`). Sie decken **7,1 % aller Token**. Auf dem heutigen
   Layout liegen beide Schreibweisen auf derselben Key-Mitte – die Geometrie kann sie
   nicht trennen, nur die Frequenz.
2. **Kollineare Trigramme** (das mittlere Zeichen liegt auf der Linie der Nachbarn, trägt
   also keine Forminformation; frequenzgewichtet): QWERTZ **10,82 %**, Neo 2 15,39 %,
   Colemak 15,74 %, Dvorak 17,22 %. Pfadlänge pro Wort: QWERTZ 12,52, Neo 2 12,97,
   Dvorak 14,24 Keybreiten. Tipp-optimierte Layouts (Handwechsel) sind für **einen**
   Finger das falsche Ziel.

**Synthetischer Decoder-Test** (neu gebaut in §2.6.3: 1.324 Wörter, deutsches Profil,
Rauschen 0,05 Keybreiten):

| Gitter | top-1 |
|---|---|
| Long-Press (heute) | 96,37 % |
| nur a–z im Key-Map | 85,57 % |
| `ü ö ä ß` als Tasten | **97,73 %** |

Der frühere 77,34/90,11-Lauf war ein a–z-Key-Map und ist mit dem gespeicherten Werkzeug
nicht reproduziert; der Long-Press ist für den Decoder sichtbar. Der Mechanismus ist
exakt (der Zug für `würde` und `wurde` ist identisch), die Züge sind synthetisch, also
sind die absoluten Zahlen optimistisch.

**Ergebnis:** Der Long-Press ist für den Decoder sichtbar; der nachgebaute Test
(§2.6.3) misst 96,37 % gegen 97,73 % mit eigenen Tasten, also **+1,36**, nicht +12,8.
Der Layout-Wechsel ist deshalb **nicht als Erkennungs-Hebel übernommen**; die App bleibt
beim Long-Press. Der Patch `experiments/german-umlaut-keys.patch` ist optional, wenn das
Layout ohnehin angefasst wird. Technische Notiz für den Fall: die Long-Press-Einträge für
`ä ö ü ß` müssen dann **entfernt** werden – `GlideKeyMap.of` nimmt das erste Zeichen an
einer Position (`putIfAbsent`, Basis vor Long-Press), sonst bleibt der Umlaut auf der
Basistaste und die neue Taste ist für den Decoder unsichtbar. Der Wechsel setzt gelernte
Formen und Hand-Offsets zurück (am Layout-Fingerprint), und die Reihen werden ~9 %
schmaler (10 → 11 Tasten).

### 2.6 Nachtrag: Blend, Join-Guard, Komposita-Liste (Layout nur als Nachtrag)

Alles gegen `22d5020b`, FUTO Deutsch, `ALL=1 RESULTS=4 COLS=11 THREADS=8`, n = 2.588.
Die Patches dazu: [`patches/`](patches/README.md).

#### 2.6.1 Reranker-Blend im Glide-Pfad

`SuggestionEngine.blendGlideContextModel` sitzt jetzt in `finishGlide` **vor**
`rerankGlide` (wie im Tipp-Pfad: Score-Blend, dann Rang-Rerank). Kandidaten
bewegen sich um `clamp(0,7 · (lnP(c) − lnP(Führer)), ±3,0)`; Pool bleibt
`GLIDE_RERANK_POOL = 8`.

| Deckel | Gewicht 0,5 | 0,7 | 1,0 | 1,5 |
|---|---|---|---|---|
| 1,0 | 75,41 | 75,37 | 75,33 | 75,33 |
| 1,5 | 77,07 | 77,03 | 76,94 | 76,94 |
| 2,0 | 78,60 | 78,47 | 78,38 | 78,33 |
| 2,5 | 79,82 | 79,86 | 79,60 | 79,56 |
| **3,0** | 80,73 | **80,82** | 80,56 | 80,21 |
| 4,0 | 81,34 | 81,73 | 81,65 | 81,26 |
| ohne | 81,65 | 82,39 | 82,91 | **83,13** |

Basis auf denselben 2.294 Zügen mit Vorgängerwort: **70,84 %**. Ausgeliefert
wird 0,7/3,0 = **80,82 %** (+9,98); ohne Deckel wären es 82,39 bei gleichem
Gewicht, 83,13 beim besten Gewicht 1,5. **Achtung: in-sample.** Das Korpus-
Bigramm kennt die Testsätze. Auf einem 20-%-Satz-Split (LM auf den anderen
80 %) sind es **68,97 → 69,17 (+0,20)**; das Train-LM hat nur 1.293 Wörter.
Das echte `.wmlm` muss den Gerätegewinn zeigen, siehe
[`experiments-followup.md`](experiments-followup.md) §0. **Wichtiger:** Es gibt
**kein deutsches `.wmlm`**; `ContextModelCatalog` listet nur `en` und
`bn_rom`. Auf Deutsch ist `contextModel` null und der Blend ein No-op. Der
deutsche n-gram-Pack als Rang-Rerank (der `NgramReranker`-Weg) bringt +0,45;
als Score-Blend −1,0; als Kontextquelle 0,4–1,2 %. Ein deutsches `.wmlm` muss
erst trainiert/veröffentlicht werden (`tools/wmlm`). Ein echtes Modell bringt
nach dem englischen Proxy **+4,9 top-1** im Glide (0,7/3,0), bis +5,8 ohne
Deckel; Schätzung für Deutsch +3–5, siehe [`wmlm-gain.md`](wmlm-gain.md). Der
lokale Trainingsweg (WSL2, 4B-Grenze, API-Kosten) und der größte
Lehrer-Engpass — `distill.py` mappt nur Ein-Token-Wörter, Qwen 20,1 %,
Gemma 3 4B 32,6 % der deutschen Worttypen — stehen in
[`wmlm-training-windows.md`](wmlm-training-windows.md). Die
Obergrenze aus §2.4 (Pool 4,
α = 2, ohne Deckel) bleibt 82,13. Das Sprachmodell in dieser Messung ist ein
Korpus-Bigramm (derselbe Ersatz wie `rerank_eval.py`), nicht das
heruntergeladene `.wmlm`; die Form ist die ausgelieferte.

```sh
# Pool dumpen (gepatchter Harness), dann den Deckel-Sweep fahren
ALL=1 THREADS=8 RESULTS=8 COLS=11 DUMP=pool.jsonl \
    ./target/release/examples/glide_beam_eval de_swipes.jsonl german.json de_150k.txt
python3 tools/blend_cap_eval.py pool.jsonl de_swipes.jsonl
```

#### 2.6.2 Komposita-Guard statt Konstante

Der Join hat jetzt zwei Bremsen: `joinMinPart` (mindestens vier Buchstaben je
Teil) und `joinPartPenalty · ln(1 + Teilfrequenz)` je abgeschlossenem Teil.
Deutsches Profil: `joinCost 8,0`, `joinMinPart 4`, `joinPartPenalty 0,1`.

| Lauf (deutsches Profil) | top-1 | top-4 |
|---|---|---|
| ohne Join | 74,15 | 82,81 |
| `join_cost 3,0` (alt) | 70,63 | 79,60 |
| **Guard 8,0 / 4 / 0,1** | **74,61** | **83,31** |

Der Guard holt +0,46 top-1 und +0,50 top-4 gegenüber „ohne Join“ und dreht
den alten Verlust von −3,52 in ein Plus. Die Oracle-Obergrenze (Ziel fehlt in
der Liste, zerfällt in zwei Listenwörter ≥ 3 Buchstaben) ist **118/2.588 =
4,56 %**; davon holt der Guard rund ein Zehntel. Der Rest braucht ein
Komposita-Sprachmodell, keine weitere Konstante: die richtigen Teile
(`bundes` 122 + `ministerium` 903) sind zu selten gegen falsche Splits aus
häufigen Wörtern (`binden` + `nun`).

Ein nachträglicher Margin-Filter („Join nur, wenn er den besten Ein-Wort-Leser
um m Nats schlägt“) wurde auf den Join-Dumps geprüft: bei `join_cost 3` holt er
mit m = 3 nur 68,70 statt 66,11 (Baseline 71,45, ausgelieferte Gewichte), bei
`join_cost` 8/10 ist er neutral bis leicht negativ. Deshalb der Length/Penalty-
Guard statt des Margins.

```sh
python3 tools/join_oracle.py de_swipes.jsonl de_150k.txt
echo "freq_weight=0.5 gap_weight=2.0 join_cost=8 join_min_part=4 join_part_penalty=0.1" | \
  COLS=11 ALL=1 THREADS=8 RESULTS=4 ./target/release/examples/glide_beam_eval \
    de_swipes.jsonl german.json de_150k.txt
```

#### 2.6.3 Umlaut-Tasten: die synthetische Messung neu gezogen

**Nutzen klein; nicht als Issue-Vorschlag übernommen.** Die Messung bleibt als
interne Evidenz, damit die Zahl nicht später als größerer Hebel wiederkommt.

Das alte Synthetik-Werkzeug ist nicht gespeichert; [`tools/synth_layout_eval.py`](tools/synth_layout_eval.py)
baut es nach (1.324 häufige Wörter, Key-Mitten, Rauschen 0,05 Keybreiten,
deutsches Profil). Drei Gitter:

| Gitter | top-1 | top-4 |
|---|---|---|
| Long-Press, Umlaut auf der Basistaste (was die App heute baut) | 96,37 % | 100,00 % |
| nur a–z im Key-Map (die alte 77-%-Untergrenze) | 85,57 % | 87,46 % |
| `ü ö ä ß` als eigene Tasten (11 Spalten) | **97,73 %** | **100,00 %** |

Gewinn **+1,36 Punkte** bei Rauschen 0,05; +1,28 bei 0,10, +1,43 bei 0,15,
+1,06 bei 0,20. Die absoluten Zahlen sind optimistisch (keine echten Pausen/
Schlaufen); der Unterschied ist das Signal. Wichtig: die App-Long-Press ist für
den Decoder **sichtbar** (`GlideKeyMap.of` legt ü/ö/ä/ß auf die Basistaste), das
ist das erste Gitter. Die frühere Zahl 77,34 % entspricht eher dem a–z-Gitter
(85,57 % hier, andere Wortliste/Saat). Auf echten FUTO-Zügen ändert die
`ß`-Taste nichts (71,45 → 71,45): FUTO zeichnet auf einem Gitter mit ü/ö/ä, und
die 34 ß-Ziele wurden nicht auf einer ß-Taste gezogen.

```sh
python3 tools/synth_layout_eval.py --words de_150k.txt \
    --engine /pfad/zu/wmkeyboard/native/wm-engine --targets 1324 --noise 0.05
```

#### 2.6.4 Der größte deutsche Hebel: echte Komposita in die Wortliste

Die 150k-Liste verliert die Komposita, die Leute wischen. **Generierte**
Komposita waren ein Nettoverlust; **echte** Komposita aus `de_full` sind etwas
anderes. Konstruktion: jedes `de_full`-Wort, das nicht in `de_150k` steht und
in zwei `de_150k`-Wörter zerfällt (Teile ≥ 3), mit seiner echten Frequenz
anhängen — **441.470 beobachtete Wörter**, keine Erfindungen.

| Wortliste (deutsches Profil) | top-1 | top-4 |
|---|---|---|
| 150k | 74,15 | 82,81 |
| **150k + 441k echte Komposita** | **75,70** | **84,23** |
| 150k + 346k (Teile ≥ 4) | 75,58 | 84,20 |
| volle 1,16-Mio-Liste | 75,46 | 84,39 |
| **150k + 441k + Join-Guard** | **75,77** | **84,47** |

Das sind **+1,55 top-1 / +1,42 top-4** aus einer Datenänderung, mehr als der
Guard (+0,46) und mehr als der deutsche Pack-Rerank (+0,45). Die kuratierte
591k-Liste ist top-1 besser als die volle 1,16-Mio-Liste, weil sie die seltenen
Nicht-Komposita nicht mitbringt. Werkzeug:
[`tools/build_compound_list.py`](tools/build_compound_list.py) (`de_150k.txt`
+ `de_full.txt` -> `de_150k_comp3.txt`). Das ist eine Wörterbuch-Erweiterung,
kein Engine-Patch.

## 3. Upstream-Stand

`origin/main` am 27.10.2026: `22d5020b`. Glide-relevante Commits seit 23.10.:

| Commit | Inhalt | Bewertung |
|---|---|---|
| `d0020afc` | Tuning auf echten Wischern gefittet (`gap 1.33`, `shape 0.5`, `channel 6`, `end 2.0`, `near 1.9`), Floor-Test, neue `.so` | Basis unserer Messungen |
| `3526e41b` | offene Enden an der Leertaste (kein Shape-Rescoring) | korrekt |
| `cb0cb305` | `freqWeight` + `GlideLanguageProfiles` (DE 0.5/2.0), JNI 27, `retuneGlide` | **verifiziert gut** |
| `cbddb079` | 32 Buchstaben, `MAX_IDEAL_POINTS 34`, `samples_for(arc)` | Tests 4/4 grün |
| `047a0b22` | Komposita im Walk (`join_cost`, min-Teilfrequenz, max. 2 Joins) | **gemessen negativ** (§4.1) |
| `7efdba4a` | Seed-Index (Startzellen-Buckets) | schnell, aber Fallback-Lücke (§4.3) |
| `b42b0bfa` | Check-up (`GlideCheckup.kt`, Screen, fit `freq_weight`) | Design passt, hier nicht kompilierbar |
| `22d5020b` | Kana-Glide (japanischer Composer) | außerhalb des deutschen Pfads |

Verifiziert: 30/30 `Tuning`-Felder Kotlin↔Rust identisch (nach den zwei
Guard-Feldern); JNI-Array 30/30 auf beiden Seiten; 496 Rust-Unit-Tests plus
3 + 5 + 4 Integrationstests grün. Die Patches sind **nicht** auf `main`; sie
liegen nur in diesem Ordner. `origin/main` läuft weiter, also vor dem nächsten
Vergleich neu klonen.

## 4. Offene Befunde

### 4.1 Komposita: Guard eingebaut, netto positiv (erledigt in §2.6.2)
Der alte `join_cost 3.0` war mit dem deutschen Profil 70,63 statt 74,15 (−3,52).
Der Guard (`joinMinPart 4`, `joinPartPenalty 0.1`, `joinCost 8.0`) macht daraus
74,61 top-1 / 83,31 top-4, also +0,46 / +0,50 gegenüber ohne Join. Die
Oracle-Obergrenze ist 4,56 % (118 Züge); der Guard holt davon rund ein Zehntel.
Der Rest ist mit Teilfrequenzen nicht erreichbar, siehe §2.6.2. **Der größere
Hebel ist die echte Komposita-Liste:** 150k + 441k beobachtete Wörter =
75,70/84,23, mit Guard 75,77/84,47 (§2.6.4); das ist eine Datenänderung, kein
Join-Tuning. Patches: `0002-compound-join-guard`. **Die deutsche Profil-Zeile
hat jetzt 8,0/4/0,1**;
ein alter 28-Werte-JNI-Aufruf schlägt laut fehl (neue Bibliothek verlangt 30),
siehe §4.2.

### 4.2 Android-`.so` und JNI-Prüfung (P0, nach dem Patch dringlicher)
Die APK trägt die eingecheckten `.so` aus `core/language/src/main/jniLibs` (F-Droid baut
aus Quelle). Der Patch hebt das Array auf **30 Werte** (zwei Guard-Felder); die neue
Bibliothek verlangt `>= 30` und liest 30. Ein alter 28-Werte-Kotlin-Aufruf gegen die
neue Bibliothek scheitert damit laut (`tuning()` → `None`), statt `joinMinPart`/
`joinPartPenalty` still zu ignorieren. Die **alte** 28-Werte-Bibliothek gegen den neuen
Kotlin-Aufruf (30) akzeptiert weiter und ignoriert die zwei Felder — deshalb: `.so`
neu bauen, bevor der Guard auf dem Gerät läuft. Prüfung auf exakte Länge (oder ein
Versionswort) bleibt offen; ein stiller Fehlschlag darf nicht wieder möglich sein.

### 4.3 Seed-Index-Fallback (P1)
`startingNear` liefert nur `null`, wenn die 3×3-Zellen **keine Form** enthalten
(`total == 0`). In echten Stores liegen dort ~40 Formen, der Fallback greift nie; eine
passende Form zwei Zellen weiter geht verloren. Fix: `found.isEmpty()` als Bedingung.

### 4.4 Zwei rote Tests + CI (erledigt)
- `glide_freq_weight::at_weight_zero_…`: setzt jetzt `shape_channel = 0.0`, grün.
- `glide_join::with_a_finite_charge_…`: Toleranz 1e-4 statt 1e-6, grün.
- Neu: `glide_join::a_four_letter_floor_keeps_a_three_letter_tail_from_joining`.
- CI fährt jetzt `cargo test --release --manifest-path native/wm-engine/Cargo.toml`
  vor `./gradlew unitTests`. Voller Lauf: 496 + 3 + 5 + 4 Tests grün. Patch:
  `0004-tests-ci`.

### 4.5 Reranker-Deckel (erledigt; ohne deutsches `.wmlm` inert)
`blendGlideContextModel` sitzt in `finishGlide` vor `rerankGlide`; Deckel 3,0,
Gewicht 0,7. Auf den 2.294 Zügen mit Kontext: 70,84 → **80,82** (+9,98) gegen
die ungedeckelte Obergrenze 82,13 (Pool 4) bzw. 83,13 (Pool 8, Gewicht 1,5).
Der Blend läuft **vor** dem Rang-Rerank, wie im Tipp-Pfad; `GLIDE_RERANK_POOL`
bleibt 8. Patch: `0001-glide-context-blend`. Das Sprachmodell der Messung ist
ein Korpus-Bigramm; auf dem Gerät ist es das `.wmlm`, dessen Nats-Skala
anders ist — beim ersten echten Lauf das Gewicht 0,7/Deckel 3,0 nachmessen,
nicht als Naturkonstante behandeln.

## 5. Reproduktion

```sh
git clone https://github.com/wasi-master/wmkeyboard && cd wmkeyboard
git checkout 22d5020b
# Patches in dieser Reihenfolge; 0000 ist nur der Mess-Harness
for p in 0000-eval-harness 0001-glide-context-blend 0002-compound-join-guard \
         0004-tests-ci; do
  git apply <dieses repo>/wmk-glide/patches/$p.patch
done
# optional, nicht empfohlen: git apply <dieses repo>/wmk-glide/experiments/german-umlaut-keys.patch
cd native/wm-engine
cargo build --release --example glide_beam_eval
cargo test --release --manifest-path Cargo.toml   # 496 + 3 + 5 + 4 grün

# Deutsch, ausgelieferte Gewichte
COLS=11 ALL=1 THREADS=8 ./target/release/examples/glide_beam_eval \
    de_swipes.jsonl german.json de_150k.txt
# Deutsches Profil, dann mit dem Join-Guard
printf 'freq_weight=0.5 gap_weight=2.0\nfreq_weight=0.5 gap_weight=2.0 join_cost=8 join_min_part=4 join_part_penalty=0.1\n' | \
    COLS=11 ALL=1 THREADS=8 ./target/release/examples/glide_beam_eval de_swipes.jsonl german.json de_150k.txt
# Pool für den Blend mit Deckel
ALL=1 DUMP=pool.jsonl RESULTS=8 COLS=11 THREADS=8 \
    ./target/release/examples/glide_beam_eval de_swipes.jsonl german.json de_150k.txt
python3 tools/rerank_eval.py pool.jsonl de_swipes.jsonl
python3 tools/blend_cap_eval.py pool.jsonl de_swipes.jsonl

# Layout synthetisch (braucht die Wortliste und das gebaute Beispiel)
python3 tools/synth_layout_eval.py --words de_150k.txt \
    --engine /pfad/zu/wmkeyboard/native/wm-engine --targets 1324 --noise 0.05
# Komposita-Obergrenze
python3 tools/join_oracle.py de_swipes.jsonl de_150k.txt
```

Daten und Lizenzen: FUTO `swipe.futo.org` (MIT, `swipe-5/swipe5.jsonl`,
`layouts/german.json`, `layouts/qwerty.json`), HeliBoard Gesture Data (CC BY-SA 4.0,
Codeberg `eclexic/heliboard-gesture-data`, `compressed/batch_1/de/*.zst`), FrequencyWords
Deutsch (MIT, `content/2018/de/de_full.txt`). Details und `curl`-Zeilen im Issue-Entwurf,
§12/§13.

## 6. Arbeitshinweise für eine neue Session

- **Zahlen neu ziehen, nicht zitieren.** `main` läuft weiter; jede Zahl hier hat ein
  Kommando. Ein kleiner Unterschied (71,45 vs 71,52) kommt von `RESULTS`/`k`, nicht von
  einem Fehler. Auch die Profil-Basis ist hier 74,15 statt der früheren 74,27 (Engine-
  Revision/`RESULTS`), nicht ein neuer Fehler.
- **Kotlin ist hier nicht baubar** (kein Android-SDK). Rust-Tests gehen:
  `cargo test --release --manifest-path native/wm-engine/Cargo.toml`. Die
  Kotlin-Änderungen (Blend, Tuning-Felder; der optionale Layout-Patch) sind deshalb nur
  per Diff geprüft, nicht kompiliert.
- **Offen nach dem Patch:** (1) `.so` neu bauen (JNI 28 → 30, §4.2); (2) ein deutsches
  `.wmlm` trainieren/veröffentlichen (`issue-german-wmlm.md`) und den Blend damit auf
  einem gehaltenen Split messen (0,7/3,0 ist am Korpus-Bigramm gefittet); (3) HeliBoard
  mit dem Guard erneut ziehen — die 10.908 Züge wurden hier nicht neu geladen;
  (4) Seed-Index-Fallback §4.3.
- Das Issue **#966 ist gepostet**; der Nachtrag-Kommentar
  (`issue-966-followup.md`) und der deutsche `.wmlm`-Feature-Request
  (`issue-german-wmlm.md`) sind **noch nicht gepostet**. Neue Upstream-Issues/-Kommentare
  gehen mit dem vorhandenen Token nicht (nur `pull`); Forgejo-Push ja, Upstream-PR nein.
