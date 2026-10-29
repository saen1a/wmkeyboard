# Deutsches `.wmlm`: Trainingsplan für diesen Rechner

Stand: 28.10.2026. Ergänzt [`wmlm-training-windows.md`](wmlm-training-windows.md)
(Hardware, Kosten, Rezept) und [`wmlm-gain.md`](wmlm-gain.md) (erwarteter
Gewinn). Alles hier mit **auf dieser Maschine gemessenen** Zahlen; Schätzungen
sind als solche markiert. Ziel: ein deutsches `de_context.wmlm`, das den
Glide-Blend erstmals auf einem deutschen Gerät aktiviert.

## 0. Kurzfassung

- **Die GPU läuft.** Ubuntu 24.04 unter WSL2, ROCm 7.2.1, librocdxg 1.2.0,
  PyTorch 2.9.1+rocm7.2.1: `torch.cuda.is_available() == True`,
  `AMD Radeon RX 9060 XT`, 15,9 GB VRAM, 69 TFLOP/s fp16 im 4096³-Matmul.
- **Bester lokaler Lehrer auf 16 GB: `Qwen/Qwen3.5-4B-Base`.** Öffentlich,
  kein Gate, 4B, 32 Layer, 248k Vokabular, ~8 GB fp16. Auf 100 deutschen
  Sätzen: **45,1 % Top-8 / 16,1 % Top-1** Lehrer-Treffer; ~1,5–1,7 Sätze/s
  mit `batch=16`, `ctx=40`. 150k Sätze ≈ **13 h**, 500k ≈ **42 h**.
- **`Qwen/Qwen3.5-4B` (Instruct) ist etwas schlechter** (44,3 / 15,5) und für
  rohe Fortsetzung das falsche Modell. **Gemma 3 4B über den Unsloth-Spiegel
  ist in diesem Stack unbrauchbar** (fp16 NaN, bf16 degenerierte Ausgabe); das
  offizielle, gated Modell ist ungetestet.
- **Größere deutsche Kandidaten geprüft (27.10.2026):**
  **Kolibri 1** (Aleph Alpha, 78B/3,46B MoE, Apache 2.0) hat den besten
  deutschen Tokenizer — **62,9 %** ganze Wörter im Modellvokabular statt
  23,6 % bei Qwen — ist aber **post-trained** (Reasoning) und braucht 156 GB
  BF16 (Scaleway: B300 nur als 8-GPU-Knoten, ~60 €/h). **Soofi S Base**
  (31,6B/3B, **Base**, deutsch-first, 63 GB → 1×H100) wäre der beste
  praktische Kandidat, ist aber **gated/Closed Beta** und lizenzrechtlich
  noch „other“. **Qwen3.8-Flash** ist **180B, post-trained** und teilt den
  248k-Qwen-Tokenizer (23,6 %); als DeepInfra-API billig, als Korpus-Lehrer
  nicht erste Wahl. Details und Entscheidungsbaum: §1.5 und §5.2a.
- **Reihenfolge:** zuerst **DeepInfra** (GPT-OSS-120B als Preis/Leistungs-
  Sieger, Qwen3.8-Flash als Qualitäts-Upgrade) und **lokal** Qwen3.5-4B-Base.
  **Scaleway nur**, wenn der 100-Satz-A/B eine Lücke zeigt, die ein deutscher
  Spezialist (Soofi/Kolibri) schließen muss. Kein GPU-Mietwagen auf Verdacht.
- **Der Multi-Token-Patch ist fertig und gemessen** (`patches/0005`): Auf dem
  vollen Vokabular (22.512 Wörter) mappt Qwen2.5 nur **12,8 %** ganze Wörter,
  Qwen3.5 **23,6 %**; die Produktregel erreicht **100 %**. Auf 100 Sätzen
  holt der Patch bei Qwen 0.5B **+41 von 1.439** Zielen in die Top-8
  (422 → 463), gezielt `hause` statt `haus`.
- **DeepInfra ist gemessen untauglich (27.10.2026).** GPT-OSS-120B
  verweigert `echo`; Qwen3.8-Flash/Gemma/Mistral liefern Chat-Bodies ohne
  `token_logprobs`; Qwen3.5-9B/Llama 3.1 liefern Prompt-Logprobs, aber nur
  **1–2 `top_logprobs`-Einträge** pro Position — keine Top-k-Verteilung.
  Der Probe (`tools/deepinfra_echo_probe.py`) markiert das als `FAIL`
  („too sparse“). **Nebius Token Factory** hat `echo` + `logprobs` und
  einen funktionierenden Signup (1 $ Startguthaben); der Probe liegt
  bereit (`tools/nebius_echo_probe.py`), der Key fehlt noch. Together-
  Signup funktioniert wieder (27.10.); Probe und Token-Test liegen bereit.
- **Phase 1 ist positiv (28.10.2026):** deutsches `de_context.wmlm`, 10,86 MB,
  Glide 150k 74,15 → **77,40** (0,5/5,0), mit 441k Komposita 75,70 → **78,48**;
  Tippen +2,4–2,7 top-1; heldout ppl 76,7. Gate erfüllt. Ein großer Lehrer
  erst nach einem 100-Satz-A/B (Qwen3.5-9B-Base auf L4, ~1 €); nächste lokale
  Hebel: d320/8/1024 und 500k Soft-Targets.

## 1. Ist-Stand

### 1.1 Gebaut und getestet

| Baustein | Zustand | Beleg |
|---|---|---|
| WSL-Trainingsdistro | Ubuntu 24.04.5, Kernel 6.18.33.1 | `wsl -l -v` |
| ROCm | 7.2.1 + librocdxg 1.2.0, `gfx1200` sichtbar | `rocminfo` |
| PyTorch | 2.9.1+rocm7.2.1, GPU-Matmul | 69,19 TFLOP/s fp16 |
| Korpus | Tatoeba DE + Leipzig News 2023 | 1.784.711 Sätze, 21,36M Tokens |
| `prep.py` | `vocab=24576 pieces=2048 ctx=40`, `seed_words=de_aosp` | 657.478 Typen, 84,58 % Token-Abdeckung |
| Trainingsdaten | `train.npz` 160 MB, `heldout` 20k Sätze / 431k Tokens | `out/de_lm_full` |
| Multi-Token-Mapping | Patch + `--self-test` grün | `patches/0005` |
| Lehrer Qwen3.5-4B-Base | 100 Sätze destilliert, fp16, keine NaNs | 45,1 / 16,1 |
| Schüler-Training | CPU und GPU End-to-End, Export, `lm_probe` | siehe §1.3 |
| DeepInfra-Probe | live getestet: Prompt-Logprobs teils da, `top_logprobs` nur 1–2 → **FAIL** | §1.6 |

### 1.2 Token-Abdeckung (gemessen, `tools/wmlm_token_coverage.py`)

| Wortliste | Tokenizer | ganze Wörter | frequenzgewichtet | Multi-Token |
|---|---|---:|---:|---:|
| `de_150k`, 24k Wörter | Qwen2.5 | 20,1 % | 76,1 % | 100 % |
| | Qwen3.5 | **30,7 %** | **87,2 %** | 100 % |
| | Gemma 3 | 32,6 % | 86,6 % | 100 % |
| volles Modell-Vokabular, 22.512 | Qwen2.5 | 12,8 % | – | 100 % |
| | Qwen3.5 | **23,6 %** | – | 100 % |

Die letzte Zeile ist die entscheidende: Ohne den Patch bekommen **76 % der
Wörter** im deutschen Modellvokabular kein Lehrer-Signal. Mit dem Patch
bekommen sie eines; die Produkte für 4+ Teile sind allerdings klein und
verrauscht.

### 1.3 Lehrer-Vergleich (100 Tatoeba-Sätze, dieselben Zeilen, `topk=24`)

