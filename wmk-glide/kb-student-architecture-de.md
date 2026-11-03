# KB: Deutscher Schüler — Architektur, KD-Daten und Rebuild

Stand: 2026-11-02. Scope: **Schüler-only**, kein neuer Lehrer-Pass, keine Änderung am laufenden 90k-Training. Dieses Dokument ersetzt die veralteten OOV-Zahlen in `kb-context-blend-optimizations.md` §2.4 und sammelt die geprüften Messungen, Mathematik und Research-Evidenz.

## 0. Executive Summary

1. **Die 20,5 % / 19,6 % „unspellbar“-Zahl ist veraltet.** Der aktuelle Engine-/Vokabularstand seedet einzelne Buchstaben als Start-Pieces; `gib` ist spellbar (`▁g` + `##ib`), `lm_probe` liefert einen finiten Score. Die 20,5 % sind die Menge, die **ohne** Single-Letter-Start-Pieces unspellbar wäre. Aktuell sind nur **3 Wörter** (griechische Lookalikes) wirklich `None`; das reale Residual sind Wörter mit **>6 Pieces**: 2,45 % der 150k-Typen (0,084 % der Tokenmasse) und 10,2 % der 591k-Typen (0,145 % der Tokenmasse). Entfernen ist **neutral bis −0,04 pp**; nicht empfohlen.
2. **Die 15,3 % Piece-KD-Rows sind real, aber kein Grund, Zeilen zu löschen.** Maskiere KD (CE bleibt) oder gewichte KD auf diesen Rows weich (λ≈0,1–0,3). Die aktuelle Implementierung enthält `logsumexp` über das **volle** Vokabular; ein Piece-Ziel mit Lehrermasse 0 bekommt einen **positiven** KD-Gradienten und wird unterdrückt. Bei `L=(1−α)CE+αKD` ist der stationäre Punkt `p_b=1−α` (α=0,3 → 0,7). Das ist **kein No-op**. Zeilen ganz zu löschen ist nur konsistent, wenn die Inferenz ausschließlich ganze Wörter zulässt — das ist hier nicht der Fall.
3. **Größte Schüler-only-Hebel:** KD-Maske/Soft-Weight, **`MAX_WORD_PIECES` 6→8**, **Rebuild der 2.048 Pieces bei stabilen Wort-IDs**, K/α-Sweep (nicht blind K=10), Daten-Reweighting, Depth/Width-Rebalance und ein kandidatenkonditionierter Reranker. Mehr Breite (d288) war negativ. Die **Wortliste** (22.512 Wörter) ist mit 61 % der Parameter der größte Hebel, aber ohne Lehrer/Remap fixiert; die **Piece-Inventur** ist dagegen ohne Teacher änderbar, weil Pieces nie KD-Targets sind und hinter den Wörtern liegen.
4. **Messung:** 2.588 Glide-Züge haben bei 10 % Discordance eine MDE von **1,74 pp**; 0,5-pp-Claims sind Rauschen. ppl ist Diagnose, nicht Ship-Metrik.

## 1. Audit der alten Behauptungen

### 1.1 20,5 % / 19,6 % unspellbar

Alte Tabelle (`kb-context-blend-optimizations.md:98-113`) vs. aktueller Stand (`artifacts/data/vocab.txt`, `Pieces.build` in `tools/wmlm/common.py:74-87`):

| Liste | gültige Typen | im Vokabular | aktuelle `pieces_of`-None | >6 Pieces | aktuell unspielbar (Typen) | Tokenmasse unspielbar | Glide-Ziele betroffen |
|---|---:|---:|---:|---:|---:|---:|---:|
| `de_150k` | 145.395 | 20.045 | **3** | 3.565 | **3.568 (2,45 %)** | **0,084 %** | **0 / 2.594** |
| `de_150k_comp3` | 583.154 | 21.182 | **3** | 59.398 | **59.401 (10,19 %)** | **0,145 %** | **4 / 2.594** |

