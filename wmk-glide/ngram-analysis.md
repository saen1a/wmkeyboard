# N-Gramme: was die Daten tragen und was nicht

Stand: 27.10.2026. Analyse der deutschen n-gram-Packs (`de_bigrams`,
`de_trigrams`) und der naheliegenden Erweiterungen. Die Zahlen sind mit den
Skripten in [`experiments/`](experiments/README.md) erzeugt; die Rohdaten sind
öffentlich (Tatoeba, Leipzig, FrequencyWords). Ziel ist nicht ein neuer
Decoder, sondern der Kontext, den die Engine ohne ein deutsches `.wmlm` hat.

## 0. Kurzfassung

| Hebel | Gemessener Effekt | Aufwand |
|---|---|---|
| **Chat-/Register-Pack** statt web+news | **+2,71** Next-Word-top-1 auf Chat (14,88 vs 12,17) | mittel: neuer Pack + Auswahl |
| **4-Gramm** zusätzlich zu Trigramm | **+2,32** Next-Word-top-1 (17,20 vs 14,88) | hoch: Format, Codec, Engine |
| Trigramm statt Bigramm | +3,96 auf Chat (14,88 vs 10,92) | **schon in der App** |
| **Größerer Deckel** (75k→300k Trigramme) | **+1,23** Next-Word-top-1 | klein: Daten/Download |
| **Normalisierter Pack-Score** (Backoff) | **+0,20** Glide-top-1 auf FUTO | klein: `left`-Zähler |
| Dictionary-gated Pack | nicht gemessen; weniger verschwendete Paare | klein: Build |
| Class-/Skip-Gramme | neutral bis negativ auf FUTO | nicht zuerst |
| Cache/User-N-Gramme | auf FUTO nicht messbar | braucht Chat-Daten |

Der wichtigste Befund: **Domäne schlägt Ordnung.** Die App hat den Trigramm-
Vorteil schon; was fehlt, ist ein Pack aus dem Register, in dem getippt wird
(Chat), nicht aus Web/News. Der größte Einzelhebel ist deshalb ein
**Chat-Pack**, nicht ein 4-Gramm auf dem falschen Korpus.

## 1. Was heute ausgeliefert wird

- `NgramPackCatalog`: Deutsch = `de_bigrams.txt.gz` (150.000) +
  `de_trigrams.txt.gz` (75.000), Quelle `deu-com_web_2021_1M` ×3 +
  `deu_news_2024_1M` ×1 (Daten-Repo-README).
- Die App liest nur den Kopf der Dateien; der Deckel entscheidet, welche Paare
  auf das Gerät kommen. Der Pack ist ~1,3 MB komprimiert.
- `NgramReranker` (Kotlin) → `wm-engine`'s `rerank`: Pack-Trigramm 0.6/Cap 1.5,
  Pack-Bigramm 0.45/Cap 1.2, dazu User-Trigramm/Bigramm/Skip, Seed und Recency;
  `LM_WEIGHT = 0`. Der Score-Blend (`blendContextModel`) nutzt nur das
  neuronale `.wmlm`, nicht den Pack.
- **Kein deutsches `.wmlm`**: `ContextModelCatalog` hat nur `en`/`bn_rom`.
  Auf Deutsch ist der Score-Blend ein No-op; der Pack-Rang-Rerank ist der
  einzige Kontextgewinn.

## 2. FUTO-Glide: der Pack im Decoder

FUTO Deutsch, 2.294 Züge mit Vorgängerwort, Top-32-Pool, deutsches Profil.
Abdeckung des **aktuellen** Packs:

| Größe | Wert |
|---|---|
| Ziel in der Pack-Vokabel (de_full-Unigramm) | 96,1 % |
| Kontext (Vorgängerwort) im Pack | 79,0 % |
| (Vorgänger, Ziel)-Bigramm im Pack | **41,3 %** |
| (Vorgänger2, Vorgänger, Ziel)-Trigramm im Pack | **7,8 %** |

Der Pack deckt also nur 41 % der Ziel-Bigramme und 8 % der Trigramme ab; die
restlichen Paare können nur über Unigramm/Backoff oder gar nicht wirken.

Rang-Rerank (Rank-Step + Evidenz, wie `NgramReranker`):

| Variante | top-1 |
|---|---|
| Decoder | 70,84 |
| roher Pack (`ln(1+c)`, wie heute) | 71,32 (+0,48) |
| **normalisiert + Unigramm-Backoff** | **71,53 (+0,69)** |
| Backoff allein | 71,49 (+0,65) |
| Wikipedia-Pack (gleicher Deckel) | 71,71 (+0,87) |
| web+wiki, Deckel 300k | 71,67 (+0,83) |
| Class-Backoff / Skip-Gramme | 71,4–71,5 (kein Gewinn) |

FUTO sind Wikipedia-Sätze; der aktuelle Pack ist Web/News. Ein Wikipedia-Pack
ist dort **+0,18** besser als der normalisierte web/news-Pack (71,71 vs 71,53),
aber die App tippt Chat, nicht Enzyklopädie. Der Glide-Gewinn bleibt klein, weil der Pack nur den Pool von 8
umsortieren darf; die Kandidatengenerierung ist der größere Hebel.

