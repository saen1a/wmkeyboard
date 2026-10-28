# WMK Glide: die nächste Stufe – was gemessen wurde und was nicht trägt

Stand: 26.10.2026. Nachtrag zu [`state.md`](state.md) §2.6 und zum
Issue-Kommentar [`issue-966-followup.md`](issue-966-followup.md). Getestet wurde
alles, was dort noch nicht steht: gehaltener Test, breiterer Pool, Trigramm,
Cache, gelernter Reranker, Komposita-Prior, Kontextquelle, Frequenz-Exponent,
Diakritika. Alle Zahlen auf FUTO Deutsch (`de_swipes.jsonl`, 2.588 Züge,
`german.json`, `de_150k.txt`), Decoder ohne Handmodell.

## 0. Die wichtigste Korrektur: 80,82 ist in-sample

Der Blend in §2.6.1 baut das Bigramm aus **denselben** Sätzen, auf denen er
gemessen wird. Das ist eine Obergrenze, keine Erwartung. Mit einem echten
Halte-Test (20 % der Sätze per SHA-256, LM nur auf den anderen 80 %):

| Fairer Test (506 Züge mit Vorgängerwort) | top-1 |
|---|---|
| Decoder | **68,97** |
| Blend (Bigramm, 0,7/3,0) | **69,17** (+0,20) |
| Blend (Trigramm) | 69,17 |
| Blend (Bigramm + Trigramm) | 69,17 |

Das Train-LM hat nur 1.293 Wörter Vokabular (die FUTO-Sätze sind ein kleiner
Korpus); das Ziel steht bei nur **34,9 %** in den Top-50 des LM. Ein echtes
`.wmlm` ist auf einem großen Korpus trainiert und dürfte dazwischen liegen —
aber die **80,82 aus §2.6.1 sind kein Beleg für den Gerätegewinn**. Auf dem
Gerät mit dem echten `.wmlm` und einem gehaltenen Satz-Split nachmessen, bevor
die Zahl irgendwo als Versprechen steht.

## 0b. Es gibt kein deutsches `.wmlm`

Der `ContextModelCatalog` veröffentlicht nur `en` und `bn_rom`; für Deutsch
gibt es **kein neuronales Kontextmodell**, nur den **n-gram-Pack**
(`data/de/de_bigrams.txt.gz`, `de_trigrams.txt.gz`, zusammen ~1,3 MB). Auf
einem deutschen Gerät ist `contextModel` also `null`, und
`blendGlideContextModel` ist ein **No-op**. Der Blend-Patch wirkt erst, wenn
ein deutsches `.wmlm` trainiert und veröffentlicht ist.

Was der echte deutsche Pack kann (FUTO, 2.294 Züge mit Vorgängerwort):

| Nutzung des Packs | top-1 |
|---|---|
| Decoder | 70,84 |
| **Score-Blend** (wie `blendGlideContextModel`) | **69,83** (negativ) |
| **Rang-Rerank** (der Weg des `NgramReranker`, Pack-Bigramm/Trigramm) | **71,3** (+0,45) |
| Pack-Top-50 als Kontextquelle: Ziel außerhalb des Pools | **0,4–1,2 %** |

Der Pack-Rang-Rerank ist der einzige **heute verfügbare** deutsche
Kontextgewinn: +0,45, nicht +10. Der Score-Blend mit dem Pack verliert, weil
die Pack-Frequenzskala nicht zu den Decoder-Nats passt. Eine Pack-Kontextquelle
hilft kaum: wenn der Decoder das Ziel verfehlt, steht es fast nie in den
Pack-Top-N (nur 2–6 von 506 Zügen). Der in-sample hohe Recall (14–15 %) war
Leakage des Korpus-Bigramms, nicht der Pack.

**Konsequenz:** Für Deutsch ist der erste Hebel nicht ein Tuning-Feld, sondern
ein **deutsches `.wmlm`** (`tools/wmlm`) oder ein besserer Pack-Reranker. Der
Blend-Patch ist für Sprachen mit Modell richtig, für Deutsch derzeit wirkungslos.

## 1. Breiterer Pool: der Deckel bindet, nicht der Pool

Gleicher Dump (Top 32), Blend 0,7/3,0 gegen den Führer:

| Pool | Deckel 3,0 | ohne Deckel (w = 1,0) |
|---|---|---|
| 4 | 80,65 | 82,08 |
| 8 | **81,04** | 83,22 |
| 12 | 81,04 | 83,52 |
| 16 | 81,04 | 83,65 |
| 24 | 81,04 | 83,70 |
| 32 | 81,04 | 83,70 |