Reconciliation: Die alte Tabelle nennt 95.577 (150k) bzw. 447.784 (591k) „per Pieces spellbar“. Aktuell sind es 125.347 bzw. 561.969. Differenz: **29.770** bzw. **114.185** — genau die Wörter, die ein **Single-Letter-Start-Piece** brauchen. Die alte „nicht spellbar“-Zahl 29.773/114.188 = diese Menge + die 3 echten `None`-Wörter. Die alte Analyse hat Single-Letter-Starts also ausgeschlossen; `Pieces.build` seedet sie aber (`chosen_s = set(letters)`, `common.py:80`).

Beleg: `lm_probe de_context.wmlm "ich will nach" gib zugleich straßenbahn` liefert finite Scores (`gib` = `▁g`+`##ib`). Die 3 echten `None`-Wörter sind `comρuter`, `κind`, `κreatur` (griechische Lookalikes).

**Entfernen-Ablation (read-only, gleicher Harness, `de_context_2m.wmlm`, `COLS=11 FREQ=0.5 GAP=2.0 WEIGHT=0.5 CAP=5 RESULTS=8`):**

| Liste | Blend top-1/top-4 | nach Entfernen der >6-Piece-Wörter | Δ |
|---|---:|---:|---:|
| `de_150k` | 77,28 / 83,46 | 77,28 / 83,46 | **0,00 pp** |
| `de_150k_comp3` | 78,48 / 84,85 | 78,44 / 84,81 | **−0,04 pp** |

Die 4 verlorenen Comp3-Ziele: `universitätsklinikum`, `originalschauplätzen`, `beamtenlaufbahn`, `befehlsgemäß`. Im Typing-Heldout sind 318/238.033 (150k) bzw. 619/238.033 (591k) Token betroffen (0,13 %/0,26 %). **Typing-Gegenprobe** (500 Fälle, `SCATTER=fast`, base): top-1/top-3 bleiben 58,40/77,80, aber „new words rewritten“ steigt **0,2400 → 0,2900 (100)** — entfernte Wörter werden OOV und damit eher autokorrigiert. **Fazit: nicht entfernen.** Pfadnuance: Der Typing-Strip (`logprob_listed`) scored nur gelistete Wörter; dort ist Entfernen kein LM-Ranking-Hebel. Glide nutzt `scoresSpelled` und kann OOV spellen; die Glide-Ablation ist die Produktmetrik. Der erste sinnvolle Fix ist die Engine-Grenze `MAX_WORD_PIECES=6` (`lm.rs:60`); danach der Piece-Rebuild (§3.5). Das ist ein kleiner Produkt-Hebel (max. +0,15 pp aus 4 Glide-Zielen), kein Daten-Pruning.

Support-Pruning-Mathematik: Für Kandidatenmenge `C`, entfernte Menge `R`, Ziel `y` gilt
`A(C\R) ≥ (1−π_R)·A(C)` mit `π_R = P(y∈R)`; nach oben begrenzt durch `1−π_R`. Renormierung über `C` ist für den Argmax strikt monoton und ändert Top-1 nicht. Typgewichtete und tokengewichtete Entfernung können um Größenordnungen auseinanderliegen (Zipf): hier 2,45 %/10,2 % Typen vs. 0,084 %/0,145 % Token. Deshalb immer beide berichten.

### 1.2 15,3 % Piece-KD-Rows

`de_soft_2m.masks.masks.json`: `piece=3.242.201`, `rows=21.378.590` → **15,1656 %**. Betroffene Sätze: **1.498.574 / 1.979.982 = 75,69 %** haben mindestens eine Piece-Row (mean 1,64; p90 4; max 25).

Der Lehrer hat auf diesen Rows Masse 0, weil er nur ganze Wörter mapped (`audit_signal.json`: `actual_is_piece=0,153`, `piece_top24=0,0`). Die aktuelle KD-Loss ist aber **nicht** auf die Top-k-IDs beschränkt: `distill_loss` bildet `lse = logsumexp(logits)` über das volle Vokabular (`tools/wmlm/train.py:199-201`). Für ein Piece-Ziel `b` außerhalb der Lehrer-Top-k gilt:
`∂KD/∂z_b = p_b > 0`, also **Unterdrückung**. Mit CE:
`∂L/∂z_b = (1−α)(p_b−1) + α·p_b = p_b − (1−α)`, stationär **`p_b* = 1−α`**.
Bei α=0,3 wird das korrekte Piece auf Lehrer-Batches also auf **0,7** gedeckelt; bei α=0,5 auf 0,5. Das ist der Grund, KD auf diesen Rows zu maskieren oder weich zu gewichten — nicht, weil die Row „uninformativ“ wäre.