## 3. Chat: der Pack als Next-Word-Modell

Tatoeba Deutsch, 783.774 Sätze, 80/20-Split, 1.057.081 Test-Paare. Next-Word-
Top-1/Top-3 aus dem Pack (Bigramm/Trigramm, Backoff zum Unigramm):

| Pack | top-1 | top-3 |
|---|---|---|
| web/news, Bigramm | 9,14 | 17,15 |
| web/news, Trigramm | 12,17 | 20,70 |
| Tatoeba, Bigramm | 10,92 | 20,22 |
| **Tatoeba, Trigramm** | **14,88** | **24,62** |

Damit lassen sich die Effekte trennen:

- **Ordnung** (Bigramm → Trigramm) auf Tatoeba: **+3,96**.
- **Domäne** (web/news → Tatoeba) bei Trigramm: **+2,71**.
- Die App hat Trigramme, aber den web/news-Pack. Für Chat fehlen ihr die
  **+2,71** der Domäne.

### Deckel

Tatoeba-Trigramme, gleicher Test:

| Trigramme im Pack | top-1 | top-3 |
|---|---|---|
| 50k | 14,52 | 24,14 |
| 75k (heute) | 14,88 | 24,62 |
| 150k | 15,46 | 25,46 |
| 300k | 16,11 | 26,37 |
| 600k | 16,57 | 27,00 |
| 1M | 16,82 | 27,35 |

75k → 300k sind **+1,23**; danach flacht es ab. Bigramme 150k → 300k sind nur
+0,26. Der Trigramm-Deckel ist der lohnendere, weil Trigramme den Kontext
tragen; der Pack wächst dabei auf wenige MB.

### 4-Gramme

Tatoeba-4-Gramme, Backoff 4→3→2→1:

| 4-Gramme | top-1 | top-3 |
|---|---|---|
| 50k | 15,79 | 25,13 |
| 150k | 16,52 | 25,87 |
| 300k | **17,20** | **26,63** |

Gegen Trigramm 14,88 sind das **+2,32** bei 300k. Das ist der größte
Ordnungsgewinn, aber er braucht:

- ein neues Feld im Pack-Format (`wmng`/`NgramPackCodec`),
- einen 4-Gramm-Zähler im Build (`import_leipzig_ngrams.py`),
- `RerankContext.prev3` und einen neuen Term im `rerank` (die Kotlin-Seite
  hat `prev3` schon; ein 4-Gramm braucht drei Kontextwörter, kein `prev4`),
- mehr Download/Latenz.

Ohne Chat-Pack ist der 4-Gramm-Gewinn auf dem web/news-Pack deutlich kleiner;
erst die Domäne, dann die Ordnung.

## 4. Was das für die App heißt

### 4.1 Register-/Chat-Pack (größter Hebel)

Deutsch hat heute **einen** Pack für alle Register. Die App kennt `Register`
(neutral/casual/formal) und `ContextField` (chat/email/search). Ein
**`de_chat`-Pack** aus Tatoeba + OpenSubtitles, ein **`de_formal`-Pack** aus
News/Wikipedia, und die Auswahl im `SuggestionEngine`:

- `casual`/`chat` → Chat-Pack,
- `formal`/`email`/`search` → Formal-Pack,
- neutral → der allgemeine web/news-Pack (heute).

Gemessener Hebel auf Chat: **+2,71** Next-Word-top-1 gegenüber web/news bei
gleicher Ordnung. Das ist mehr als jede Deckel- oder Glättungsänderung.

### 4.2 Normalisieren und backoffen

Der Rang-Rerank nutzt heute `weight * ln(1 + count)`; die Wahrscheinlichkeit
`count / left(context)` mit Unigramm-Interpolation ist auf FUTO **+0,20**.
Dafür braucht der Pack einen **`left`-Zähler** pro Kontext (Summe der
Bigramm-/Trigramm-Zähler) oder die Engine summiert ihn beim Laden. Der
Rank-Step/cap bleibt; nur der Term wird ersetzt. Kein neues Format, wenn der
`left`-Zähler aus den vorhandenen Zeilen berechnet wird.

### 4.3 Größere Deckel

Trigramm 75k → 300k: **+1,23** auf Chat; 4-Gramm 300k: +2,32 gegen Trigramm.
Der Pack wächst von ~1,3 MB auf wenige MB. Erst nach 4.1 messen: ein größerer
Deckel auf dem falschen Register bringt weniger.

### 4.4 Dictionary-gated Pack

Der Pack wird auf `de_full` (1,16 Mio.) gebaut; die App bietet aber nur ihre
eigene Liste (`de_aosp`, 205.888) plus die echte Komposita-Liste (§2.6.4).
Paare, die ein Wort außerhalb dieser Liste nennen, können nie feuern. Ein Pack,
der auf **der App-Liste + 441k Komposita** gated, hat bei gleichem Deckel mehr
nutzbare Paare. Das ist der Weg, den der Bengali-Build schon geht; für Deutsch
noch nicht gemessen, aber billig zu bauen.