Mit dem 3-Nat-Deckel bringt der breitere Pool **nichts**: die zusätzlichen
Kandidaten liegen mehr als 3 Nats zurück und dürfen nicht aufsteigen. Ohne
Deckel sind es +0,48 von 8 auf 32. (P8 = 81,04 statt 80,82 aus §2.6.1: der Dump
ist mit `RESULTS=32` erzeugt; der Unterschied ist `RESULTS`/Pool, kein Fehler.) Ein zweiter Durchgang mit 16/32 ist also nur
sinnvoll, wenn der Deckel mitwächst oder das LM besser wird.

## 2. Trigramm, Cache, Voll-Liste

- **Trigramm** statt Bigramm: in-sample mit Deckel 3 **81,47 statt 81,04**
  (+0,43), im fairen Test **69,17 statt 69,17** (kein Unterschied). Das echte
  `.wmlm` sieht den ganzen Satz; ein zusätzliches Trigramm im Blend ist nur
  dann sinnvoll, wenn kein neuronales Modell installiert ist. Dann ist der
  Korpus-Pack die Quelle, nicht ein neues Feld.
- **Cache** (Wort kam früher im selben Satz vor): 81,04 → 81,12 bei Gewicht 1;
  nur **91/2.294** Züge haben überhaupt einen Pool-Kandidaten, der früher im
  Satz stand. Auf diesem Korpus nicht messbar; in einem echten Gespräch kann
  `recentWords` mehr bringen, aber das braucht Conversational-Daten.
- **Voll-Liste als Unigramm** (1,16 Mio Wörter statt Korpus-Unigramm): bricht
  den Blend auf 62–65 % ein. Die Frequenzskala der Voll-Liste passt nicht zur
  Korpus-Bigramm-Wahrscheinlichkeit; ohne Neukalibrierung unbrauchbar.

## 3. Gelernter Reranker (conditional logit)

Features: Decoder-Score, Unigramm/Bigramm/Trigramm-Logp, Cache, Länge,
Komposita-Flag, Voll-Listen-Frequenz, Umlaut. Trainiert auf 1.788 Zügen,
getestet auf 506 (Satz-Split), Softmax über den Pool, L2:

| | top-1 |
|---|---|
| Decoder (Führer) | 68,97 |
| Deckel-Blend (Bigramm) | **69,17** |
| Logit (9 Features) | 67,92 |

Der Logit overfittet die Trainingssätze (Loss nahe 0): das Trigramm-Feature
sieht dort den Ziel-Satz selbst. Auf dem gehaltenen Split verliert er gegen den
einfachen Deckel-Blend. **Nicht ausliefern.** Ein Reranker-V2 lohnt erst mit
einem externen LM und viel mehr Trainingssätzen, nicht mit diesen neun Features
auf 1.788 Zügen.

## 3b. Deckel mit Streuung: neutral

Die Streuung der echten Züge (mittlerer Abstand zur nächsten Key-Mitte) ist
Median **0,572** Keybreiten, p10 0,424, p90 0,706. Ein Deckel
`3 · (1 + s·(spread − 0,572))`, geklemmt auf 1,5–5:

| s | fairer Test |
|---|---|
| −1 | 68,77 |
| 0 | 68,97 |
| +0,5 / +1 / +2 | 69,17 |

Der feste Deckel 3,0 mit dem besten Gewicht ist genauso gut (69,17); der
streuungsabhängige Deckel gewinnt nichts, und negativ (unsauberen Zügen weniger
vertrauen) verliert. Kein Shipping-Kandidat auf diesem Korpus.

## 4. Komposita: der Prior hilft nicht, die Kandidaten fehlen

Auf dem Guard-Pool (Top 32, deutsches Profil, `8/4/0,1`):

| | top-1 (nicht-leere Pools) |
|---|---|
| Guard | 74,99 |
| + Voll-Listen-Bonus (`ln(1+f)`, α = 1) | 75,11 (+0,12) |
| + Teil-Paar-Tabelle (471.851 Paare aus der Voll-Liste) | 75,11 (+0,12) |

Von den **118** joini-baren Zielen (Ziel fehlt in 150k, zerfällt in zwei
Listenwörter) sind **67** in der Voll-Liste, aber nur **25** im Top-32-Pool und
**16** top-1. Der Engpass ist die **Kandidatengenerierung**, nicht die
Bewertung: ein Bonus kann nur die 25 umsortieren, die der Join-Walk schon
gefunden hat. Nächster Schritt wäre eine **Komposita-Quelle** (Voll-Liste oder
Teil-Paar-Expansion) oder ein Join, der mit einem Teil-Paar-Prior früher im
Walk überlebt — nicht noch ein Score-Bonus.