| Lehrer | dtype | Top-8 | Top-1 | Multi-Token-Ziele in Top-8 | Durchsatz |
|---|---|---:|---:|---:|---:|
| Qwen2.5-0.5B | fp16 | 35,2 % | 9,8 % | 27 | ~4–7 Sätze/s |
| Qwen2.5-1.5B | fp16 | 42,2 % | 15,0 % | 50 | ~3 Sätze/s |
| Qwen2.5-3B | fp16 | 44,0 % | 14,7 % | 53 | ~1,9 Sätze/s |
| Qwen3.5-4B (Instruct) | bf16 | 44,3 % | 15,5 % | 59 | ~1,2 Sätze/s |
| **Qwen3.5-4B-Base** | **fp16** | **45,1 %** | **16,1 %** | **62** | **~1,5–1,7 Sätze/s** |
| Qwen3.5-4B-Base | bf16 | 44,8 % | 16,2 % | 62 | ~0,8 Sätze/s |
| Gemma 3 4B (Unsloth) | fp16/bf16 | unbrauchbar | – | – | – |

„Top-8“ heißt: das tatsächliche nächste Wort steht in den Lehrer-Top-8 über
dem Schüler-Vokabular. Das ist die Größe, die `distill.py` in `train.py`
füttert (`topk=24` im Produktivlauf, hier 8 gemessen).

### 1.4 Schüler-Durchsatz (d256/6/768, ctx 40)

| Gerät | Batch | Steps | Zeit | Hochrechnung 30k Steps |
|---|---:|---:|---:|---:|
| Ryzen 9 3900X (CPU) | 64 | 100 | 52 s | ~4,3 h |
| RX 9060 XT (ROCm) | 64 | 100 | 10 s | ~0,8 h |
| RX 9060 XT (ROCm) | 256 | 50 | ~25 s | ~4,2 h |

Batch 64 ist schnell, aber verrauschter; die ausgelieferte Rezeptur nimmt
größere Batches. Für den ersten Lauf: `batch=256`, `steps=30000`, das sind
~7,7M Satz-Präsentationen und ~4–5 h auf dieser Karte.

### 1.5 Größere deutsche Kandidaten (geprüft 27.10.2026)

Für diesen Zweck zählt nicht Chat-Qualität, sondern die **Nächste-Wort-
Verteilung auf rohem deutschem Text**. Deshalb: Base vor Instruct, deutscher
Tokenizer vor multilingual, und die Verteilung muss über dem 24k-Schüler-
Vokabular ausreichend ganze Wörter treffen.

| Modell | Params / aktiv | Stufe | Tokenizer, ganze Wörter (volles Vokabular) | Lizenz / Zugang | Serving | Urteil |
|---|---|---:|---|---|---|---|
| **Kolibri 1** (BF16) | 78B / 3,46B | post-trained (Reasoning) | **62,9 %** | Apache 2.0, offen | 156 GB BF16; 1×B300, 2×H200 oder 4×H100; FP8-Repo 78 GB, vLLM ungeprüft | bester Tokenizer, aber kein Base und teuer/schwer |
| **Soofi S Base** | 31,6B / 3B | **Base** | k. A. (gated) | „other“, gated Closed Beta; final permissiv angekündigt | 63 GB BF16, 1×H100 80 GB | bester praktischer Base-Kandidat, **wenn** Zugang |
| **Qwen3.5-9B-Base** | 9,65B | Base | 23,6 % | Apache 2.0, offen | 18 GB BF16, L4 24 GB / L40S | bester offener Cloud-Fallback |
| Qwen3.5-4B-Base | 4B | Base | 23,6 % | Apache 2.0, offen | 8 GB, lokal 16 GB | getestet, 45,1 / 16,1, ~13 h/150k |
| Qwen3.8-27B | 27,8B | post-trained | 23,6 % | Apache 2.0 | 56 GB BF16, 14 GB 4-bit | kein Base |
| Qwen3.8-Flash(-Next) | **180B** | post-trained | 23,6 % | Qwen Community License | 360 GB BF16; praktisch nur API | kein Base; API-Fallback |
| Llama3-German-8B | 8B | Base | 12,7 % | Llama | 16 GB | Tokenizer schlechter als Qwen3.5, Qualität unklar |
| LeoLM-7B | 7B | Base | 0 % (Tokenizer-Artefakt) | Llama | 14 GB | nicht weiterverfolgen |

Qwen3.5-9B-Base ist noch **nicht auf Lehrerqualität gemessen**; sein
Tokenizer ist byte-identisch mit Qwen3.5-4B (23,6 % ganze Wörter), die
Qualität dürfte über 4B liegen, der Sprung ist aber nicht belegt.

**Tokenizer-Messung** (`--multi`, dieselbe Methode wie §1.2): Kolibri trifft
auf `de_150k` **60,8 %** der Typen und **95,4 %** gewichtet ganz; Qwen3.5
30,7 / 87,2; Llama3-German 20,0 / 75,7. Auf dem vollen Modellvokabular:
Kolibri 62,9 %, Qwen3.5/Qwen3.8 23,6 %, Llama3-German 12,7 %. Das ist der
härteste Vorteil von Kolibri: 63 % der Wörter bekommen eine direkte
Ein-Token-Wahrscheinlichkeit statt eines Piece-Produkts.

**Aber:** Kolibri ist ein **post-trainedes Reasoning-Modell**, kein Base-
Modell; sein Roh-Text-Verhalten ist nicht garantiert. Das BF16-Repo hat
156 GB, das FP8-Repo 78 GB. Auf Scaleway gibt es B300 nur als **8-GPU-Knoten
für ca. 60 €/h**; eine H100 80 GB (ca. 3 €/h) reicht für Kolibri-BF16 nicht
und für das FP8-Repo nur mit vLLM-Glück. Ein Q4_K_M-GGUF (46,3 GB) passt auf
eine L40S 48 GB, aber Prompt-Logprobs über llama.cpp sind ungeprüft.

**Soofi S** ist die bessere Stufe (Base, deutsch-first, 63 GB → 1×H100), aber
die HF-Repos sind `gated: manual` und die Lizenz ist bis zur finalen
Veröffentlichung „other“. Ohne Zugang ist es keine Option.

**Qwen3.8-Flash** ist die falsche Klasse: Die offenen Gewichte
(`Qwen3.8-Flash-Next`) sind **180B**, post-trained, Vision-Sprache, und der
Tokenizer ist derselbe 248k-Qwen-Tokenizer (23,6 % ganze Wörter). Als
DeepInfra-API ist es billig (0,11/0,38 $ pro 1M Tokens), aber für rohe
Korpus-Fortsetzung nicht die erste Wahl. **Qwen3.8-27B** ist ebenfalls
post-trained; es gibt (Stand heute) kein offizielles `Qwen3.8-27B-Base`.

### 1.6 DeepInfra: Preis/Leistung (geprüft 27.10.2026)

**Bester deutscher Tokenizer (gemessen):** **Kolibri 1** — 62,9 % ganze
Wörter im Modellvokabular, 60,8 % Typen / **95,4 % gewichtet** auf `de_150k`.
Der Tokenizer von **German GPT-2** ist auf dem vollen Vokabular minimal
besser (64,0 %), gehört aber zu einem schwachen Modell; **Bloom-German**
58,0 %, **LLäMmlein** 43,7 %. Bei den modernen Lehrer-Modellen liegt
**GPT-OSS-120B** vorn (23,8 % / 88,1 %), knapp vor Qwen3.5/3.8
(23,6 % / 87,2 %) und Gemma 3 (23,1 % / 86,6 %).

150k Sätze ≈ **1,8M Input-Tokens** (12 Tokens/Satz). „Echo“ rechnet den
Prompt zusätzlich als Output ab; „normal“ nur ~0,2M Output. Alle Preise sind
$/1M Tokens, alle Modelle bei DeepInfra sind **post-trained** (kein Base).

