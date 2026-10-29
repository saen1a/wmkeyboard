# Deutsches `.wmlm`: Training unter Windows (RX 9060 XT) und was es kostet

Stand: 27.10.2026. Ergänzt [`wmlm-gain.md`](wmlm-gain.md) (was ein deutsches
Modell bringt) und [`issue-german-wmlm.md`](issue-german-wmlm.md) (das
Upstream-Rezept). Hier geht es um zwei Fragen: **Wie trainiert man das Modell
auf einem Windows-Rechner mit RX 9060 XT?** Und: **Was kostet das, lokal,
in der Cloud oder über eine API?** Der auf dieser Maschine getestete
Durchlauf (ROCm, Lehrerwahl, gemessener Durchsatz, Gates) steht in
[`wmlm-training-plan.md`](wmlm-training-plan.md).

Alle Zahlen sind entweder aus dem Repo-Code, aus den verlinkten
Anbieterseiten (Abruf 27.10.2026) oder mit
[`tools/wmlm_token_coverage.py`](tools/wmlm_token_coverage.py) gemessen.
Nichts davon ist ein Trainingsergebnis eines deutschen Modells — ein solches
existiert weiterhin nicht.

## 1. Kurzfassung

- **Windows-native kann PyTorch, aber kein Training.** ROCm 7.2.1 listet die
  RX 9060 XT (gfx1200) offiziell, mit PyTorch 2.9.1, Python 3.12 und
  Adrenalin 26.2.2. AMD schreibt aber ausdrücklich „No ML training support“
  und „only LLM batch sizes of 1“.
- **Training läuft in WSL2.** Ubuntu 24.04/22.04, ROCm 7.2.1, librocdxg; die
  9060 XT steht in der WSL-Matrix, und ROCDXG nennt „machine learning
  training“ als Einsatzzweck.
- **Größerer Lehrer + kleinerer Batch ist der richtige Tausch.** Der Batch im
  Lehrer-Pass ist reine Inferenz und kostet nur Zeit. 16 GB VRAM deckeln den
  lokalen Lehrer bei ~4B (FP16); 7B passt nicht.
- **Der größte deutsche Engpass ist die Token-Abdeckung, nicht die
  Lehrergröße.** `distill.py` verwirft jedes Wort, das der Lehrer in mehrere
  Token zerlegt. Bei Qwen sind das ~80 % der deutschen Worttypen (20,1 %
  Abdeckung), bei Gemma 3 4B ~67 % (32,6 %). Frequenzgewichtet sieht es mit
  76,1 % bzw. 86,6 % besser aus — die Lücke sitzt aber genau im Chat-Register
  (`nein`, `warum`, `danke`, `hallo`, `morgen`).
- **Kosten sind einstellig bis knapp zweistellig.** Lokal 2–5 € Strom; ein
  API-Lehrer (Gemma 3 27B) für 15M Tokens 1–4 $; eine gemietete GPU für den
  ganzen Lauf 5–15 $. Die eigentlichen Kosten sind Arbeitszeit.

## 2. Windows: was offiziell geht und was nicht

### 2.1 Nativ

| | |
|---|---|
| OS | Windows 11 |
| GPU | RX 9060 XT (gfx1200) — offiziell gelistet |
| PyTorch | 2.9.1+rocm7.2.1 |
| Python | 3.12 |
| Treiber | Adrenalin 26.2.2 |
| Datentypen | FP16, FP8 (FP8 nur RDNA4) |

AMD-Limits für Windows (wörtlich):

> „No ML training support.“
>
> „On Windows, only LLM batch sizes of 1 are officially supported.“

Das heißt: Für Inference ist die native Installation brauchbar, für das
`.wmlm`-Training nicht. Wer es trotzdem versucht, arbeitet ohne offizielle
Unterstützung; getestet ist nur Batch 1.

### 2.2 WSL2

Der offizielle Trainingsweg auf dieser Hardware:

- Ubuntu 24.04 LTS oder 22.04
- ROCm 7.2.1 (Userspace) + **librocdxg** (ROCDXG)
- Windows-Treiber Adrenalin 26.2.2 für WSL2
- `HSA_ENABLE_DXG_DETECTION=1` für ROCm 7.2.x (ab 7.13 nicht mehr nötig)
- PyTorch 2.9.1+rocm7.2.1, Python 3.12

Die WSL-Matrix listet die RX 9060 XT; ROCDXG beschreibt sich als Brücke für
„AI inference, machine learning training, and HPC applications“. Im
Gegensatz zu nativem Windows sind unter WSL auch Triton und der übrige
ROCm-Stack unterstützt.

### 2.3 Setup

```powershell
wsl --install -d Ubuntu-24.04
# danach Adrenalin 26.2.2 für WSL2 installieren und neu starten
```

```bash
# in WSL, nach ROCm-7.2.1-Installation und librocdxg-deb
export HSA_ENABLE_DXG_DETECTION=1

python3.12 -m venv ~/wmlm-venv
. ~/wmlm-venv/bin/activate

pip install --no-cache-dir \
  https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.1/torch-2.9.1%2Brocm7.2.1.lw.gitff65f5bc-cp312-cp312-linux_x86_64.whl \
  https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.1/torchvision-0.24.0%2Brocm7.2.1.gitb919bd0c-cp312-cp312-linux_x86_64.whl
pip install numpy transformers accelerate

python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Daten und Checkpoints gehören ins WSL-Dateisystem (`~`), nicht nach
`/mnt/c`: über die Windows-Brücke ist `np.load` auf großen Arrays deutlich
langsamer.

Bei 32 GB Host-RAM und knapper WSL-Zuteilung:

```ini
# C:\Users\<du>\.wslconfig
[general]
instanceIdleTimeout=-1

[wsl2]
memory=24GB
swap=8GB
vmIdleTimeout=-1
```

`vmIdleTimeout`/`instanceIdleTimeout` sind Pflicht für einen Overnight-Lauf:
Ohne sie schaltet WSL die Instanz nach ~60 s ohne angehängte Shell ab, auch
wenn ein systemd-Dienst läuft. Genau das hat den ersten 75k-Lauf nach wenigen
Minuten beendet.

## 3. Lehrerwahl: 16 GB VRAM

`distill.py` lädt den Lehrer mit `dtype=torch.float16` auf die GPU. Die
Gewichte sind der Speicherfresser, nicht der 10–19M-Schüler.

| Lehrer | FP16-Gewichte | lokal 16 GB | sinnvoller distill-Batch |
|---|---:|---|---|
| Qwen2.5-1.5B | 3,1 GB | ja | 64–128 |
| Qwen2.5-3B | 6,2 GB | ja | 32–64 |
| Qwen3-4B-Base | ~8 GB | ja | 16–32 |
| Gemma 3 4B (`-pt`) | ~8 GB | ja | 16–32 |
| Qwen2.5-7B | 15,2 GB | **nein** | — |
| Gemma 3 12B | ~24 GB | nein | Cloud/API |
| Gemma 3 27B | ~54 GB | nein | Cloud/API |

7B passt mit FP16 nicht: 15,2 GB Gewichte plus Aktivierungen und
KV-Cache sprengen 16 GB. 4-Bit-Quantisierung wäre theoretisch möglich, aber
`distill.py` unterstützt sie nicht, und bitsandbytes ist auf ROCm/WSL nicht
Teil des offiziellen Stacks. Für >4B ist der API- oder Cloud-Lehrer der
richtige Weg (Abschnitt 6).

**Batch ≠ Kontext.** Ein kleinerer Batch im Lehrer-Pass ändert das Ergebnis
nicht, nur die Laufzeit. `ctx=40` bleibt: Das ist der Vertrag mit
`wm-engine/src/lm.rs`, dem Glide-Harness und der App. Wer VRAM sparen muss,
senkt den Batch, nicht `ctx`.

## 4. Der eigentliche Engpass: Token-Abdeckung

`distill.py` baut die Lehrer-Ziele so:

```python
for sid, w in enumerate(vocab):
    for form in {w, w.capitalize()}:
        enc = tok.encode(" " + form, add_special_tokens=False)
        if len(enc) == 1:
            s_ids.append(sid)
            t_ids.append(enc[0])