Die 1,16-Mio-Liste als **Decoder-Liste** war in §2.3 schon **72,41 %** (gegen
71,45, ausgelieferte Gewichte); mit deutschem Profil sind es **75,46** (§7b). Das ist
der ehrlichere Vergleich für eine Komposita-Quelle.

## 5. Kontextquelle: mechanisch gut, aber das LM ist zu schwach

Per-Stroke-Top-50 des fairen LM als zusätzliche `Source` (eigener Trie,
`Tier::User`), Ziel:

| | Wert |
|---|---|
| Ziel in den LM-Top-50 | 34,9 % |
| Ziel in den Top-50 und vom Decoder gelesen (extra-only top-1) | 33,3 % (≈ 95 % der Fälle) |
| Decoder + Quelle, bester Gewichtspunkt | **69,43** (Basis 68,84, +0,59) |

Die **Lesbarkeit** ist nicht das Problem: wenn das Ziel in der 50-Wort-Liste
steht, liest der Decoder es fast immer. Das Problem ist die **Trefferquote des
LM**: 34,9 % auf dem kleinen Korpus. Mit einem echten `.wmlm` (großes
Vokabular, bessere nächste-Wort-Verteilung) ist das die eine Erweiterung, die
über die Pool-Coverage hinausführen kann. Sie braucht aber **pro Wort ein
Logp**, keine flache Trie-Frequenz: die flache Variante brachte +0,59, die
logp-kodierte +0,59 — der Unterschied verschwindet, weil das Korpus-LM zu
schwach ist.

## 6. Frequenz-Exponent: kein Top-1-Gewinn

`freq_weight * ln(1+f)^α` im Decoder (deutsches Profil), α:

| α | top-1 | top-4 |
|---|---|---|
| 0,7 | 69,94 | 80,53 |
| 0,8 | 71,37 | 81,45 |
| 0,9 | 73,18 | 82,19 |
| **1,0** | **74,15** | 82,81 |
| 1,1 | 74,00 | 83,08 |
| 1,2 | 73,49 | 83,31 |
| 1,3 | 71,64 | 82,88 |

Top-4 gewinnt bei 1,2 (+0,50), top-1 verliert (−0,66). Kein Shipping-Kandidat;
die vorhandene lineare Gewichtung ist für Top-1 besser.

## 7. Diakritika: auf a–z stark, in der App redundant

Synthetisch (1.324 Wörter, deutsches Profil), a–z-Keymap ohne Umlaute, dann
eine **Wortlisten-Restaurierung** (für jeden Top-Kandidaten die frequenteste
`ä/ö/ü/ß`-Variante aus der 150k-Liste):

| Gitter | top-1 |
|---|---|
| a–z, keine Umlaute | 85,57 |
| a–z + Wortlisten-Restaurierung | **92,75** (+7,18) |
| Long-Press (App heute) | 96,37 |
| `ü ö ä ß` als Tasten | 97,73 |

Die Restaurierung holt 7,18 der 12,16 Punkte, die a–z zu den echten Tasten
fehlen. Aber die App hat den Long-Press: dort sind beide Schreibweisen schon im
Key-Map, und die Frequenz entscheidet bereits. Die Restaurierung ist also eine
Option für ein **Layout ohne Umlaute**, kein Ersatz für den Long-Press und
kein Grund, die Tasten wieder einzuführen.

## 7b. Der beste deutsche Hebel: echte Komposita in die Wortliste

Die 150k-Liste verliert die Komposita, die Leute wischen. **Generierte**
Komposita waren ein Nettoverlust (unter 2 % echte Wörter); **echte** Komposita
aus der FrequencyWords-Voll-Liste sind etwas anderes. Konstruktion: jedes
`de_full`-Wort, das nicht in `de_150k` steht und in zwei `de_150k`-Wörter
zerfällt (Teile ≥ 3), mit seiner echten Frequenz anhängen. Das sind **441.470
beobachtete Wörter**, keine Erfindungen. Deutsches Profil, `RESULTS=4 COLS=11`:

| Wortliste | top-1 | top-4 |
|---|---|---|
| 150k | 74,15 | 82,81 |
| **150k + 441k echte Komposita** | **75,70** | **84,23** |
| 150k + 346k (Teile ≥ 4) | 75,58 | 84,20 |
| volle 1,16-Mio-Liste | 75,46 | 84,39 |
| **150k + 441k + Join-Guard** | **75,77** | **84,47** |