| Modell | in/out | 150k echo | 150k normal | Tokenizer voll / de_150k gewichtet | Urteil |
|---|---:|---:|---:|---:|---|
| Mistral-Nemo-12B | 0,03/0,03 | 0,11 | 0,06 | 23,0 % / 84,4 % | billig, aber schwächer |
| Llama-3.1-8B | 0,02/0,04 | 0,11 | 0,04 | Llama-Tokenizer (nicht gemessen) | zu alt/schwach |
| **GPT-OSS-120B** | **0,04/0,17** | **0,38** | **0,11** | **23,8 % / 88,1 %** | **Preis/Leistungs-Sieger** |
| Gemma-3-27B | 0,08/0,16 | 0,43 | 0,18 | 23,1 % / 86,6 % | solide, aber kein Vorteil |
| DeepSeek-V4-Flash | 0,06/0,18 | 0,43 | 0,14 | 13,6 % / 75,4 % | deutscher Tokenizer schwach |
| Qwen3.5-9B | 0,10/0,15 | 0,45 | 0,21 | 23,6 % / 87,2 % | klein, aber günstig |
| Nemotron-3-Super-120B | 0,08/0,40 | 0,86 | 0,22 | gated, ungemessen | 120B, Tokenizer offen |
| **Qwen3.8-Flash** | **0,11/0,38** | **0,89** | **0,28** | **23,6 % / 87,2 %** | **Qualitäts-Upgrade** |
| Qwen3.5-35B-A3B | 0,14/1,00 | 2,05 | 0,45 | 23,6 % (Familie) | teurer Output |
| Qwen3.5-27B | 0,26/2,60 | 5,15 | 0,99 | 23,6 % (Familie) | teuer |
| Qwen3.8-27B | 0,20/2,50 | 4,86 | 0,86 | 23,6 % (Familie) | teuer |

**Preis/Leistung:** **GPT-OSS-120B** ist der klare Sieger — 120B MoE für
**0,38 $** pro 150k Sätze im Echo-Worst-Case, Tokenizer auf Qwen3.5-Niveau.
**Qwen3.8-Flash** ist das Qualitäts-Upgrade (180B) für **0,89 $**; immer noch
im Cent-Bereich. **Gemma 3 27B** ist ähnlich teuer wie GPT-OSS, aber kleiner
und mit schlechterem Tokenizer. **DeepSeek V4 Flash** und **Phi-4** fallen
wegen des deutschen Tokenizers raus (13,6 % / 12,6 % ganze Wörter).
**Mistral Nemo** ist die billigste brauchbare Option, aber 12B.

**Messung 27.10.2026 (Key vorhanden):** DeepInfra ist als Korpus-Lehrer
**unbrauchbar**:

- `openai/gpt-oss-120b` → HTTP 400 `"echo is not supported for this model"`.
- `Qwen/Qwen3.8-Flash`, `google/gemma-3-27b-it`,
  `mistralai/Mistral-Nemo-Instruct-2407` → Chat-Body ohne
  `token_logprobs`.
- `Qwen/Qwen3.5-9B` und `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo` →
  Legacy-Shape mit Prompt-Logprobs, aber **nur 1–2 `top_logprobs`-Einträge
  pro Position**, auch bei `logprobs=100/200`. Das ist der gewählte Token,
  keine Top-k-Verteilung; für `distill.py` (topk=24) unbrauchbar.

Der Probe markiert das jetzt als `FAIL` („top_logprobs too sparse“). Die
Preistabelle oben bleibt als Referenz, falls ein anderer Anbieter/Endpunkt
die volle Verteilung liefert; DeepInfra selbst fällt für dieses Rezept aus.
**Damit bleiben lokal (Qwen3.5-4B-Base), Scaleway (Qwen3.5-9B-Base / Soofi)
oder Together (unten) als Wege.**

### 1.7 API-Alternativen zu DeepInfra (geprüft 27.10.2026)

DeepInfra fällt aus (nur 1–2 `top_logprobs`). Andere Anbieter:

| Anbieter | Prompt-Logprobs | Top-N | Modelle | Preis / 150k (echo) | Urteil |
|---|---|---|---:|---|---:|
| **Nebius Token Factory** | ja (`echo` + `logprobs`), OpenAPI | **20?** | Qwen3-30B-A3B, Qwen3-235B, Qwen3.5-397B, Qwen3.8-27B | **0,72 / 1,44 / 7,56 $** | **zweite API-Wahl; Signup + 1 $ frei** |
| **Scaleway GPU** (`distill.py` oder vLLM) | ja (`distill.py`: volle Softmax; vLLM: `prompt_logprobs`) | **voll / 100** | Qwen3.5-9B-Base, Soofi, Kolibri | ~1–3 € (L4/H100) | **zuverlässigster Weg** |
| ACS Infra | ja (`prompt_logprobs: -1`) | **voll** | Llama-8B, Llama-405B, Trinity | unbekannt, Approval | Base-API, aber kein deutsches Modell |
| Together AI | ja, dokumentiert | 20 | Qwen3.5-9B, Qwen3.8-Flash, GPT-OSS | 0,76–1,35 $ | **erste API-Wahl; Probe/Token-Test bereit** |
| Fireworks | ja (`echo`) | **5** | Qwen, Llama, GPT-OSS | wenige $ | zu sparse |
| OpenAI | ja (`echo`) | **5** | GPT-4.1/5 | teuer | zu sparse |
| Novita | ja (`echo`) | **5** | Qwen/DeepSeek | wenige $ | zu sparse |
| Hyperbolic/Featherless | unklar | ? | Qwen/Llama, Base-Modelle | wenige $ | ungeprüft |

**Nebius-Details:** `/v1/completions` hat `echo` und `logprobs` (OpenAPI
`CompletionRequest`); ein `prompt_logprobs`-Feld gibt es nicht, es ist die
vLLM-Legacy-Form. Ob `top_logprobs` pro Prompt-Position wirklich 20
Alternativen liefert, muss der Probe zeigen (DeepInfra hatte dieselbe Form,
aber nur 1–2 Einträge). Preise und Tokenizer:

| Nebius-Modell | in/out | 150k echo / normal | Tokenizer voll / de_150k gewichtet |
|---|---:|---:|---:|
| Qwen3-30B-A3B-Instruct | 0,10/0,30 | 0,72 / 0,24 $ | 12,8 % / 76,1 % |
| Qwen3-235B-A22B-Instruct | 0,20/0,60 | 1,44 / 0,48 $ | 12,8 % / 76,1 % |
| **Qwen3.5-397B-A17B** | **0,60/3,60** | **7,56 / 1,44 $** | **23,6 % / 87,2 %** |
| Qwen3.8-27B | 0,45/3,00 | 6,21 / 0,99 $ | 23,6 % / 87,2 % |

Signup: `https://tokenfactory.nebius.com/`, Key als `NEBIUS_API_KEY`,
**1 $ Startguthaben**. Probe:
[`tools/nebius_echo_probe.py`](tools/nebius_echo_probe.py). Teste zuerst
**Qwen3-30B-A3B** (billig) und **Qwen3.5-397B** (Qualität/Tokenizer).
`PASS` nur bei ≥10 Alternativen pro Prompt-Position; dann Schüler-`topk`
auf 20 oder 16. Qwen3-30B/235B haben den schlechten Qwen3-Tokenizer
(12,8 %); Qwen3.5-397B hat den guten Qwen3.5-Tokenizer (23,6 %) und ist
trotz 397B für < 8 $ zu haben.