```

Nur Wörter, die der Lehrer als **einen** Token schreibt, bekommen
Lehrer-Masse. Alles andere behält das One-Hot-Ziel. Das ist keine
Eigenschaft des Lehrers, sondern seines Tokenizers — und bei Deutsch ein
großes Loch.

### 4.1 Messung

Gemessen mit [`tools/wmlm_token_coverage.py`](tools/wmlm_token_coverage.py)
auf den 24.000 häufigsten Wörtern aus `de_150k.txt` (im Daten-Zip
`data/wmk-glide-de-data.zip`), nach genau der Regel oben. Die Gewichtung
nutzt die Frequenzspalte der Liste; sie ist eine Näherung auf das spätere
`prep.py`-Vokabular, keine exakte Auszählung.

| Lehrer-Tokenizer | DE Worttypen | DE frequenzgewichtet | EN Worttypen |
|---|---:|---:|---:|
| Qwen2.5-1.5B / 3B / Qwen3-4B | **20,1 %** | 76,1 % | 78,6 % |
| Gemma 3 4B | **32,6 %** | 86,6 % | 91,2 % |

Die drei Qwen-Tokenizer sind byte-identisch (gleiche `tokenizer.json`,
md5 `3f99a313c3754208a7f3acfccadc53cd`); Qwen2.5 und Qwen3 teilen sich das
Vokabular. Die Gemma-3-4B-Datei aus dem Unsloth-Spiegel ist für `-it` und
`-pt` identisch (md5 `47a57159581e58f7886ef7f99a0e7dc9`); die offizielle
Datei ist lizenzbedingt gated.

Die fehlenden Wörter sind nicht exotisch, sondern Alltag und Chat:

```
nein     -> Ġne + in
warum    -> Ġwar + um
danke    -> Ġdan + ke
hallo    -> Ġhal + lo
morgen   -> Ġm + orgen
gegangen -> Ġgeg + angen
```

Gemma 3 4B deckt `nein`, `warum`, `morgen`, `gegangen`, `Straße` ganz ab;
`danke` und `hallo` bleiben mehrteilig. Deshalb der Sprung von 20,1 auf
32,6 Prozent: größeres, multilinguales Vokabular.

### 4.2 Konsequenz

Ein größerer Lehrer hilft bei den 80 % Worttypen nicht, deren Wahrscheinlichkeit
gar nicht ankommt. Bevor man 30 Stunden in einen 27B-Lehrer steckt, sollte
das Mapping repariert werden.

## 5. Multi-Token-Mapping

Für ein Wort `w`, das der Lehrer in `t1..tk` zerlegt, ist die gesuchte
Wahrscheinlichkeit das Produkt der bedingten Token-Wahrscheinlichkeiten:

```
p(w | Kontext) = p(t1 | Kontext)
               * p(t2 | Kontext, t1)
               * ...
               * p(tk | Kontext, t1..t(k-1))
```

Alle Faktoren stehen im Forward-Pass, der ohnehin über den Satz läuft:
`logits` an der Position vor `t1` liefert `p(t1)`, die Position von `t1`
liefert `p(t2)`, und so weiter. `offset_mapping` sagt, welche Lehrer-Token
zu welchem Wort-Span gehören. Der bestehende `topk`-Schnitt über das
Schüler-Vokabular bleibt; die Produkte werden wie bisher über die Top-k
renormalisiert.

Skizze für `distill.py`:

```python
# statt nur Ein-Token-Wörtern: pro Schülerwort die Lehrer-Tokenfolge merken
s_ids, t_seqs = [], []
for sid, w in enumerate(vocab):
    if sid < len(SPECIALS) or w.startswith(START) or w.startswith(CONT):
        continue
    for form in {w, w.capitalize()}:
        enc = tok.encode(" " + form, add_special_tokens=False)
        if enc:
            s_ids.append(sid)
            t_seqs.append(enc)
            break