**Widerspruch aufgelöst:** Eine Research-Notiz behauptete, Maskieren sei ein No-op, weil „zero-mass pieces never enter KD“. Das ist **falsch** für diese Implementierung; der `logsumexp`-Term erzeugt den positiven Gradienten. Numerischer Check: bei `ids=[0,1]`, `p=[0.6,0.4]`, Ziel `b=2` ist `∂KD/∂z_2 = 1/3 > 0`. Die erste Research-Notiz und der Code gewinnen.

**Gemessene Screen-Evidenz:** G3 V2 (KD-Maske, CE bleibt, α=0,5) = **5,0402** vs. G1 V9 **5,0304** (+0,0098 Nats); V3 = **5,0283** (−0,0021); 3k-SE ≈ 0,014; keine Promotion (`gate-log.md:24`). Das ist **kein Beweis für No-op**, sondern ein unterpowerter 3k-Screen. Ein 30k-Lauf mit Maske/Soft-Weight und **OOV-/Glide-Eval** fehlt. Wichtig: Die aktuellen G5P/60k/90k nutzen `distill_align` + α=0,3, aber **keine** KD-Maske; die Unterdrückung ist dort weiterhin aktiv.

**Zeilen ganz löschen?** Nein: 15,2 % der Wortpositionen, 75,7 % der Sätze betroffen; das entfernt CE-Spelling-Supervision auf genau den seltenen/OOV-Wörtern und verschiebt die Verteilung zu häufigen Wörtern. Nur wenn Inferenz ausschließlich ganze Wörter könnte, wäre das konsistent; hier werden Pieces emittiert.

## 2. Weitere geprüfte Messungen

### 2.1 Top-k-Lehrermasse (nicht-leere Rows, `de_soft_2m.npz`)

| k | mittlere Masse | Median | Anteil Rows <90 % |
|---:|---:|---:|---:|
| 4 | 69,6 % | 69,0 % | 79,3 % |
| 8 | 85,1 % | 87,5 % | 56,1 % |
| 10 | 89,7 % | 92,6 % | 42,5 % |
| 12 | 93,1 % | 96,2 % | 30,1 % |
| 16 | 97,4 % | 99,9 % | 7,9 % |
| 24 | 100 % | 100 % | 0 % |

K=10 verwirft im Mittel 10,3 % der Top-24-Masse; K=16 nur 2,6 %. Die alte Audit-Empfehlung „Top-k K≈10“ ist damit **nicht** gut belegt. In der 300M-Studie waren plain K=5/12/25 schlechter als CE; K=10 ist nicht direkt getestet, liegt aber zwischen 5 und 12; K=24 ist grenzwertig; K=50–100 wäre besser, ist aus dem 24er-Cache aber nicht rekonstruierbar. **Schüler-only sinnvoll: K=16 vs. K=24 testen; K=10 nur mit Tail/CE-heavy, nicht blind.**

### 2.2 Parameterarithmetik

Aktuell: `V·d = 24.576·256 = 6.291.456` (61,2 % der 10,28 M Parameter). 6 Blöcke: `6·(4d²+2·d·ff) = 6·655.360 = 3.932.160`. Das Modell ist also ein **3,9-Mio.-Transformer mit 6,3-Mio.-Vokabular**. Eine Vokabularreduktion auf 12–16k würde 2,2–3,2 Mio. Parameter freisetzen; das ist der größte Qualitäts/Parameter-Hebel, braucht aber Teacher-Remap/neuen Lauf.

Schüler-only Formen (Engine liest den Header; `d % heads == 0` reicht, `wmlm-training-windows.md:319`):