**Together (wieder verfügbar):** `echo: true` + `logprobs: N` (0–20)
liefert die Prompt-Logprobs inklusive `top_logprobs`; das ist die gesuchte
Verteilung. Der Signup funktioniert wieder (27.10.).
Preise: Qwen3.5-9B 0,17/0,25 $, Qwen3.8-Flash 0,15/0,47 $, GPT-OSS-120B
0,15/0,60 $ pro 1M. 150k Sätze (1,8M Tokens) kosten im Echo-Worst-Case
**0,76 / 1,12 / 1,35 $**, normal **0,36 / 0,36 / 0,39 $**. Together hat
**kein** Base-Qwen im Serverless-Katalog; die Modelle sind post-trained.
Wegen `logprobs <= 20` den Schüler auf `topk=20` (oder 16) setzen.
Der Probe liegt als [`tools/together_echo_probe.py`](tools/together_echo_probe.py)
bereit: `TOGETHER_API_KEY=... python3 tools/together_echo_probe.py
--model Qwen/Qwen3.5-9B`. `PASS` nur, wenn mindestens 10 Alternativen pro
Prompt-Position zurückkommen. Danach
[`tools/together_token_test.py`](tools/together_token_test.py) auf 100
Sätzen aus `out/de_lm` (Top-1/Top-8 des echten nächsten Lehrer-Tokens);
erst bei brauchbarem Ergebnis wird `distill_api.py` gebaut. Der Test ist
read-only und braucht nur den Key.

```powershell
# Probe (Windows oder WSL), Key außerhalb des Repos
python wmk-glide\tools\together_echo_probe.py --key-file C:\Users\saenta\.together.key --model Qwen/Qwen3.5-9B
# Token-Test in WSL (numpy/venv)
wsl -d Ubuntu-24.04 -u root -e bash -lc 'cd /root/wmlm-de; /opt/wmlm-venv/bin/python tools/wmlm/together_token_test.py --key-file /mnt/c/Users/saenta/.together.key --data-dir out/de_lm --model Qwen/Qwen3.5-9B --sentences 100'
```

Der Token-Test misst **Lehrer-Token-Top-8**, nicht die 45,1 der lokalen 4B
(Schüler-Vokabular-Top-8). Erst `distill_api.py` liefert den vergleichbaren
A/B; der Token-Test entscheidet nur, ob Together überhaupt eine brauchbare
Verteilung liefert.

**Scaleway-Details:** Für einen einzelnen Lauf braucht es **kein vLLM** —
`distill.py` läuft auf der Instanz genauso wie lokal und hat die volle
Softmax. Auf einer **L4-1-24G (0,79 €/h)** läuft Qwen3.5-9B-Base (18 GB
BF16), auf einer **H100-1-80G (~3 €/h)** Soofi (63 GB) oder Qwen3.5-9B mit
Reserve. vLLM (`prompt_logprobs` top-100/voll) nur, wenn ein HTTP-Endpunkt
für mehrere Clients gebraucht wird. Das ist der einzige Weg zu einem
**deutschen Base-Modell** mit voller Verteilung.

**ACS Infra** ist konzeptionell ideal (Base-Modelle, `prompt_logprobs: -1`,
volle Verteilung), aber Zugang nur nach Admin-Freigabe und die Modelle sind
Llama-8B/405B/Trinity — deutscher Tokenizer schwach (Llama 12,7 % ganze
Wörter). Als Forschungsoption merken, nicht als Default.

## 2. Gates

Jedes Gate hat ein hartes Kriterium; bei Rot wird nicht weitergerechnet.

| Gate | Frage | Kriterium | Status |
|---|---|---|---|
| **G0** | Läuft die GPU? | `rocminfo` zeigt `gfx1200`; `torch.cuda.is_available()`; Matmul ohne NaN | **grün** |
| **G1** | Ist DeepInfra ein Korpus-Lehrer? | Probe Exit 0, `verdict=PASS`, Prompt-Logprobs **und** ≥10 `top_logprobs` pro Position | **rot (gemessen): 1–2 Einträge** |
| **G2** | Trägt Multi-Token? | `--self-test` grün; gezielter Fall `hause` > `haus`; Top-8-Gewinn > 0 | **grün** |
| **G3** | Ist der Korpus sauber? | 1–3M Sätze, Register Chat/News, 20k Held-out, Abdeckung > 80 % | **grün** (Tatoeba+News) |
| **G4** | Lehrer-Pass | 150k Sätze ohne NaN, Ausgabe plausibel, Kosten/Zeit im Rahmen | offen |
| **G5** | Schüler | `train.py` konvergiert, `heldout`-Loss fällt, Export lesbar | offen |
| **G6** | Gewinn auf dem Gerät | Glide-Top-1 auf gehaltenem Split ≥ **+2,0** gegen 74,15 | offen |
| **G7** | Veröffentlichung | `data/de/de_context.wmlm` + Katalogeintrag, Lizenz/Attribution | offen |

G6 ist bewusst konservativ: Die Schätzung ist +3 bis +5
([`wmlm-gain.md`](wmlm-gain.md:53)); unter +2 ist das Modell den Download
nicht wert. Der in-sample-Wert 80,82 (`state.md:174`) ist **kein** Kriterium.

## 3. Umgebung: was auf dieser Maschine steht

### 3.1 Host

| | |
|---|---|
| CPU | Ryzen 9 3900X, 12 Kerne / 24 Threads |
| RAM | 31,9 GB |
| GPU | RX 9060 XT, 15,9 GB VRAM, Treiber 32.0.32015.7029 (Adrenalin 26.10.1) |
| WSL | 2.7.8, Kernel 6.18.33.1, `.wslconfig` 24 GB / 8 GB Swap / 16 CPUs, `vmIdleTimeout=-1`, `instanceIdleTimeout=-1` |
| Distros | Ubuntu 26.04 (Daten/CPU-Prep), **Ubuntu 24.04 (Training, getestet)** |
| Disk | 873 GB frei in WSL |

`/dev/dxg` existiert; `dmesg` zeigt `dxgkio_query_adapter_info: Ioctl
failed: -22`. Das ist auf dieser Maschine **harmlos**: `rocminfo` und PyTorch
sehen die GPU. Nicht als Fehler jagen.

Für den Overnight-Lauf: Windows-Standby aus
(`powercfg /change standby-timeout-ac 0`, `hibernate-timeout-ac 0`), sonst
pausiert die WSL-VM. Verifiziert 27.10.: **nur S3**, kein Modern Standby
(S0); `STANDBYIDLE`/`HIBERNATEIDLE` AC+DC = 0, `UNATTENDSLEEP` = 0. Damit
kann die **Bildschirmsperre** keinen Sleep auslösen; der Monitor geht nach
15 min aus (`VIDEOIDLE`), die WSL-Instanz läuft weiter. Unterbrechen kann
nur ein anderes Energieschema, ein Windows-Update-Neustart oder manuelles
Herunterfahren. Nach `out/teacher_150k.DONE` den Dienst mit
`systemctl disable --now wmlm-teacher` abschalten, damit er nicht bei jedem
WSL-Boot erneut merged.

### 3.2 ROCm-Stack (24.04, reproduzierbar)

```powershell
# einmalig auf dem Host; "--no-launch" vermeidet den interaktiven Benutzer-Dialog
wsl --install -d Ubuntu-24.04 --no-launch
```

```bash
# als root in Ubuntu-24.04
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y wget gnupg2 ca-certificates curl python3.12-venv python3-pip
wget -qO- https://repo.radeon.com/rocm/rocm.gpg.key \
  | gpg --dearmor -o /etc/apt/keyrings/rocm.gpg
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] \
  https://repo.radeon.com/rocm/apt/7.2.1 noble main" \
  > /etc/apt/sources.list.d/rocm.list
apt-get update
apt-get install -y rocminfo=1.0.0.70201-81~24.04 \
  rocm-hip-runtime=7.2.1.70201-81~24.04

# librocdxg 1.2.0 (ROCm 7.2.x)
curl -sSL -o /tmp/rocdxg.deb \
  https://github.com/ROCm/librocdxg/releases/download/v1.2.0/rocdxg-roct_1.2.0_amd64.deb
dpkg -i /tmp/rocdxg.deb

# Bibliotheken, die der Torch-Wheel erwartet
apt-get install -y roctracer rocprofiler-sdk-roctx \
  miopen-hip rocblas hipblas hipblaslt hipsparselt \
  rocfft hipfft rocsolver hipsolver rccl rocrand hiprand rocsparse hipsparse
ldconfig
```

PyTorch (Python 3.12, cp312):