# im Satz: Spans aus offsets, dann
p_word = 1.0
for j in span:
    p_word *= probs[i, j - 1, teacher_ids[j]].item()
mass[sid] += p_word
```

Wichtig:

- Der erste Lehrer-Token eines Wortes wird von dem Token davor vorhergesagt.
  Für das erste Wort eines Satzes gibt es keinen Vorgänger; die bestehende
  Schleife überspringt es ohnehin (Row 0 bleibt null). Ab dem zweiten Wort
  existiert die Vorgängerposition.
- Für sehr lange Wörter in Log-Raum rechnen (`exp(sum(log p))`), sonst
  Unterlauf.
- Die Summe über das Schüler-Vokabular ist danach keine echte Verteilung
  mehr (die Bedingungskontexte unterscheiden sich). Das war sie mit den
  Ein-Token-Summen aber auch nicht; die Top-k-Renormalisierung bleibt eine
  Heuristik.
- Erwartung: Abdeckung von 20,1 % auf praktisch 100 % der Worttypen. Das ist
  die Voraussetzung dafür, dass ein 12B/27B-Lehrer für Deutsch überhaupt
  zählt. Der Gewinn ist noch nicht gemessen.

## 6. Rezept

### 6.1 Daten

```bash
cd tools/wmlm

python corpus.py \
  tatoeba:deu_sentences.tsv.bz2 \
  leipzig:deu_news_2023_1M.tar.gz \
  leipzig:deu_wikipedia_2021_1M.tar.gz \
  lines:opensub_de.txt:1:1 \
  > de_sentences.tsv
```

OpenSubtitles vorher zu „eine Zeile pro Satz“ aufbereiten; es liefert den
Dialog-/Chat-Register, der in News und Wikipedia fehlt. Duplikate entfernen,
sehr kurze und über-`ctx`-lange Sätze filtern. Ziel: 2–3 Mio. Sätze.

```bash
python prep.py de_sentences.tsv de_lm \
  vocab=32768 pieces=4096 ctx=40 seed_words=de_aosp.txt
```

`pieces=4096` ist für deutsche Komposita wichtiger als für Englisch; das
Vokabular bleibt mit ~32k und ~13 MB Modellgröße im Rahmen des catalogs.

### 6.2 Lehrer

Lokal, 16 GB:

```bash
python distill.py de_lm de_soft.npz \
  teacher=google/gemma-3-4b-pt \
  sentences=500000 topk=24 batch=16
```

- `gemma-3-4b-pt` (Base) statt `-it`: rohe Next-Token-Verteilung.
- HF-Lizenz akzeptieren, Token setzen. Fallback ohne Gating:
  `Qwen/Qwen2.5-3B` — 12 Prozentpunkte weniger deutsche Abdeckung.
- Bei OOM `batch=8`; bei NaN im Lehrer `dtype=bfloat16` statt `float16`.

### 6.3 Schüler

```bash
# auslieferbar, ~12M Parameter bei 32k-Vokabular
python train.py de_lm de_run steps=80000 batch=256 \
  d=256 layers=6 ff=768 ctx=40 \
  distill=de_soft.npz distill_alpha=0.5

# Qualitätsmaximum, ~19M Parameter (~20 MB int8)
python train.py de_lm de_run_big steps=80000 batch=192 \
  d=320 layers=8 ff=1024 ctx=40 \
  distill=de_soft.npz distill_alpha=0.5
```

`train.py` hat **keine Gradient-Akkumulation**. Für effektiv Batch 384
entweder `batch=384` (passt bei d256/6/768 meist) oder ~10 Zeilen
Akkumulation ergänzen. `lm.rs` liest die Formen aus dem Header und verlangt
nur `d % heads == 0`; das größere Modell ist also ohne Engine-Änderung
exportierbar. Ob es auf dem Telefon schnell genug ist, muss gemessen werden.

### 6.4 Export und Messung

```bash
python export.py de_run/best.pt de_lm/vocab.txt de_context.wmlm \
  --langs=de --name=German