| Form | Transformer-Parameter | Gesamt ca. | Int8 ca. | Bewertung |
|---|---:|---:|---:|---|
| d256/L6/ff768 (heute) | 3,93 M | 10,28 M | 10,9 MB | Baseline |
| d224/L8/ff672 | 4,01 M | 9,57 M | ~10,1 MB | Depth-over-width; 10M unverifiziert; billiger A/B |
| d256/L8/ff768 | 5,24 M | 11,59 M | ~12,2 MB | einfache Tiefe; ≤13 MB; testen |
| d288/L6/ff896 | — | 12,8 MB | 12,8 MB | **bereits negativ** (Glide 77,32) |

### 2.3 Messauflösung

`paired_eval.py --mde 2588`: 1,23 / **1,74** / 2,46 / 3,01 pp bei Discordance 5 / **10** / 20 / 30 %. Ein +0,5-pp-Claim auf 2.588 Zügen ist Rauschen. Für 1 pp bei 10 % Discordance braucht es ~7.850 Züge (Research; die marginale Rechnung nennt ~27.800). ppl ist Trainingsdiagnose; Produktmetrik ist Glide top-1/top-4, plus OOV-/Piece-Genauigkeit und Latenz.

## 3. Research-Synthese

### 3.1 Zero-mass KD / Vocabulary