```bash
python3.12 -m venv /opt/wmlm-venv
/opt/wmlm-venv/bin/pip install --no-cache-dir \
  "https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.1/triton-3.5.1%2Brocm7.2.1.gita272dfa8-cp312-cp312-linux_x86_64.whl"
/opt/wmlm-venv/bin/pip install --no-cache-dir \
  "https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.1/torch-2.9.1%2Brocm7.2.1.lw.gitff65f5bc-cp312-cp312-linux_x86_64.whl" \
  "https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.1/torchvision-0.24.0%2Brocm7.2.1.gitb919bd0c-cp312-cp312-linux_x86_64.whl"
/opt/wmlm-venv/bin/pip install numpy transformers
```

Immer setzen:

```bash
export HSA_ENABLE_DXG_DETECTION=1          # ROCm 7.2.x; ab 7.13 nicht nötig
export LD_LIBRARY_PATH=/opt/rocm-7.2.1/lib
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export HF_HOME=$HOME/hf-cache
```

Prüfung:

```bash
rocminfo | grep -E "Name:.*gfx|Marketing Name"
/opt/wmlm-venv/bin/python -c \
  "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Erwartet: `gfx1200`, `AMD Radeon RX 9060 XT`, `True`.

**26.04:** Der ROCm-Kompatibilitätsmatrix nennt inzwischen auch 26.04, aber
ROCm 7.2.1 ist ein
oble`-Repo. Wer bei 26.04 bleibt, nimmt ROCm 7.14 +
librocdxg 1.2.1. Für Reproduzierbarkeit ist 24.04 + 7.2.1 der getestete Weg.

## 4. Daten

### 4.1 Quellen

| Quelle | Datei | Größe | Sätze | Register |
|---|---|---:|---:|---|
| Tatoeba DE | `deu_sentences.tsv.bz2` | 12,1 MB | 784.711 | casual/chat |
| Leipzig News 2023 | `deu_news_2023_1M.tar.gz` | 219 MB | 1.000.000 | formal/other |
| Leipzig Wikipedia 2021 (optional) | `deu_wikipedia_2021_1M.tar.gz` | ~200 MB | 1.000.000 | formal/other |
| OpenSubtitles DE (optional) | `lines:opensub_de.txt:1:1` | ~? | ~1M | casual/chat |

Der getestete Korpus ist Tatoeba + News: **1.784.711 Sätze, 21.356.951
Tokens, 657.478 Typen**. `prep.py` lief in 58 s; `train.npz` ist 160 MB,
`heldout` 20k Sätze / 431k Tokens.

Lizenzen: Tatoeba CC BY 2.0 FR / CC0; Leipzig und OpenSubtitles eigene
Bedingungen; `de_aosp` Apache-2.0; FUTO MIT. Attribution ins Datenrepo.

### 4.2 Aufbau

```bash
cd ~/wmlm-de
python3 tools/wmlm/corpus.py --lang=1 tatoeba:corpora/deu_sentences.tsv.bz2 \
  > corpora/de_sentences.tsv
python3 tools/wmlm/corpus.py --lang=1 leipzig:corpora/deu_news_2023_1M.tar.gz \
  > corpora/de_news.tsv
cat corpora/de_sentences.tsv corpora/de_news.tsv > corpora/de_all.tsv
```

Vor dem Prep: Duplikate entfernen, sehr kurze Sätze (< 3 Wörter) und
Überlängen filtern. `prep.py` schneidet auf `ctx=40`; Sätze, die länger sind,
verlieren das Ende, was für den Kontext okay ist, aber für das Zielwort am
Satzende schlecht. Ein Filter auf ≤ 40 Wörter ist sauberer.

```bash
python3 tools/wmlm/prep.py corpora/de_all.tsv out/de_lm_full \
  vocab=24576 pieces=2048 ctx=40 seed_words=data/de_aosp.txt heldout=20000
```

`seed_words` ist die Tastatur-eigene Liste (`de_aosp`, 205.888 Wörter), nicht
`de_150k`. Das ist der Vertrag mit dem Strip: das Modell soll eine Meinung zu
den Wörtern haben, die die App anbietet.

**Vokabular-Abwägung:** `pieces=2048` kostet 2.048 Wortslots. Die App spelt
Pieces nur in `gateView`/`revise`, **nicht** in `scores()`; der Glide-Blend
sieht ein Wort außerhalb des Vokabulars als NaN und bewegt es nicht
(`ContextModel.kt`, `scores`). Für den Glide-Hebel zählt also das Wort, nicht
das Piece. Ablation für den ersten Lauf: `vocab=32768 pieces=2048` (≈12,9 MB)
gegen `24576/2048` (≈10,8 MB); mehr Wörter heißt mehr direkt bewertbare
Kandidaten.

## 5. Rezept

### 5.1 Lehrer

**Lokal (getestet):** Voraussetzung ist
`git apply /path/to/wmk-glide/patches/0005-distill-multitoken.patch` gegen
`tools/wmlm/distill.py` (der Patch fügt `multi=`, `dtype=`, `trust=` und
`--self-test` hinzu).

```bash
cd ~/wmlm-de
python3 tools/wmlm/distill.py out/de_lm_full out/de_soft.npz \
  teacher=Qwen/Qwen3.5-4B-Base \
  sentences=150000 topk=24 batch=16 device=cuda multi=1 dtype=float16
```

- `dtype=float16` ist auf dieser Karte ~1,5× schneller als bf16 und
  produziert keine NaNs. bf16 ist der Fallback.
- `batch=16` passt sicher; `batch=32` ist möglich, aber nicht gemessen.
- `topk=24` wie im englischen Rezept; `multi=1` ist der Patch.
- **Speicher:** `batch=16` und Softmax im Modell-dtype (fp16) fahren. Ein
  float32-`softmax` über `[batch, tokens, 248k]` treibt die 16-GB-Karte bei
  `batch=32` in Unified-Memory-Thrashing (gemessen: nur 1 GB frei, Fortschritt
  praktisch stehen). Mit `batch=16` + fp16-Softmax: 3 GB frei, 3,3 Sätze/s (steady state).
- **Chunking:** `distill.py` hat jetzt `start=`/`count=`; 30×5k-Chunks,
  `merge_soft.py` sticht sie zusammen. Fertige Chunks bleiben bei einem
  Abbruch erhalten; ein fehlender Chunk wird einzeln wiederholt.
- **Overnight:** `run_teacher_chunks.sh` läuft als
  `wmlm-teacher.service` (enabled, `Restart=on-failure`), prüft jeden Chunk
  mit `check_soft.py`, merged atomar und setzt `DONE` + SHA256. WSL:
  `vmIdleTimeout=-1` und `instanceIdleTimeout=-1`, sonst beendet die VM den
  Dienst nach ~60 s ohne Shell.
- `Qwen3.5-4B-Base` ist ein Hybrid-Attention-Modell; ohne
  `causal-conv1d`/`flash-linear-attention` laufen Referenz-Kernel
  (Warnung). Nicht zwingend installieren; die ROCm-Builds sind ungeprüft.

**API (Gate G1):** **Ergebnis 27.10.2026: FAIL** — Prompt-Logprobs
teilweise vorhanden, aber `top_logprobs` nur 1–2 Einträge; keine Top-k-
Verteilung. Der folgende Block bleibt als Regressionscheck, falls DeepInfra
oder ein anderer Anbieter die Verteilung später freischaltet.

Den Key **nicht in den Chat schreiben**. Als Benutzer-Umgebungsvariable
setzen, dann in einer neuen Shell:

```powershell
setx DEEPINFRA_API_KEY "..."
# neue Shell:
python wmk-glide\tools\deepinfra_echo_probe.py --model Qwen/Qwen3.8-Flash
# oder ohne Env-Var, Key in einer Datei außerhalb des Repos:
python wmk-glide\tools\deepinfra_echo_probe.py --key-file C:\Users\saenta\.deepinfra.key
```