Das ist **+1,55 top-1 / +1,42 top-4** aus einer reinen Datenänderung, mehr als
der Guard (+0,46) und mehr als der deutsche Pack-Rerank (+0,45). Die kuratierte
591k-Liste ist top-1 sogar besser als die volle 1,16-Mio-Liste, weil sie die
seltenen Nicht-Komposita nicht mitbringt. Der Join-Guard bleibt sinnvoll
(+0,07/+0,24 obendrauf), aber die Liste ist der größere Hebel.

Werkzeug: [`tools/build_compound_list.py`](tools/build_compound_list.py)
(`de_150k.txt` + `de_full.txt` -> `de_150k_comp3.txt`). Die Liste ist eine
**Daten-/Wörterbuch-Erweiterung**, kein Engine-Patch; sie kann wie die
bestehenden Wortlisten kompiliert/ausgeliefert werden.

## 8. Was daraus folgt

1. **Echte Komposita in die Wortliste** (+441k beobachtete Wörter):
   **75,70/84,23**, mit Guard **75,77/84,47**. Das ist der größte gemessene
   deutsche Gewinn und braucht keine Engine-Änderung.
2. **Ein deutsches `.wmlm` trainieren/veröffentlichen** (der Katalog hat nur
   `en`/`bn_rom`). Erst dann kann der Blend auf Deutsch wirken. Bis dahin ist
   der Pack-Rang-Rerank der einzige gemessene Kontextgewinn (+0,45); die 80,82
   aus §2.6.1 sind in-sample und ohne deutsches Modell nicht erreichbar.
3. **Kontextquelle** (Top-N des `.wmlm` mit Logp) ist die einzige Erweiterung
   mit einem klaren Mechanismus über die Pool-Coverage hinaus; mit einem
   echten deutschen Modell offen. Mit dem vorhandenen Pack hat sie nur
   0,4–1,2 % Headroom, weil das Ziel bei einem Decoder-Fehler fast nie in den
   Pack-Top-N steht.
4. **Nicht ausliefern:** Frequenz-Exponent, Voll-Liste als Unigramm,
   9-Feature-Logit, Cache auf diesem Korpus, breiterer Pool mit 3-Nat-Deckel.
5. **Diakritika** nur für ein Layout ohne Umlaute; in der App redundant.

## 8b. Nicht getestet (und warum)

- **Kontextgewicht im Beam / Prefix-LM**: braucht eine Prefix-Wahrscheinlichkeit
  (Zeichen-LM) oder eine per-Wort-Logp-Map, die der Walk vor dem Wortende
  lesen kann. Der `.wmlm` liefert Wort-Logp, keinen Prefix; das ist ein eigener
  Decoder-Eingriff, kein Tuning-Feld.
- **Shape/Touch** (`sigma_x/y`, Kovarianz, Timing, Velocity, mehrere
  Shape-Templates): braucht Engine- und Shape-Store-Änderungen; ohne echte
  Nutzerzüge mit Handmodell nicht sinnvoll messbar.
- **Kneser-Ney/Class/Topic**: der faire Train-Korpus hat 1.293 Wörter; jede
  Glättung ist auf dieser Datenmenge nicht aussagekräftig. Mit einem großen
  Korpus neu ziehen.
- **Satz-Viterbi**: die App decodiert einen Wisch nach dem anderen; ein
  Viterbi über die letzten Wörter braucht den nächsten Wisch oder eine
  Phrase. Auf dem FUTO-Set nicht streaming-fähig.
- **User-Adaption**: keine Korrekturpaare (akzeptiert/verworfen) im Datensatz.
- **Seed-Fallback** (§4.3): eigener Bug, nicht Teil dieser Messreihe; im
  früheren Kommentar beschrieben.

## 9. Reproduktion

```sh
# In-sample (state.md §2.6.1)
python3 tools/blend_cap_eval.py pool.jsonl de_swipes.jsonl

# Die Experimente dieser Runde
# aus wmk-glide/ (data/ und die Dumps dort)
python3 experiments/pool_blend.py pool32.tsv data/de_swipes.jsonl
python3 experiments/fair_ngram.py          # 20-%-Satz-Split, Bigramm vs Trigramm
python3 experiments/logit.py               # 9-Feature-Logit
python3 experiments/compound_guard.py      # Komposita-Prior
python3 experiments/lm_recall.py           # LM-Top-N-Recall
```

Die Skripte und der Rust-Prototyp der Kontextquelle liegen in
[`experiments/`](experiments/README.md); sie erwarten die entpackten Daten und
die Dumps dort. Die Zahlen oben sind mit genau diesen Läufen erzeugt. Vor einer
Veröffentlichung die Pfade parametrisieren und den Fair-Split als eigenen
Harness-Lauf festnageln.