cargo run --release --example lm_probe -- de_context.wmlm "ich will nach" ...
```

Danach:

- `typing_eval` auf `de_lm/heldout.tsv` (nicht auf Trainingssätzen)
- der Glide-Harness aus [`experiments/glide_lm_blend_eval.rs`](experiments/glide_lm_blend_eval.rs)
- `distill_alpha` 0,3 / 0,5 / 0,7 und ggf. `distill_share` vergleichen

Die Messlatte aus [`wmlm-gain.md`](wmlm-gain.md): Der englische Proxy gab
+4,93 Glide-top-1 (73,41 → 78,34) mit `0,7 / 3,0`; für Deutsch ist +3 bis +5
auf der 74,15-Basis geschätzt. Ob 4B/27B-Lehrer das obere Ende erreichen,
ist offen.

## 7. Kosten

### 7.1 Rechenmenge

Eine grobe Rechnung: **500k Sätze ≈ 15M Tokens**, **1,5M Sätze ≈ 45M
Tokens** (deutsch, ~30 Tokens/Satz inkl. Subwörtern). Der Lehrer-Pass liest
diese Tokens einmal; der Schüler sieht sie über viele Schritte.

### 7.2 Lokal

| | |
|---|---|
| GPU | RX 9060 XT, 150–182 W TBP |
| Systemsleistung | ~250–300 W |
| Laufzeit | Lehrer 10–30 h + Schüler 4–8 h |
| Strom | ~5–12 kWh |
| Preis | 0,30–0,40 €/kWh |
| **Summe** | **2–5 €** |

Das ist der billigste Weg, und die Karte ist schon da. Der Preis ist Zeit:
Der 4B-Lehrer über 500k Sätze läuft eher 15–30 h als 2 h.

### 7.3 Cloud-GPU (echtes Training)

| GPU | Preis | Laufzeit | Summe |
|---|---:|---:|---:|
| RTX 4090 (Vast/RunPod) | ~0,30–0,50 $/h | 6–10 h | 2–5 $ |
| A100 80 GB (DeepInfra) | 1,49 $/h | 4–8 h | 6–12 $ |
| H100 80 GB (DeepInfra) | 2,90 $/h | 2–5 h | 6–15 $ |

Für ein 10–19M-Modell ist eine A100 überdimensioniert; eine 4090 reicht.
Der Vorteil der Cloud ist nicht der Preis, sondern dass der Lehrer-Pass mit
einem 27B-Modell in Stunden statt Tagen läuft.

### 7.4 API-Lehrer (nur Destillation, kein Training)

Eine API trainiert dein `.wmlm` nicht. Sie kann den **Lehrer-Pass** liefern,
wenn sie Prompt-Logprobs zurückgibt. Preise pro 1M Tokens (Abruf 27.10.2026):

| Anbieter / Modell | Input | Output | 15M Tokens | 45M Tokens |
|---|---:|---:|---:|---:|
| DeepInfra Gemma 3 27B | 0,08 $ | 0,16 $ | 1,20–3,60 $ | 3,60–10,80 $ |
| DeepInfra Gemma 3 12B | 0,05 $ | 0,15 $ | 0,75–3,00 $ | 2,25–9,00 $ |
| DeepInfra Qwen2.5-72B | 0,36 $ | 0,40 $ | 5,40–11,40 $ | 16,20–34,20 $ |
| DeepInfra Llama 3.3 70B | 0,10 $ | 0,32 $ | 1,50–6,30 $ | 4,50–18,90 $ |
| DeepSeek Flash (off-peak) | 0,15 $ | 0,60 $ | 2,25–11,25 $ | 6,75–33,75 $ |
| DeepSeek Flash (peak) | 0,30 $ | 1,20 $ | 4,50–22,50 $ | 13,50–67,50 $ |
| DeepSeek Pro (off-peak) | 0,66 $ | 1,98 $ | 9,90–39,60 $ | 29,70–118,80 $ |
| OpenCode Go | — | — | 10 $/Monat | nicht geeignet |

Lesart der Spannen: unten nur die Prompt-Tokens (wenn `echo` die
Prompt-Logprobs als Input abrechnet), oben Prompt + Output. Die genaue
Abrechnung hängt davon ab, wie der Anbieter `echo` behandelt. Bei DeepSeek
ist die untere Spanne nur theoretisch: Prompt-Logprobs gibt es dort nicht,
relevant ist die obere (Output) — und die fällt nur an, wenn man generiert,
nicht wenn man einen Korpus bewertet.

**DeepInfra** hat `logprobs`/`top_logprobs` (1–20) und einen
`/v1/openai/completions`-Endpunkt mit `echo`. Wenn `echo=true` dort auch die
Prompt-Token-Logprobs liefert — mit einem 10-Satz-Test prüfen, nicht
annehmen —, ist der Lehrer-Pass für 1–4 $ machbar. 200 gleichzeitige
Requests pro Account; Flex-Tier 0,8×.

**DeepSeek** liefert `logprobs` nur für **generierte** Tokens. Ein Echo des
Prompts mit Prompt-Logprobs gibt es nicht. Damit ist DeepSeek kein
Korpus-Lehrer; es taugt für synthetische Sätze (Output-Tokens) oder für
Destillation entlang der eigenen Generierung. Off-peak ist halber Preis:
peak ist 01:00–04:00 und 06:00–10:00 UTC werktags, alles andere off-peak.

**OpenCode Go** ist ein Coding-Abo: 10 $/Monat (Go) bzw. 40 $/Monat (Go
Plus), mit monatlichen Modell-Limits und 5-Stunden-/Wochenfenstern. Es ist
keine Trainings-API, kein verlässlicher Logprob-/Echo-Endpunkt und für
15M-Token-Bulk nicht gedacht. Nicht dafür verwenden.

### 7.5 Gesamtszenarien

| Szenario | Kosten | Bemerkung |
|---|---:|---|
| Nur lokal (4B-Lehrer + Schüler) | **2–5 €** | billigste Variante, 1–2 Tage |
| API-Lehrer 27B + Schüler lokal | **3–12 €** | schnellster guter Weg, 500k–1,5M Sätze |
| Alles in der Cloud | **5–15 $** | 4090/A100 für den ganzen Lauf |
| DeepSeek synthetisch + Schüler lokal | **10–30 €** | schwächer als echte Korpora |

Die Rechenkosten sind nicht das Problem. Ein Tag Arbeit am API-Mapping ist
teurer als jede der Zeilen.

## 8. Empfehlung

1. **Schüler lokal** auf der 9060 XT trainieren. Dafür ist die Karte da.
2. **Lehrer:** DeepInfra ist getestet — Prompt-Logprobs teils vorhanden,
   aber nur **1–2 `top_logprobs`** pro Position, also kein top-k-Lehrer.
   **Lokal `Qwen/Qwen3.5-4B-Base`** ist der getestete Base-Lehrer: 45,1 %
   Top-8 / 16,1 % Top-1, **~3,5 Sätze/s** mit `batch=16` + fp16-Softmax,
   150k Sätze ≈ **12 h**. API-Alternativen: Together AI (wieder verfügbar; Probe und
   Token-Test bereit) und Nebius Token Factory (`echo` + `logprobs`). Nicht den
   Unsloth-Gemma-3-4B-Spiegel nehmen: fp16-NaN, bf16 degeneriert.
   **Phase 1 ist positiv (28.10.):** deutsches `de_context.wmlm`, 10,86 MB,
   Glide 150k 74,15 → 77,40 (0,5/5,0), mit 441k Komposita **78,48/84,85**;
   Tippen +2,4–2,7 top-1. Ein großer Lehrer ist erst nach einem
   100-Satz-A/B sinnvoll; nächste lokale Hebel sind d320/8/1024 und
   500k Soft-Targets.
3. **Multi-Token-Mapping** ist implementiert (`patches/0005`); auf dem vollen
   Vokabular 12,8 % (Qwen2.5) bzw. 23,6 % (Qwen3.5) ganze Wörter, 100 % per
   Produktregel. Vor dem großen Lauf auf 100 Sätzen A/B messen.
4. **DeepSeek** nur für synthetische Chat-Sätze, falls der Register nach
   Tatoeba/OpenSubtitles noch fehlt.
5. **OpenCode Go** nicht für dieses Training verwenden.

## 9. Offene Punkte

- **DeepInfra-`echo`** ist gemessen: GPT-OSS-120B verweigert `echo`,
  Qwen3.8-Flash/Gemma/Mistral liefern Chat-Bodies, Qwen3.5-9B/Llama 3.1
  liefern Prompt-Logprobs, aber nur 1–2 `top_logprobs` pro Position. Damit
  kein Korpus-Lehrer; Details und API-Alternativen in
  [`wmlm-training-plan.md`](wmlm-training-plan.md) §1.6/§1.7.
- **Echte Abdeckung des finalen Vokabulars** ist auf Tatoeba+Leipzig gemessen:
  22.512 Wörter, Qwen2.5 12,8 % / Qwen3.5 23,6 % ganze Wörter (100 %
  Multi-Token). Für den finalen Lauf mit Wikipedia/OpenSubtitles neu ziehen.
- **Multi-Token-Mapping** ist implementiert (`patches/0005`) und auf 100
  Sätzen gemessen: +41 von 1.439 Zielen in die Top-8 (Qwen 0.5B), gezielt
  `hause` statt `haus`. Offen ist der Effekt auf Glide-top-1 und Perplexität
  des Schülers.
- **Lehrergröße:** Bringt 27B gegenüber 4B bei einem 12–19M-Schüler noch
  etwas? Der Capacity-Gap spricht für Sättigung; ein A/B mit derselben
  Datenmenge wäre der Test.
- **Latenz des 19M-Modells** auf einem Mittelklasse-Telefon; erst danach
  entscheiden, ob es ausgeliefert wird.
- **Gemma-Lizenz** und HF-Zugang; der Unsloth-Tokenizer ist nur ein
  Messbehelf, das Modell kommt aus dem offiziellen Repo. Der
  Unsloth-Modellspiegel ist in diesem Stack **nicht** brauchbar (fp16-NaN,
  bf16 degeneriert); getesteter lokaler Lehrer ist `Qwen/Qwen3.5-4B-Base`.

## 10. Quellen

Abruf 27.10.2026:

- ROCm Windows-Kompatibilität:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html>
- PyTorch-Installation unter Windows:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html>
- Windows-Limits („No ML training support“, Batch 1):
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/limitations/limitationsrad.html>
- WSL-Matrix und ROCDXG:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/wsl/wsl_compatibility.html>
  und <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/wsl/howto_wsl.html>
- librocdxg (inkl. `HSA_ENABLE_DXG_DETECTION`):
  <https://github.com/ROCm/librocdxg>
- DeepSeek-Preise:
  <https://api-docs.deepseek.com/quick_start/pricing>
- DeepInfra-Preise:
  <https://deepinfra.com/pricing>
- DeepInfra Logprobs:
  <https://docs.deepinfra.com/chat/log-probs>
- OpenCode Go:
  <https://opencode.ai/docs/go>

## 11. Reproduktion der Abdeckungszahlen

```bash
pip install tokenizers

curl -L https://huggingface.co/Qwen/Qwen2.5-3B/resolve/main/tokenizer.json -o qwen.json
# Gemma: Lizenz akzeptieren, dann tokenizer.json aus dem offiziellen Repo laden

unzip -p wmk-glide/data/wmk-glide-de-data.zip de_150k.txt > /tmp/de_150k.txt
python3 wmk-glide/tools/wmlm_token_coverage.py \
  --words /tmp/de_150k.txt --limit 24000 --counts \
  --tokenizer qwen.json gemma.json
```

Erwartete Ausgabe (Stand 27.10.2026):

```
24000 words from .../de_150k.txt
qwen                             types  20.1%  weighted  76.1%
gemma                            types  32.6%  weighted  86.6%
```

Für Englisch mit `app/dictionaries-src/en.txt` (17.306 Wörter, ohne
Frequenzspalte): 78,6 % (Qwen) und 91,2 % (Gemma).