Kandidaten für den Probe (27.10.2026 in der DeepInfra-Liste geprüft):
**`openai/gpt-oss-120b`** (Preis/Leistung: 0,04/0,17 $ pro 1M),
**`Qwen/Qwen3.8-Flash`** (Qualität: 1M ctx, 0,11/0,38 $ pro 1M),
`google/gemma-3-27b-it`, `Qwen/Qwen3.5-27B`. DeepInfra hat **kein** Kolibri,
**kein** Soofi und **kein** Base-Qwen; alle dortigen Lehrer sind post-trained.
Wenn `echo` Prompt-Logprobs liefert, ist GPT-OSS-120B der billigste starke
Lehrer, Qwen3.8-Flash der Qualitäts-Upgrade — beide kein Base-Modell.

Der Probe schickt genau eine Anfrage:

```http
POST https://api.deepinfra.com/v1/openai/completions
Authorization: Bearer $DEEPINFRA_API_KEY
Content-Type: application/json

{"model":"Qwen/Qwen3.8-Flash",
 "prompt":"Ich will nach Hause gehen und morgen",
 "max_tokens":1,"temperature":0,
 "echo":true,"logprobs":5,"return_tokens_as_token_ids":true}
```

Geprüft wird die Antwort, nicht der Ruf:

- `usage.prompt_tokens` vorhanden (sonst ist die Prompt-Grenze nicht bestimmbar),
- `choices[0].logprobs.tokens` mindestens so lang wie `prompt_tokens`,
- die ersten `prompt_tokens` Einträge von `token_logprobs` sind **nicht null**,
- `top_logprobs` sind für diese Positionen gefüllt,
- `choices[0].text` beginnt mit dem Prompt (Echo),
- Ausgabe `verdict: PASS` und Exit 0.

Nur dann taugt DeepInfra als Korpus-Lehrer. `FAIL`/`PARTIAL` heißt: die Docs
meinen „Logprobs für generierte Tokens“, nicht für den Prompt. Ohne Key
antwortet der Endpunkt mit **401** (auf dieser Maschine geprüft); der
`--self-test` und `--dry-run` laufen ohne Key und ohne Netz.

- `PASS` nur, wenn `prompt_logprobs_present == prompt_tokens` und
  `verdict == PASS`.
- Bei `FAIL`/`PARTIAL`: DeepInfra ist **kein** Korpus-Lehrer (die Docs
  versprechen Logprobs nur für generierte Tokens). Dann lokal bleiben oder
  einen anderen Anbieter prüfen.
- DeepInfra hostet `gemma-3-27b-it`, nicht das Base-`-pt`; für rohe
  Fortsetzung ist ein Instruct-Modell ein Kompromiss. Der lokale
  Qwen3.5-Base ist sauberer, nur langsamer.
- Kosten bei 150k Sätzen (~1,8M Tokens): **< 1 $**; bei 500k (~6M Tokens):
  **1–2 $** (0,08 $/M Input, 0,16 $/M Output, je nach `echo`-Abrechnung).

### 5.1a Scaleway (nur falls der API/lokale A/B eine Lücke zeigt)

**Nicht als erster Schritt.** Erst DeepInfra + lokal messen; Scaleway ist die
Eskalation für einen deutsch-spezialisierten Lehrer, nicht der Default.

Ziel: dieselben 100 Sätze, dasselbe Schüler-Vokabular, dieselbe Messung wie
§1.3. Nur so ist der Vergleich mit Qwen3.5-4B-Base (45,1 / 16,1) belastbar.

| Kandidat | Instanz | VRAM | Kosten | Weg |
|---|---|---|---:|---|
| Soofi S Base (wenn Zugang) | H100-1-80G | 63 GB BF16 | ~3 €/h | `trust=1`, `dtype=bfloat16` |
| Qwen3.5-9B-Base | L4-1-24G | 18 GB BF16 | ~0,8 €/h | Standard, `trust=0` |
| Kolibri 1 FP8 | H100-1-80G | 78 GB FP8 | ~3 €/h | vLLM/FP8-Support ungeprüft |
| Kolibri 1 BF16 | B300-SXM-8 (nur 8 GPUs) | 156 GB | ~60 €/h | für einen Test overkill |
| Kolibri 1 Q4_K_M | L40S-1-48G | 46,3 GB | ~1,7 €/h | llama.cpp, Prompt-Logprobs ungeprüft |

Setup (Scaleway GPU OS 12 = Ubuntu 24.04 + NVIDIA-Treiber + Docker):

```bash
python3 -m venv ~/wmlm
~/wmlm/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128
~/wmlm/bin/pip install transformers sentencepiece accelerate huggingface_hub
export HF_HOME=$HOME/hf-cache
# gated (Soofi): HF_TOKEN mit freigeschaltetem Lesezugriff
hf download Soofi-Project/Soofi-S-Base
```

Lauf:

```bash
python tools/wmlm/distill.py out/de_lm_full out/soft_cloud100.npz \
  teacher=Soofi-Project/Soofi-S-Base sentences=100 topk=24 batch=8 \
  device=cuda multi=1 dtype=bfloat16 trust=1
```

Für Qwen3.5-9B-Base: `teacher=Qwen/Qwen3.5-9B-Base trust=0 batch=16`.
Auswertung mit demselben Skript wie in §1.3 (Top-8/Top-1 über dem
Schüler-Vokabular, `topk=24`).

**Entscheidung:** Der Cloud-Lehrer muss Qwen3.5-4B-Base um **mindestens
+3 Punkte Top-8** schlagen, sonst lohnt der Mehraufwand nicht. Bei +1 bis +3
ist der Unterschied im Rauschen der 100 Sätze; dann 300 Sätze messen. Unter
+1: lokal bleiben.

Kosten: 100 Sätze + Modell-Download sind < 1 GPU-Stunde; H100 ≈ 3 €,
L4 ≈ 0,8 €, L40S ≈ 1,7 €. Ein 150k-Lauf mit Soofi auf H100 ist ~1–2 h
(≈ 5–10 €), mit Qwen3.5-9B auf L4 ~1–2 h (≈ 2 €).

### 5.2 Schüler

```bash
python3 tools/wmlm/train.py out/de_lm_full out/de_run \
  steps=30000 batch=256 d=256 layers=6 heads=4 ff=768 ctx=40 \
  distill=out/de_soft.npz distill_alpha=0.5 distill_share=0.5
```

- ~4–5 h auf der RX 9060 XT (batch 256), ~0,8 h bei batch 64 (verrauschter).
- `train.py` hat keine Gradient-Akkumulation; batch 256 ist der Kompromiss.
- Variante für mehr Qualität: `d=320 layers=8 ff=1024` (~19M Parameter,
  ~20 MB int8); `lm.rs` liest die Formen aus dem Header, keine Engine-Änderung.
  Ob das Telefon schnell genug ist, muss gemessen werden.

### 5.3 Export

```bash
python3 tools/wmlm/export.py out/de_run/best.pt out/de_lm_full/vocab.txt \
  out/de_context.wmlm --langs=de --name=German
./src/wm-engine/target/release/examples/lm_probe out/de_context.wmlm \
  "ich will nach" hause berlin
```

Erwartet: Header `langs ["de"]`, `vocab 24576`, `ctx 40`, `d 256`, `layers 6`;
`lm_probe` liefert plausible nächste Wörter und eine Zeit pro Kontext.

## 6. Messung

### 6.1 Vor dem Gerät

1. **`lm_probe`** auf 20 Kontexten: Header, Top-10, `P(w)` für Zielwörter,
   Zeit pro Wort. Auf dem Desktop-CPU war der englische 10,8-MB-Modellaufruf
   ~2–4 ms pro zusätzlichem Wort; das Telefon ist langsamer.
2. **`typing_eval`** auf `out/de_lm_full/heldout.tsv`, mit und ohne Modell:
   Next-Word Top-1/Top-3, Strip-Top-1 (careful/fast/sloppy), Autocorrect-
   Precision/Recall, neu umgeschriebene Wörter. Der Pack (`de_bigrams`,
   `de_trigrams`) bleibt drin: `lm+pack`, nicht `lm` statt `pack`.