### 4.5 Was nicht zuerst kommt

- **Class-/Skip-Gramme**: auf FUTO neutral bis negativ (71,4–71,5). Erst mit
  Chat-Daten und einem größeren Pack neu messen.
- **Voll-Unigramm als Score-Blend**: bricht den Blend auf 62–65 % ein
  (Skalen-Mismatch; siehe `experiments-followup.md`).
- **4-Gramm vor der Domäne**: der web/news-Pack hat auf FUTO nur 7,8 %
  Trigramm-Abdeckung; ein 4-Gramm darauf ist noch dünner.
- **Cache/User-N-Gramme**: auf FUTO nicht messbar (Sätze zu kurz); braucht
  echte Chat-Verläufe und eine Decay-Gewichtung. Der User-Lexikon-Pfad hat
  Bigramme/Trigramme/Skip schon; ein Cache-LM wäre die nächste Stufe.

## 5. Implementierungsorte

| Änderung | Datei |
|---|---|
| Pack-Auswahl nach Register/Field | `SuggestionEngine.ngramPack` (heute ein `var`), `NgramPackCatalog` (Varianten), `NgramPackDownloadManager` |
| Chat-Pack bauen | `scripts/import_leipzig_ngrams.py` um eine Tatoeba-/OpenSubtitles-Quelle erweitern (der `.wmlm`-`corpus.py` liest Tatoeba schon) |
| Normalisierter Term | `wm-engine/src/rerank.rs` (`term`, `left`-Zähler), `Pack`/`wmng` (`bigram_total`) |
| 4-Gramm | `wmng.rs`/`NgramPackCodec`, `rerank.rs` (`quadgram`-Term), `RerankContext`/`prev3`/`prev4`, `import_leipzig_ngrams.py` |
| Dictionary-gated Build | `scripts/import_leipzig_ngrams.py --vocab` auf `de_aosp` + Komposita |
| Deckel | `NgramPackCatalog`/Download-Caps; Daten-Repo-Build |

## 6. Reproduktion

```sh
# Daten
curl -L -o data/deu_sentences.tsv.bz2 \
  https://downloads.tatoeba.org/exports/per_language/deu/deu_sentences.tsv.bz2
curl -L -o data/deu_wikipedia_2021_1M.tar.gz \
  https://downloads.wortschatz-leipzig.de/corpora/deu_wikipedia_2021_1M.tar.gz
# de_bigrams/de_trigrams aus wasi-master/wmkeyboard-data/data/de/
# de_full.txt aus FrequencyWords

# FUTO-Glide-Pack
python3 experiments/pack_quality.py      # Abdeckung + roh/normalisiert
python3 experiments/build_wiki_pack.py   # Wikipedia-Pack
python3 experiments/compare_packs.py     # web vs wiki vs kombiniert

# Chat-Next-Word
python3 experiments/chat_pack.py         # web vs Tatoeba, Bigramm
python3 experiments/chat_pack_tri.py     # Trigramm
python3 experiments/chat_pack_tri_caps.py
python3 experiments/chat_pack_4.py       # 4-Gramm
python3 experiments/chat_web_tri.py      # web-Trigramm auf Chat
```

Die Skripte sind Forschungscode; die großen Korpora (Tatoeba 12 MB,
Wikipedia 207 MB) sind nicht im Repo. Der FUTO-Vergleich ist ein
Wikipedia-Domänen-Proxy; die Chat-Zahlen sind Tatoeba (casual/chat), nicht
die App-Daten. Vor dem Shipping auf einem gehaltenen Chat-Korpus
(`typing_eval`) und auf dem Gerät messen.

## 7. Fazit

1. **Chat-/Register-Pack** bauen und auswählen: +2,71 Next-Word-top-1 auf Chat,
   der größte n-gram-Hebel ohne neues Modell.
2. **Trigramm-Deckel 75k → 300k**: +1,23, billig; danach 4-Gramme (+2,32) mit
   Format-/Engine-Änderung.
3. **Pack-Score normalisieren/backoffen**: +0,20 im Glide-Rerank, kleine
   Engine-Änderung.
4. **Dictionary-gated Pack** (App-Liste + Komposita): weniger tote Paare.
5. **4-Gramm, Cache und Personalisierung** erst danach; Class/Skip und
   Voll-Unigramm sind auf den vorhandenen Daten keine Gewinner.

Der Pack ist ein **+0,5-bis-+0,9**-Hebel im Glide-Pfad und ein
**+2,7-bis-+4**-Hebel im Next-Word-Pfad, je nach Domäne. Der größte deutsche
Einzelhebel bleibt die echte Komposita-Liste (+1,55); das deutsche `.wmlm`
ist der nächste Kontextschritt und nach dem englischen Proxy **+4,9 top-1**
im Glide wert ([`wmlm-gain.md`](wmlm-gain.md)).