- **Maske KD, behalte CE.** Der Piece-Gradient ist positiv (Unterdrückung); CE ist der einzige Spelling-Supervisor. [Hinton 2015](https://arxiv.org/abs/1503.02531); [Kim & Rush 2016](https://arxiv.org/abs/1606.07947); [Kudo 2018](https://arxiv.org/abs/1804.10959).
- **Zeilen löschen nur bei W-only-Inferenz.** Sonst Train/Test-Mismatch; die Wortwahrscheinlichkeiten werden um `1/P(W)` inflationiert. Hier werden Pieces emittiert → nicht löschen.
- **Kandidatenliste nicht prunen.** Support-Pruning kann nur helfen, wenn das Ziel bleibt; BPE-Vokabular-Trimming kann die Qualität sogar verschlechtern ([Cognetta et al. 2024](https://arxiv.org/abs/2404.00397)); Typ- vs. Tokengewichtung ist entscheidend ([Ushio et al. 2023](https://arxiv.org/abs/2305.15020)); seltene Wörter sind die Schwäche kleiner LMs ([Chen et al. 2016](https://aclanthology.org/P16-1186/)).
- **Word-Space-Marginalisierung** ist die prinzipielle Lösung, braucht aber Lehrer-Wortmasse; der Cache hat für OOV-Pieces keine. Ohne Teacher: Maske/Soft-Weight, kein Row-Drop.

### 3.2 Top-k / Tail / Temperatur

- Renormalisiertes Top-k ist **biased**: Kopf massen werden um `1/Z` aufgeblasen, Tail fehlt; CE ist Gegengewicht ([Anshumann et al. 2025](https://aclanthology.org/2025.acl-long.885/); [Khanbayov & Kurban 2026](https://arxiv.org/abs/2610.15589)).
- Plain K=5/10/16 war in einer 300M-Studie schlechter als CE; K=24 grenzwertig; K=50–100 besser, aber aus dem 24er-Cache nicht verfügbar. Mit explizitem Tail-Term ist K=5–10 gut ([Dasgupta et al. 2026](https://arxiv.org/abs/2602.20816)); der Tail fehlt hier.
- α (KD-Gewicht) 0,3–0,4, CE 0,6–0,7; T≈1,5–2,0 (auf Lehrer-Logits vor Top-k; aus dem Cache nur approximativ); KD früh, CE spät ([Peng et al. 2024](https://arxiv.org/abs/2410.16215); [Zhong et al. 2024](https://arxiv.org/abs/2402.11890)). Label-Smoothing nicht als Tail-Ersatz ([Müller et al. 2019](https://arxiv.org/abs/1906.02629)).

### 3.3 Edge-LM / Reranker

- Das Modell ist **vokabularlastig** (61 % Emb). Depth-over-width hat sub-1B-Evidenz ([MobileLLM](https://arxiv.org/abs/2402.14905)); tied embeddings behalten ([Press & Wolf](https://arxiv.org/abs/1608.05859)); RoPE/GQA/SwiGLU bringen bei ctx40/d256 keinen belegten Vorteil; RMSNorm ist Speed, kein Top-1-Hebel; Checkpoint-Averaging ist billig ([SWA](https://arxiv.org/abs/1803.05407), [Model Soups](https://arxiv.org/abs/2203.05482)).
- **Reranker/Listwise** ist der direkteste Produkt-Hebel: top-1 78,5 %, top-4 84,9 % → 6,4 pp Kopfraum. Ein k=8-Cross-Encoder/Listwise-Head auf Decoder-Kandidaten trainiert direkt die Zielentscheidung; Evidenz bei ≥110M, bei 10M **unverifiziert** ([Cross-Encoder](https://arxiv.org/abs/1901.04085); [ListT5](https://arxiv.org/abs/2402.15838)). Kalibrierung als Log-Prob ausgeben, nicht als roher Margin.
- **Daten:** Dedup, Register-Mix (Chat/News vs. Wikipedia), Compound-Oversampling; 2M ist 53 % Chat / 47 % News + 15,1 % OpenSubtitles; Glide ist Wikipedia-artig. 1,2M epoch-matched (55k) ist ein sauberer Datenvergleich.

### 3.4 Deutsche Morphologie/Komposita (Schüler-only)

- Das reale Residual ist **nicht** die alte 20,5-%-Zahl, sondern `>MAX_WORD_PIECES` (6). 2,45 %/10,2 % der Typen, 0,084 %/0,145 % der Token; 4 Glide-Ziele. Entfernen ist neutral/−0,04 pp. Der kleine Fix ist `MAX_WORD_PIECES` 6→8 (Rust, `lm.rs:60`) oder längere Start-Pieces; das kostet zusätzliche Forward-Steps für lange OOV-Wörter und ist kein Teacher-Thema.
- **Ohne Teacher** ist die **Wortliste** fixiert; die **2.048 Pieces** können dagegen neu gebaut werden (Wort-IDs stabil, Pieces hinter den Wörtern, Teacher-Cache gültig). 32k-Wortvokabular/word-space braucht Teacher.
- **Mit Teacher** (Zukunft): 32k-Vokabular mit Alphabet-Seed + Komposita, word-space Targets; CompoundPiece/Compound-Splitting reduziert harte deutsche Komposita; Byte-Fallback ist die robuste OOV-Alternative, aber teurer ([Sennrich et al. 2016](https://aclanthology.org/P16-1162/); [Kudo 2018](https://arxiv.org/abs/1804.10959); [ByT5](https://arxiv.org/abs/2105.13626)). Deutsche Komposita-Evidenz: neuronale Splitter übertreffen den Stand um ~5 % ([Krotova et al. 2020](https://arxiv.org/abs/2003.09606)); Pre-Splitting kann die Repräsentation seltener Komposita verbessern, aber der Tokenizer-/Vokabularwechsel invalidiert den Teacher-Cache ([Jenkins et al. 2023](https://aclanthology.org/2023.emnlp-main.1002.pdf)).
- **Nicht** Kandidatenwörter entfernen; BPE-Vokabular-Trimming kann die Qualität verschlechtern ([Cognetta et al. 2024](https://arxiv.org/abs/2404.00397)).
### 3.5 Stück-Rebuild ohne Teacher (neu, wichtig)

- **Hybrid Wort + WordPiece bleibt richtig.** Wort-Tokens halten Sequenzen kurz; Pieces geben offenes Vokabular. Hybride sind schneller als Character-Level und vermeiden `<unk>` ([Luong & Manning 2016](https://arxiv.org/abs/1604.00788); [GNMT 2016](https://arxiv.org/abs/1609.08144)); monolinguale Tokenizer sind qualitätsrelevant ([Rust et al. 2020](https://arxiv.org/abs/2012.15613)).
- **`MAX_WORD_PIECES` 6→8 zuerst.** Zero Retraining, zero Teacher, reversibel; deckt `k=7,8` auf dem Piece-Scoring-Pfad; 4 Glide-Ziele. Kosten: zwei zusätzliche Forward-Steps pro langem OOV-Kandidaten; der Typing-Strip ist nicht betroffen, weil er nur gelistete Wörter scored.
- **2.048 Pieces neu bauen, Wortliste festhalten.** `distill.py` speichert Student-Token-IDs; Pieces sind **nie** KD-Targets und werden in `prep.py` hinter den Wörtern angehängt. Ein neues Piece-Inventar (Buchstaben, deutsche Morpheme/Affixe/Digraphs, ggf. Unigram/BPE statt Substring-Frequenz) hält die **Wort-IDs und den Teacher-Cache gültig**; nur `train.npz`, `align` und `masks` müssen neu gebaut werden. Kein Teacher-Pass.
- **BPE-Dropout/Segmentierungs-Augmentation** kann die Robustheit erhöhen ([Provilkov et al. 2019](https://arxiv.org/abs/1910.13267)); kleiner Code + Retrain.
- **Komposita nur in der Kandidatengenerierung splitten**, nicht als LM-Input: CompoundPiece senkt harte deutsche Komposita von 14,6 % auf 1,8 % ([arXiv 2305.14214](https://arxiv.org/abs/2305.14214)); Pre-Splitting hilft in-restricted ([Jenkins et al. 2023](https://aclanthology.org/2023.emnlp-main.1002/)), aber Splitting ist kein automatischer Gewinn ([Koehn & Knight 2003](https://aclanthology.org/E03-1076/)) und hat False-Split-Risiko (`hast`+`alt` vs. `haushalt`, `issue-966-followup.md:474`).
- **Byte/Character** ist bei 10M der falsche Trade ([ByT5](https://arxiv.org/abs/2105.13626); [CANINE](https://arxiv.org/abs/2103.06874)).
- **Wortliste neu selektieren** (Token-Coverage) wäre der größte Coverage-Hebel, ändert aber Wort-IDs und invalidiert den Cache ohne Remap → nicht ohne Teacher.

## 4. Schüler-only Plan (kein neuer Lehrer)

| Prio | Experiment | Warum | Kosten | Metrik |
|---:|---|---|---|---:|---|
| 1 | **KD-Maske/Soft-Weight auf Piece-Rows** (V2; λ=0,1–0,3) + α=0,3 | Entfernt nachgewiesene Unterdrückung; CE bleibt | 3k 40 min; 30k 6,3 h | Heldout + **OOV/Piece-Accuracy** + Glide |
| 2 | **`MAX_WORD_PIECES` 6→8** | zero Retraining; 4 Glide-Ziele; deckt `k=7,8` | Minuten | Glide, Latenz |
| 3 | **2.048 Pieces neu bauen** (Wortliste stabil) | kein Teacher; senkt `k`, bessere deutsche Morphologie | Prep + 30k Retrain | Glide, `k`-Histogramm, OOV |
| 4 | **K=16 vs. 24**, α 0,3/0,4, share 0,25/0,5/0,75 | K=10 ist nicht belegt; K=16 hält 97,4 % Masse | 3k je 40 min | Glide top-1/top-4, OOV |
| 5 | **Blend weight/cap re-sweep** auf größerem Held-out | potenziell +4–6 pp top-1 (English proxy); Overfit-Gefahr | Stunden | Glide top-1, 2.294-Züge-Grenze |
| 6 | **EMA/Last-k-Averaging** | billig, positiv | fast 0 | Heldout/Glide |
| 7 | **Daten-Reweighting**: OpenSubtitles raus (NC), **lizenzklare Chat-Daten** rein, News/Wikipedia hoch | Domain-Mismatch; 15,1 % NC; Chat-Register erhalten | Subset, 3k | Glide, Lizenz |
| 8 | **Form-A/B**: d224/L8/ff672 oder d256/L8 | Emb 61 %; Depth-over-width | 3k/30k | Größe, Latenz, Glide |
| 9 | **Reranker/Listwise** auf Decoder-Pools | direkter Top-1-Hebel; 6,4 pp Kopfraum | Tage (Engine) | Glide top-1, Latenz |
| 10 | **Warm-Start** altes 2M + `distill_align` | billige Rettung, kein Teacher | 3k 40 min | Heldout/Glide |
| 11 | **20k-Heldout / größeres Glide-Set** | MDE 1,74 pp | Minuten/Code | Statistik |

**Nicht tun:** Kandidatenwörter entfernen (neutral/−0,04 pp); Piece-Rows ganz löschen (75,7 % Sätze, CE-Verlust); plain K=10; d288; RoPE/SwiGLU/GQA bei ctx40; Label-Smoothing; `share=1.0`; ppl als Ship-Metrik.

## 5. Rebuild, falls später ein Lehrer-Pass erlaubt ist

1. **2.048 Pieces zuerst** (ohne Teacher): Buchstaben/Morpheme/Affixe/Digraphs, Wortliste stabil; Teacher-Cache bleibt gültig; `train.npz`/`align`/`masks` neu bauen.
2. **32k-Wortvokabular** mit Alphabet-Seed, Komposita und word-space Targets; 32k kostet ~+2,1 Mio. Parameter (~12,4 MB), innerhalb 13 MB. Behebt Piece-Rows und Wortabdeckung an der Wurzel; braucht Teacher-Remap.
3. **True Tail + BOS** (Tail-Masse ist im 24er-Cache nicht rekonstruierbar).
4. **9B-Base-Lehrer** (gewann den Lehrer-A/B: +1,22/+2,31 top-1, NLL −0,18/−0,19); 27B post-trained ist gemischt (Chat-NLL schlechter als 9B-Base).
5. **Sauberer Korpus** (OpenSubtitles raus, Near-Dup-Dedup, Register-balanced) und **Reranker**.
6. **32k/word-space** löst das 15,3-%-Problem; die Maske bleibt als Fallback.

## 6. Reproduktion

```bash
# Audit 20,5 % (read-only, Python)
python - <<'PY'
import sys, os
sys.path.insert(0, "tools/wmlm")
from common import Pieces
root = "wmk-glide"
v = [l.rstrip("\n") for l in open(f"{root}/artifacts/data/vocab.txt", encoding="utf-8")]
vset = set(v)
s = set(t[1:] for t in v if t.startswith("\u2581"))
c = set(t[2:] for t in v if t.startswith("##"))
pe = Pieces(s, c)
for name, path in [("150k", f"{root}/artifacts/data/de_150k.txt"),
                   ("591k", f"{root}/artifacts/data/de_150k_comp3.txt")]:
    n = inv = none = long = 0
    for line in open(path, encoding="utf-8"):
        p = line.split()
        if not p: continue
        w = p[0].lower()
        if len(w) < 2 or not w.isalpha(): continue
        n += 1
        if w in vset: inv += 1; continue
        enc = pe.encode(w)
        if enc is None: none += 1
        elif len(enc) > 6: long += 1
    print(name, n, inv, none, long, "unspellable", none + long)
PY
# Glide-Ablation (WSL, CPU)
COLS=11 FREQ=0.5 GAP=2.0 WEIGHT=0.5 CAP=5 RESULTS=8 THREADS=8 \
  native/wm-engine/target/release/examples/glide_lm_blend_eval \
  wmk-glide/artifacts/data/de_swipes.jsonl \
  wmk-glide/artifacts/data/german.json \
  <wortliste> wmk-glide/artifacts/models/de_context_2m.wmlm
# MDE
python tools/wmlm/paired_eval.py --mde 2588
```

Artefakte: `de_soft_2m.masks.masks.json`, `audit_signal.json`, `gate-log.md:24`, `de_context_2m.wmlm`, `de_150k.txt`, `de_150k_comp3.txt`.

## 7. Offene Fragen

- Bringt KD-Maske/Soft-Weight bei 30k **OOV/Glide** etwas, auch wenn ppl flach bleibt?
- K=16 vs. 24: Produktmetrik, nicht nur ppl.
- Daten-Reweighting: Wikipedia/News statt Chat/OpenSubtitles.
- Reranker bei 10M: lohnt der Engine-Aufwand?
- Kontextlimit: `logprob_pieces` verliert multi-piece-Wörter, wenn `tokens.len()+pieces.len()>ctx`; das ist eine separate OOV-Grenze, die die Typabdeckung nicht zeigt.