3. **Glide-Harness** aus `experiments/glide_lm_blend_eval.rs` mit
   `de_swipes.jsonl`, `german.json`, `de_150k.txt` (+ Komposita-Liste) und
   `de_context.wmlm`. Der Harness ist sprachunabhängig; er lädt das Modell
   und fährt den echten Blend. Deutsches Profil:
   `COLS=11 FREQ=0.5 GAP=2.0`; am 28.10. gemessen: **0,5/5,0 = 78,48/84,85**
   mit Komposita, `0,7/3,0 = 77,28/84,81`. Der frühere 71,17-Wert war
   Default-Tuning ohne `FREQ`/`GAP`.
4. **Fairer Split:** 20 % der Sätze per SHA-256 als Held-out; das LM nur auf
   den anderen 80 % trainieren. Die 80,82 aus `state.md:174` sind in-sample
   und dürfen nicht als Gerätegewinn zitiert werden
   (`experiments-followup.md:10-28`).

### 6.2 Abnahme

| Messung | Baseline | Ziel |
|---|---:|---:|
| Glide Top-1, gehaltener Split, deutsches Profil | 74,15 | **≥ 76,2** (+2) |
| Glide Top-4 | 82,81 | ≥ 83,8 |
| Glide Top-1 mit Komposita-Liste | 75,70 | ≥ 77,7 |
| Next-Word Top-1 (typing_eval) | ohne Modell | +3 bis +5 Punkte |
| Modellgröße | – | ≤ 13 MB |
| Latenz pro Wort auf dem Telefon | – | < 10 ms (Ziel) |

**Ergebnis Phase 1 (28.10.2026, lokal):** Glide 150k **74,15 → 77,40**
(0,5/5,0; 76,35 bei 0,7/3,0), mit 441k Komposita **75,70 → 78,48**
(77,28 bei 0,7/3,0), top-4 **84,85**; Tippen +2,67 (300 Fälle, 0,2/1,0)
bzw. +2,40 (500 Fälle, 0,5/5,0) — knapp unter dem +3–5-Ziel, aber positiv; Modell **10.856.432 Bytes**, heldout ppl
**76,7**. Gate erfüllt; Details `state.md` §2.7. Die Baseline 74,15 gilt nur
mit `COLS=11 FREQ=0.5 GAP=2.0`; der Harness hat dafür jetzt `FREQ`/`GAP`
(Default 0,5/2,0). Der frühere 71,17-Wert war Default-Tuning.
Die Latenz auf dem Telefon ist noch nicht gemessen.

Wenn G6 rot ist: nicht veröffentlichen; zuerst Lehrer/`topk`/`distill_alpha`
und Vokabular-Ablation prüfen. Der englische Proxy zeigt, dass der Mechanismus
trägt (+4,9); ein deutsches Modell, das < +1 bringt, hat ein Daten- oder
Mapping-Problem, keine Mechanik-Frage.

## 7. Zeit und Kosten

| Szenario | Lehrer | Schüler | Gesamt | Kosten |
|---|---|---|---|---:|
| Lokal, 150k Sätze, Qwen3.5-4B-Base (Phase 1, 30×5k) | ~13 h | 4–5 h | **~18 h** | 3–4 € Strom |
| Lokal, 500k Sätze | ~42 h | 4–5 h | **~2 Tage** | 8–12 € Strom |
| DeepInfra (GPT-OSS/Qwen3.8) | **entfällt** | **entfällt** | – | **keine Top-k-Verteilung** |
| Nebius Qwen3-30B-A3B, 150k | 1–2 h | 4–5 h | **< 1 Tag** | 0,24–0,72 $ |
| Nebius Qwen3.5-397B, 150k | 1–2 h | 4–5 h | **< 1 Tag** | 1,44–7,56 $ |
| Together Qwen3.5-9B, 150k | 1–2 h | 4–5 h | **< 1 Tag** | 0,36–0,76 $ |
| Together Qwen3.8-Flash, 150k | 1–2 h | 4–5 h | **< 1 Tag** | 0,36–1,12 $ |
| Together GPT-OSS-120B, 150k | 1–2 h | 4–5 h | **< 1 Tag** | 0,39–1,35 $ |
| Cloud-GPU 4090, 150k | 6–8 h | 2 h | **~1 Tag** | 4–8 $ |
| Scaleway L4, Qwen3.5-9B, 150k | 1–2 h | 4–5 h | **~1 Tag** | 2–4 € |
| Scaleway H100, Soofi S (wenn Zugang), 150k | 1–2 h | 4–5 h | **~1 Tag** | 8–12 € |
| Scaleway L40S, Kolibri Q4, 150k | 2–4 h (ungeprüft) | 4–5 h | **~1 Tag** | 6–10 € |
| Scaleway B300-8, Kolibri BF16, 150k | 1–2 h | 4–5 h | **~1 Tag** | ~120–130 € (nicht empfohlen) |
| Nur CPU (Fallback) | 0.5B: ~4 h/120k; 4B: Tage | 4,3 h/30k (batch 64) | Tage | Strom |

Lokale Lehrerzeiten sind aus 100 Sätzen hochgerechnet, nicht über 150k
gemessen; DeepInfra- und Cloud-Zeiten sind Schätzungen. Der Engpass sind
nicht die Rechenkosten, sondern die Arbeitszeit für API-Mapping, Sharding
und Messung.

## 8. Risiken

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| DeepInfra `echo` liefert keine Prompt-Logprobs | API-Lehrer fällt weg | lokaler Qwen3.5-4B-Base (getestet) |
| Qwen3.5-Hybrid ohne optimierte Kernel | 1,5 statt 5 Sätze/s | akzeptieren oder `causal-conv1d`/`fla` prüfen (ROCm ungeprüft) |
| Gemma 3 4B (Unsloth) kaputt | keine Gemma-Destillation | Qwen3.5-4B-Base; offizielles Gemma nur mit Lizenz testen |
| `pieces=2048` frisst Wortslots | Glide-Blend sieht 15 % der Tokens nicht | Ablation `vocab=32768` / `pieces=1024` |
| ROCm/Treiber-Drift | GPU fällt nach Update weg | Versionen pinnen; 24.04 + 7.2.1 behalten |
| `dxg`-Ioctl-Fehler in `dmesg` | sieht schlimm aus, ist harmlos | `rocminfo`/Torch als Wahrheit |
| WSL-Idle-Timeout | VM stoppt nach ~60 s ohne Shell und killt den Lauf | `vmIdleTimeout=-1` + `instanceIdleTimeout=-1`; systemd-Dienst |
| 248k-Softmax im Lehrer | 14,8 GB VRAM, Thrashing bei batch=32 | batch=16 + fp16-Softmax; 2–3 GB frei |
| Kein Resume in `distill.py` | langer Lauf geht bei Abbruch verloren | 30×5k-Chunks + `merge_soft.py`; fertige Chunks bleiben |
| Lizenzen | Veröffentlichung blockiert | Tatoeba/Leipzig/OPUS-Attribution, `de_aosp` Apache-2.0 |
| Upstream-Rechte | Katalogeintrag/PR nicht möglich | Forgejo-Push ja; Upstream-Token nur Lesen |
| Soofi S gated/„other“ | kein Zugang, keine Veröffentlichung | Preview nur forschen; finale permissive Freigabe abwarten |
| Kolibri post-trained | Roh-Text-Verteilung nicht Base | 100-Satz-A/B; bei < +3 Punkten nicht skalieren |
| Kolibri-Serving | 156 GB BF16, Scaleway-B300 nur 8× (~60 €/h) | FP8 auf H100 oder Q4-GGUF auf L40S testen; sonst Qwen3.5-9B |
| Qwen3.8-Flash 180B | Self-Hosting unlukrativ, post-trained | nur DeepInfra-API nach `echo=PASS` |
| Cloud-Kosten | Download/Storage/Egress | 63–160 GB Modell auf lokale NVMe; Instanz nach 1–2 h löschen |

## 9. Reihenfolge der Arbeit

**Phase 1 (erledigt, 28.10.2026, lokal).** 150k-Lehrer → Schüler →
Export → Messung. Der Lehrer-Pass lief als `wmlm-teacher.service`
(30×5k, `Restart=on-failure`); WSL hatte `vmIdleTimeout=-1` und
`instanceIdleTimeout=-1`. Ergebnis:

- `out/de_soft_150k.npz`: 150.000 Sätze, 1.723.966 Zeilen, **91,3 %**
  Lehrer-Masse, SHA/`check_soft` OK.
- `train.py`: 30.000 Steps, heldout loss **4,3400** (ppl **76,7**),
  Checkpoints lesbar.
- `de_context.wmlm`: **10.856.432 Bytes**, d256/6/4/768, ctx40,
  vocab24576, `langs ["de"]`; `lm_probe`/`typing_eval` laufen.
- Glide: **77,40** top-1 (150k, 0,5/5,0), **78,48** mit 441k Komposita,
  top-4 **84,85**; 76,35/77,28 bei 0,7/3,0. Tippen **+2,40/+2,67** top-1.
- **Gate erfüllt**; `wmlm-teacher`/`wmlm-student` nach `DONE` **disabled**.

**Phase 2 (Bedingung erfüllt, optional).** 100-Satz-A/B mit
Qwen3.5-9B-Base auf L4 (~1 €) oder Soofi auf H100 (wenn Zugang); nur
skalieren, wenn der Cloud-Lehrer den lokalen 4B um **≥ 3 Punkte Top-8**
schlägt. Sonst bleibt das lokale Modell; die nächsten lokalen Hebel sind
d320/8/1024 und 500k Soft-Targets.

**Großer Lehrer?** Kein kompletter 150k-Neustart auf Verdacht. Der lokale
4B erfüllt das Gate bereits; ein 9B/Soofi-Lauf ist erst nach einem
100-Satz-A/B sinnvoll. Kolibri (156 GB, B300-8, post-trained) ist für einen
10-M-Schüler nicht gerechtfertigt. Der Engpass ist eher der Schüler
(10,3 M) und die 150k Soft-Targets, nicht die Lehrerbreite.

1. **G1 ist rot (gemessen 27.10.):** DeepInfra liefert keine Top-k-
   Verteilung. Kein `distill_api.py` gegen DeepInfra, keine API-Kosten dort.
   Der Probe bleibt als Regressionscheck.
2. **Lokal läuft:** `Qwen3.5-4B-Base`, `out/de_lm_full`, **150k Sätze**
   in 30×5k-Chunks (`merge_soft.py`), `batch=16`, `topk=24`, `multi=1`,
   `dtype=float16`, Softmax in fp16; gemessen **~3,2 Sätze/s**, **~13 h**.
   Fertige Chunks bleiben bei einem Abbruch erhalten. `batch=32` mit
   float32-Softmax thrash't die 16-GB-Karte (nur 1 GB frei,
   Unified-Memory-Spill); die fp16-Softmax in `patches/0005` behebt das.
   Das ist der getestete Base-Lehrer und der Fallback.
3. **Together AI (jetzt verfügbar):** `TOGETHER_API_KEY` setzen;
   `together_echo_probe.py` auf `Qwen/Qwen3.5-9B` und
   `Qwen/Qwen3.8-Flash` laufen lassen. Bei `PASS` (≥10 Alternativen)
   `together_token_test.py --data-dir out/de_lm --sentences 100`; bei
   brauchbarem top-8 `distill_api.py` bauen und 100 Sätze gegen den lokalen
   Lauf A/B messen. 150k über Together kosten 0,76–1,35 $. Nebius bleibt
   der zweite API-Anbieter.
4. **vLLM auf Scaleway (nur bei Bedarf):** `prompt_logprobs` top-100/voll;
   L4 mit Qwen3.5-9B-Base (~1 €) oder H100 mit Soofi (wenn Zugang). Erst
   100 Sätze testen; mieten nur, wenn der lokale/Together-Lauf die Lücke
   nicht schließt (§5.1a).
5. **Schüler** mit `d256/6/768`, `steps=30000`, `batch=256`,
   `distill_alpha=0.5`; nach 10k/20k/30k checkpointen.
6. **Export + `lm_probe`**, dann `typing_eval` auf Held-out, dann
   Glide-Harness mit dem echten Modell auf gehaltenem Split.
7. **Ablationen** (nur wenn G6 knapp): `vocab=32768`, `pieces=1024`,
   `distill_alpha` 0,3/0,5/0,7, `topk` 16/24/32, `d320/8/1024`.
8. **Veröffentlichung:** `data/de/de_context.wmlm`,
   `ContextModelEntry(languageId="de", repoCode="de", stem="de_context",
   approxBytes=<size>)`, Lizenz-README, `lm_probe`-Ausgabe als Beleg.

## 10. Offene Punkte

- **DeepInfra:** gemessen untauglich (27.10.2026): GPT-OSS-120B verweigert
  `echo`; Qwen3.8/Gemma/Mistral liefern Chat-Bodies; Qwen3.5-9B/Llama 3.1
  liefern Prompt-Logprobs, aber nur 1–2 `top_logprobs`-Einträge. Keine
  Top-k-Verteilung, also kein `distill_api.py`.
- **Nebius Token Factory:** `/v1/completions` mit `echo` + `logprobs`,
  aber ohne `prompt_logprobs`-Feld; die Top-N-Dichte ist live ungetestet
  (kein `NEBIUS_API_KEY`). Signup + 1 $ frei. Probe liegt bereit; bei
  `PASS` Schüler-`topk` auf 20/16. Qwen3.5-397B ist der Qualitätskandidat.
- **Together AI:** Docs sagen `echo` + `logprobs` (0–20); der Signup
  funktioniert wieder. `today` Probe + Token-Test bereit, Key fehlt.
- **Scaleway GPU:** `distill.py` mit voller Softmax ist der sauberste Weg,
  aber Instanz-Setup und Qwen3.5-9B-Base/Soofi-Zugang sind ungetestet;
  erst 100 Sätze, dann 150k.
- **Fireworks/OpenAI/Novita:** `top_logprobs` ist auf 5 begrenzt; für
  top-24 zu sparse. Nur mit `topk<=5` denkbar, nicht empfohlen.
- **Hyperbolic/Featherless:** vLLM-basiert, aber `echo`/Prompt-Logprobs
  nicht dokumentiert; nur mit Key testen, keine Priorität.
- **Lehrergröße:** 4B ist der lokale Deckel (16 GB). 9B passt auf L4/L40S,
  30B (Soofi) auf H100, 78B (Kolibri) nur mit FP8/Q4 oder großem Knoten.
  Ob die Größe bei einem 10–19M-Schüler mehr als der Tokenizer-Vorteil
  bringt, ist offen; das 100-Satz-A/B entscheidet.
- **Soofi-Zugang:** `gated: manual`, Lizenz „other“, finale permissive
  Freigabe angekündigt. Ohne Zugang nicht planbar.
- **Kolibri-Rohverhalten:** post-trained (Reasoning); erst messen, ob die
  Nächste-Wort-Verteilung auf Korpus-Text sauber ist. Der Tokenizer-Vorteil
  (62,9 % ganze Wörter) ist gemessen, die Qualität nicht.
- **`scores()` und Pieces:** Der Glide-Blend spelt keine Pieces; das ist
  eine App-Grenze, keine Modell-Grenze. Vokabular-Ablation messen, bevor
  `pieces` erhöht wird.
- **Telefon-Latenz:** erst nach dem Export messbar; das 19M-Modell ist
  ohne Engine-Änderung exportierbar, aber nicht automatisch schnell genug.
- **Register:** Tatoeba+News deckt Chat und Formal; OpenSubtitles/Wikipedia
  erst hinzufügen, wenn `typing_eval` im Chat-Register schwach ist.
