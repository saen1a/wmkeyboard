# KB: Lokale Lehrer-Kandidaten mit Qwen-Tokenizer

Stand 29.10.2026. Ergänzt [`wmlm-training-plan.md`](wmlm-training-plan.md)
§4 und [`HANDOFF.md`](HANDOFF.md). Ziel: ein besserer Lehrer als
`Qwen/Qwen3.5-4B-Base` für den 10M-Schüler, lokal auf 16 GB (RX 9060 XT),
ohne den Qwen-Tokenizer zu verlassen.

## 1. Kriterien

1. **Tokenizer:** Qwen3.5/3.8 (248k) oder Qwen3 (151k). `distill.py` mappt
   Lehrer-Tokens über Text; gleiche Familie reduziert Multi-Token-Verlust.
   Llama/Mistral/Teuken-Tokenizer sind ein Bruch.
2. **Base vor Instruct/Reasoning:** Für rohe Nächste-Token-Soft-Targets ist
   ein Base-Modell sauberer. Instruct/Reasoning nur, wenn der 100-Satz-A/B
   auf Chat **und** News gewinnt.
3. **Quantisierung:** Lehrer-Logprobs sind empfindlich. BF16/FP16 > FP8 >
   8-bit > 4-bit. 4-bit/GGUF nur nach A/B; Q4 kann die Top-k-Verteilung
   verschieben. `distill_multi.py` nutzt HF Transformers, kein GGUF.
4. **VRAM (16 GB):** 4B BF16 ~8,4 GB; 9B Q8 ~9,5 GB; 9B BF16 ~17,9 GB
   (passt nicht); 27B Q4 ~16,7 GB + KV (passt nicht); 27B Q3 ~13,5 GB
   (knapp, langsam); 35B-A3B Q3 ~16,4 GB + KV (knapp).
5. **Deutsch:** Nicht nur Benchmark, sondern Top-1/Top-8/NLL des echten
   nächsten Tokens auf Chat- und News-Heldout; dann student-gemappte
   Soft-Targets.
6. **Speed:** 4B ~3,1 Sätze/s (getestet); 9B Q8 ~1,5–2,2/s; 27B Q3
   ~0,7–1,0/s. 1,2M dauert bei 9B ~6–9 Tage, bei 4B ~4,4 Tage.
7. **Lizenz/Runtime:** Apache-2.0 bevorzugt; HF-Transformers + ROCm,
   keine GGUF-/llama.cpp-Sonderstrecke.

## 1a. Ist eine Base zwingend? Nein — Evidenz

- **Qwen3 Technical Report, §4.5:** Strong-to-Weak-Distillation nutzt
  **post-trained Lehrer** (Qwen3-32B / Qwen3-235B-A22B) und deren
  Token-Logits; die kleinen Modelle werden darauf distilliert. Das ist
  ausdrücklich Logit-Distillation, nicht nur SFT.
- **DeepSeek-R1:** Die R1-Distill-Modelle nutzen die **post-trained
  R1**-Ausgaben (800k Beispiele), nicht einen Base-Lehrer.
- **Gemma 2:** Pretraining-Distillation von einem größeren Lehrer; die
  SFT-Phase nutzt synthetische Lehrer-Ausgaben. Auch hier ist der Lehrer
  nicht zwingend Base.
- **wmkeyboard selbst:** Das englische `en_context.wmlm` wurde mit
  **`Qwen/Qwen2.5-1.5B`** destilliert (`tools/wmlm/remote/run_en2.sh`;
  `tools/wmlm/README.md`); `distill.py` default ist Qwen2.5-0.5B. Das ist
  eine **Base**, aber eine kleine und aus Kostengründen, kein Beleg, dass
  Base zwingend ist. In der 100-Satz-Messung lag Qwen3.5-4B-Base knapp vor
  Instruct (45,1/16,1 vs. 44,3/15,5) — ein Bias-Vorteil, kein Ausschluss.

**Fazit:** Base ist eine **Präferenz für eine saubere Rohtext-Verteilung**,
keine Voraussetzung. Post-trained Lehrer sind in der Praxis üblich und
können durch bessere Sprachqualität gewinnen. Entscheidend ist der
student-gemappte A/B, nicht das Etikett.

## 2. Kandidaten

| Modell | Params | Tokenizer | Typ | Lokal (16 GB) | Deutsch | Urteil |
|---|---:|---|---|---|---|---|
| **Qwen3.5-4B-Base** | 4,66B | Qwen3.5 248k | Base | BF16, ~8,4 GB | solide | **Baseline, getestet** |
| **Qwen3.5-9B-Base** | 9,65B | Qwen3.5 248k | Base | Q8 ~9,5 GB | besser als 4B | **erster Testkandidat** |
| **Empero Qwen3.8-9B-Distill** | 9,65B | Qwen3.5 248k | Destillat aus Qwen3.8-2.4T, Reasoning/EN | Q8 ~9,5 GB | indirekt, nicht DE-spezifisch | zweiter Test |
| **Empero Qwen3.8-4B-Distill** | 4,66B | Qwen3.5 248k | Destillat, Reasoning/EN | BF16 ~8,4 GB | indirekt | billiger 4B-Test |
| **LightOn Qwen3-8B-DE** | 8,19B | Qwen3 151k | Deutsch-native Reasoning-SFT | Q8 ~8,2 GB | **deutsch-optimiert** | dritter Test; Qwen3-Tokenizer |
| Qwen3.8-27B | 27,8B | Qwen3.5 248k | post-trained, MTP | Q4 ~16,7 GB + KV: **nein**; Q3 knapp | stark | **nicht lokal sinnvoll** |
| Qwen3.5-27B | 27B | Qwen3.5 248k | Base | Q4 ~16,7 GB + KV: nein | gut | zu groß |
| Qwen3.5-35B-A3B | 35B-A3B | Qwen3.5 248k | Base/MoE | Q3 ~16,4 GB + KV: knapp | gut | VRAM-Risiko; Q3 |
| SauerkrautLM/DiscoLM/LeoLM | 7–70B | Mistral/Llama | DE-Finetunes 2023/24 | teils | gut, aber alt | **nicht Qwen**; SwissAI: überholt |
| Teuken-7B | 7B | eigen | EU/DE | BF16 ~14 GB | schwach (47,7 % DE-Wissen) | **nein** |
| Kolibri-78B | 78B | eigen | DE/EN MoE | 4-bit ~40 GB | stark | **nicht lokal** |
| AlphaEdge Qwen3.5-*-deu | 0,8/2B | getrimmt | DE-Vokabular | klein | klein | kein Lehrer |

## 3. Was ist „besser“?

Nicht die Parameterzahl allein. Der 9B-Base ist der naheliegende Schritt:
gleiche Tokenizer-Familie, echtes Base-Modell, 8-bit passt. Das Empero-9B
ist aus Qwen3.8-2.4T destilliert, aber auf **Englisch/Reasoning/Mathe/Code**
getrimmt; Deutsch kann vom Qwen3.5-Base kommen, muss aber gemessen werden.
LightOn Qwen3-8B-DE ist deutsch-native, aber ein **Reasoning-SFT** und
Qwen3-Tokenizer; für rohe LM-Soft-Targets nicht automatisch besser.

**4-bit/GGUF** sind für den Lehrer riskant: Die Top-k-Verteilung kann sich
verschieben, und `distill_multi.py` spricht HF-Transformers, nicht
llama.cpp. Wenn 9B Q8 auf ROCm nicht läuft, ist der nächste saubere Weg
ein 4B-BF16-A/B oder eine GPTQ/AWQ-Unterstützung, nicht blind Q4.

## 3a. Live-A/B 4B-BF16 vs 9B-8bit (29.10.2026)

`tools/teacher_ab.py`, je 50 Chat-/50 News-Sätze, 64 Tokens, echtes
nächstes Token:

| Modell | Register | top-1 | top-8 | NLL |
|---|---|---:|---:|---:|
| Qwen3.5-4B-Base BF16 | Chat | 28,43 % | 50,10 % | 4,502 |
| Qwen3.5-4B-Base BF16 | News | 32,10 % | 54,87 % | 4,253 |
| **Qwen3.5-9B-Base 8bit** | **Chat** | **29,65 %** | **52,56 %** | **4,322** |
| **Qwen3.5-9B-Base 8bit** | **News** | **34,41 %** | **56,93 %** | **4,063** |

Delta 9B−4B: **+1,22/+2,31** top-1, **+2,46/+2,06** top-8,
**−0,18/−0,19** NLL (Chat/News). Beide Register gewinnen; 8-bit killt den
Vorteil nicht.

**Speed (batch=16, 100 Sätze, je 64 Tokens):** 4B BF16 **2,69 Sätze/s**,
9B Q8 **2,58 Sätze/s** — praktisch gleich. 1,2M wären damit **~5,2 vs.
~5,4 Tage**, nicht 6–9. Der 9B kostet also fast keine Extrazeit, nur
~9,5 GB VRAM und die 8-bit-Loader-Strecke.

**Grenzen:** 100 Sätze, nur Lehrerqualität, kein Schüler-Training. Der
nächste Gate ist ein **10k-Soft-Target-A/B** mit 3k–5k Schüler-Steps;
erst wenn der Schüler gewinnt, lohnt der 1,2M-Lauf. `distill_multi.py`
braucht dafür einen `load8bit`-Pfad (`BitsAndBytesConfig`), der im
A/B-Skript bereits funktioniert.

## 4. 100-Satz-A/B

1. Je 100 Chat- und News-Sätze aus dem Heldout.
2. Lehrer: Top-1/Top-8/NLL des **echten nächsten Tokens** auf beiden
   Registern; 4B-Base als Referenz.
3. Danach student-gemappte Soft-Targets (`multi=1`, topk=24) und
   `typing_eval`/Glide auf demselben Split.
4. Gewinner nur, wenn Chat **und** News nicht schlechter werden und die
   Geschwindigkeit den 1,2M-Lauf in akzeptabler Zeit schafft.
5. 8-bit vor 4-bit; bei 4-bit separat A/B.

## 4a. H100 80 GB und Kolibri

**Gibt es ein destilliertes Kolibri? Nein.** Aleph Alpha hat nur
**Kolibri-1 (78B, 3,46B aktiv, FP8 ~78 GB)** veröffentlicht; **Kolibri
Origin (30,6B)** ist intern und nicht downloadbar. `Kolibri-1-dspark` ist
ein Draft-Modell für Speculative Decoding, kein destillierter Lehrer.
Community-Varianten sind **Quantisierungen** (4-bit, NVFP4, MLX, GGUF),
keine Destillate.

**Passt Kolibri auf eine H100 80 GB?** Offiziell **nein**:
- BF16 ~156 GB → 4× H100.
- FP8 ~78 GB → **Minimum 2× H100 SXM5** (oder 1× H200/B200/B300); eine
  H100 80 GB reicht mit KV/Overhead nicht.
- 4-bit-Community (~40 GB) passt, ist aber inoffiziell; für Lehrer-Logprobs
  und vLLM-Plugin riskant. GGUF/MLX passt nicht in `distill_multi.py`.

**Ein H100 80 GB (€2,8665/h) ist trotzdem die beste Einzel-GPU-Option.**
Für **Deutsch** ist wahrscheinlich **Qwen3.8-27B** der beste Lehrer:
- **Qwen3.8-27B** (27B dense, BF16 ~55 GB / FP8 ~28 GB) passt; neuer
  (Aug 2026), in unabhängigen Berichten deutlich besseres Deutsch als
  Qwen3.5-35B-A3B, Sprache/Punctuation auf Muttersprachler-Niveau. Es ist
  post-trained, kein Base; für Soft-Targets ist die Completion-Verteilung
  trotzdem brauchbar.
- **Qwen3.5-35B-A3B-Base** (~72 GB BF16) ist die **Base**-Alternative:
  schneller (3B aktiv), aber älter und in Sprach-Benchmarks etwas schwächer
  (MMLU-Pro 85,3 vs. 86,1; IFEval 91,9 vs. 95,0; MMLU-ProX 81,0 vs. 82,2;
  WMT24++ 76,3 vs. 77,6 für 27B).
- **Qwen3.5-27B** ist ebenfalls besser als 35B-A3B auf Sprach-Benchmarks,
  aber Qwen3.8-27B ist die neuere Generation.
- 1,2M mit 27B BF16 bei 50–200 Sätzen/s: **1,7–6,7 h / 5–19 €**; FP8
  (28 GB) eher 100–400 Sätze/s → **0,8–3,3 h / 3–10 €**. Ein 30–60-min-
  Benchmark (~1–3 €) klärt es.
- Das ist wahrscheinlich das beste **korrekte** Ergebnis pro Euro/Zeit;
  Kolibri auf 2×H100 (€5,73/h) wäre die maximale deutsche Qualität, kostet
  aber ~95–190 € für 1,2M und braucht das Aleph-Alpha-vLLM-Plugin.

**Qwen3.8-Flash-Next / Qwen3.5-Flash:** Das sind zwei verschiedene Dinge.

| Modell | Parameter | Präzision / Größe | 1× H100 80 GB? |
|---|---|---:|---|
| **Qwen3.5-Flash** | gehostete Version von **Qwen3.5-35B-A3B** | offenes 35B-A3B: BF16 ~72 GB | **ja** (BF16, MTP aus) |
| Qwen3.5-35B-A3B-Base | 35B total / 3B aktiv | BF16 ~72 GB | **ja** |
| **Qwen3.8-Flash-Next** | 125B main + 51B N-Gramm + 4B MTP, 6B aktiv | FP8 ~180 GB | **nein**; 2× H100 |
| Qwen3-Next-80B-A3B | 80B / 3B aktiv | FP8 ~76 GB | **ja**, 8K-Kontext; älter |

**Qwen3.8-Flash-Next** ist der 125B-Qwen4-Vorschau-MoE, kein 35B-Flash.
FP8 braucht ~2× H100 (oder 1× B200); BF16 ~360 GB; 4-bit-Community passt
vielleicht auf eine H100, ist aber quantisiert und für Lehrer-Logprobs
riskant. **Qwen3.5-Flash** dagegen ist nur der gehostete Name des offenen
**Qwen3.5-35B-A3B**; dessen Gewichte passen als BF16 auf **eine** H100.

**Durchsatz — wichtiger als die Parameterzahl:** Bei `prompt_logprobs` zählt
**Prompts/s**, nicht die Decode-Tokens/s. Ein Satz hat ~20 Tokens; 100 t/s
wären nur ~5 Sätze/s und 1,2M ≈ 67 h. Die H100 macht bei batched Prefill
aber viel mehr:

| Pfad | Schätzung | 1,2M | Kosten @2,8665 €/h |
|---|---:|---:|---:|
| 35B-A3B BF16, vLLM, Batch 32–64 | **100–500 Sätze/s** | **0,7–3,3 h** | **2–10 €** |
| 35B-A3B FP8 (36 GB), Batch 128–256 | 200–1000 Sätze/s | 0,3–1,7 h | 1–5 € |
| **27B BF16, vLLM** | **50–200 Sätze/s** | **1,7–6,7 h** | **5–19 €** |
| **27B FP8 (28 GB), Batch 128–256** | **100–400 Sätze/s** | **0,8–3,3 h** | **3–10 €** |
| 35B-A3B BF16, HF `distill_multi.py` Batch 16 | 10–30 Sätze/s | 11–33 h | 32–95 € |
| lokal 9B Q8 | 2,58 Sätze/s | 5,4 Tage | ~15–20 € Strom |

Die vLLM-Schätzungen sind aus der H100-Bandbreite/3B-active-MoE
hochgerechnet, nicht gemessen. **Ein 30–60-min-Benchmark (1–3 €) klärt es.**
Ziel: **>35 Sätze/s**, dann bleibt 1,2M unter 10 h (<29 €); bei 100 Sätzen/s
sind es ~3,3 h (~10 €). `distill_multi.py` mit HF-Transformers ist für
<10 h zu langsam; dafür einen vLLM-Offline-Collector
(`LLM.generate(prompts, SamplingParams(prompt_logprobs=24, max_tokens=1))`)
verwenden.

**Kosten:** H100 80 GB €2,8665/h; 1,2M mit 35B-A3B BF16 bei 100–500 Sätzen/s
~0,7–3,3 h = **~2–10 €**; bei nur 30 Sätzen/s ~11 h = €32. Lokal 9B Q8:
~5,4 Tage, ~15–20 € Strom. Flash-Next/Kolibri auf 2×H100: ~2× Satz, also
~4–20 € bei gutem Durchsatz, plus 125B/78B-Setup; bei 10–20 Sätzen/s
~17–33 h = €97–190.

### 4a.1 H100-1-80G vs. L40S-1-48G (live 30.10.2026, `scw`)

| | H100-1-80G | L40S-1-48G |
|---|---:|---:|
| Preis | 2,8665 €/h | **1,46988 €/h** |
| FP8 dense | 1.513 TFLOPS | 733 TFLOPS |
| VRAM-Bandbreite | ~2,0 TB/s | 864 GB/s |
| VRAM | 80 GB | 48 GB |
| vCPU / RAM | 24 / 240 GB | 8 / 96 GB |
| Netz | 10 Gbps | 2,5 Gbps |
| Bestand `fr-par-2` | **out of stock** | low stock (2) |

Für die Prefill-Last (`prompt_logprobs=24`, `max_tokens=1`, Batch 32, ~25
Tokens/Prompt) ist die L40S **0,4–0,5× der H100**, also ~40–55 statt 100+
Prompts/s.

**Gemessen am 30.10.2026** (echter Lauf, `benchmark_quick.py`, Qwen3.8-27B-FP8,
vLLM 0.32.0, torch 2.13.0+cu130): **59,45 Prompts/s**, 1.029 Prompt-Tokens/s,
477,9 ms je Batch-32, NLL 4,28, top-1 32,2 %, top-k-Breite 24,4, 0 fehlende
bzw. nicht-finite Logprobs. Projektion: **1,2M = 5,61 h / 16,19 €**,
2M = 9,34 h / 26,99 €. Break-even gegenüber H100@100/s liegt bei 50,9
Prompts/s — die L40S ist damit **pro Satz günstiger als eine H100 bei
100/s**, aber halb so schnell. Distill-Durchsatz im gleichen Lauf:
55,8 Sätze/s (10k Sätze, Masse 90,6 %).

Notwendige vLLM-Einstellungen auf dieser Karte (sonst startet der Engine
nicht bzw. bricht beim ersten `generate` ab): `max_num_seqs=64` (Qwen3.8
belegt einen Mamba-Cache-Block pro Sequenz, Default 256 passt nicht in
48 GB), `max_logprobs=24` (Default 20) und
`VLLM_USE_FLASHINFER_SAMPLER=0` (das GPU-OS-Image hat kein `nvcc`, der
FlashInfer-JIT-Sampler kann seinen Kernel nicht bauen). Break-even pro Satz liegt bei **50,9 %** der H100-Rate
(1,46988/2,88775); bei 0,4–0,5× ist sie **gleich teuer bis ~25 % teurer**
und braucht doppelt so lange: 1,2M ≈ 7,4 h / 10,9 € (45/s) statt 3,3 h /
9,6 €; 2M ≈ 12,3 h / 18,1 € (über der 12-h-Regel).

**Zwei harte Grenzen der L40S:** 48 GB reichen für FP8-27B (28 GB), aber
**nicht** für die BF16-Referenz (55 GB) oder 35B-A3B-BF16 (72 GB) — der
BF16-vs-FP8-A/B (Phase 0b/1) ist dort unmöglich. Und 2M setzt ≥100
Prompts/s voraus, was auf der L40S nicht erreichbar ist; dort bleibt der
1,2M-Pfad.

**Entscheidung 30.10.2026:** H100 abwarten (2M + BF16-Referenz bleiben so
möglich), L40S nur als Fallback für 1,2M. Die L40S-1-48G ist mit 1,46988 €/h
live bestätigt; das Image `Ubuntu Noble GPU OS 13 (Nvidia)` ist
`741cfd27-a822-4c82-b80f-973b562743ad`.

## 4b. Base-Modelle für Deutsch auf einer H100

**Qwen3.8-27B hat keine öffentliche Base-Variante.** Das Modellkarten-Repo
enthält nur das post-trained Modell; die HF-Diskussion „Base model, PLEASE!“
bestätigt das. Dasselbe gilt für **Qwen3.5-27B** (Diskussion „Availability of
the Qwen3.5-27B Base model“: nicht veröffentlicht). Auch
**Qwen3.5-122B-A10B-Base** und **Qwen3-32B-Base** sind nicht abrufbar
(401/kein Repo). Die einzige aktuelle 30B+-Base der Qwen3.5-Familie ist
**Qwen3.5-35B-A3B-Base**.

| Modell | Base? | Typ | Aktiv | 1× H100 80 GB | Deutsch | Urteil |
|---|---|---|---|---:|---|---|
| **Qwen3.5-35B-A3B-Base** | **ja** (Karte: nur Pre-training) | MoE 35B | 3B | BF16 ~72 GB | DE 76,6 | **beste verfügbare Base** |
| Qwen3.5-4B/9B/2B/0.8B „Base“ | **Namensvetter, Karte sagt Pre-training & Post-training** | dense | – | ja | solide | **nicht gesichert Base** |
| Qwen3-14B-Base | **ja** (Pretraining) | dense 14B | 14B | BF16 ~28 GB | älter, schwächer | **größte echte dense Base auf 1× H100** |
| Qwen3.5-27B | nein | dense 27B | 27B | BF16 ~55 GB | stark | post-trained, keine Base |
| **Qwen3.8-27B** | **nein** | dense 27B | 27B | BF16 ~55 GB / FP8 ~28 GB | **sehr stark** | **bester Deutsch-Lehrer, aber nicht Base** |
| Qwen3.6-27B | nein | dense 27B | 27B | BF16 ~55 GB | stark | post-trained, älter als 3.8 |
| Qwen3-32B-Base | **nicht veröffentlicht** | dense 32B | – | – | – | Qwen3-32B ist post-trained |
| Qwen3.5-122B-A10B | nein | MoE 122B | 10B | FP8 ~122 GB: nein; 4-bit ~61 GB: ja | besser | quantisiert, nicht Base; 4-bit-Risiko |
| Kolibri-1 | nein (nur post-trained) | MoE 78B | 3,5B | FP8 ~78 GB: 2× H100; 4-bit ~40 GB: ja | DE-fokussiert | 4-bit/Plugin, nicht Base |
| Teuken-7B-Base | ja | dense 7B | 7B | ~14 GB | schwach (47,7 %) | nicht besser |
| Pharia-1-7B / Occiglot-7B | teils | dense 7B | 7B | ~14 GB | gut, aber alt | nicht besser als Qwen3.5 |

**Wichtig zur Verifikation:** Die Modellkarten sind eindeutig nur bei
**Qwen3.5-35B-A3B-Base** („Training Stage: Pre-training“), **Qwen3-14B-Base**
(„Pretraining“) und **Teuken-7B-Base**. Die Qwen3.5-4B/9B/2B/0.8B-„Base“-
Karten sagen dagegen **„Pre-training & Post-training“** — der Name „Base“
ist dort irreführend; ich würde sie nicht als reine Base behandeln.
Qwen3.8-27B, Qwen3.5-27B, Qwen3.6-27B, Qwen3-32B und Kolibri-1 sind
post-trained.

**Dense vs. MoE:** Dense 27B hat 27B aktive Parameter und ist pro Token
sprachlich stärker als der 35B-A3B mit nur 3B aktiven. Genau deshalb ist
Qwen3.8-27B (dense, post-trained) im Deutsch-Vergleich vorn. Eine **dense
27B-Base** gibt es aber nicht — die Wahl ist:
- **Base zwingend:** Qwen3.5-35B-A3B-Base (MoE, bestes Deutsch) oder
  Qwen3-14B-Base (dense, aber älter/schwächer).
- **Deutsch maximal:** Qwen3.8-27B (post-trained, dense), auch ohne Base.
- **Kompromiss:** Qwen3.5-122B-A10B 4-bit (post-trained, 10B aktiv) passt
  auf eine H100, ist aber quantisiert und keine Base.

**Was kommt Qwen3.8-27B-Base am nächsten?** Am ehesten
**Qwen3.5-35B-A3B-Base** (gleiche Familie, echte Base) oder das
**post-trained Qwen3.8-27B selbst**. Eine 27B-dense-Base existiert nicht;
Qwen3.5-27B ist nur post-trained.

**Empfehlung:** Wenn „Base“ hart ist, **Qwen3.5-35B-A3B-Base BF16** auf
einer H100; wenn Deutsch wichtiger ist, **Qwen3.8-27B BF16/FP8** (keine
Base, aber der beste Sprachlehrer). Ein 100-Satz-A/B auf der H100
entscheidet, ob der Base-Vorteil den Sprachunterschied aufwiegt.

## 4c. Kolibri-GGUF/MLX auf einer H100?

**MLX ist Apple-only.** `here-be-dragons-ai/Kolibri-1-MLX-3bit` und
`eins78/Kolibri-1-mlx-mixed-4-8-bit` laufen **nicht** auf einer H100.

**GGUF** läuft auf einer H100 über llama.cpp/CUDA, wenn die Datei in 80 GB
passt:

| Repo | Quant | Größe | 1× H100? |
|---|---|---:|---|
| webmp3/Sakura | IQ4_XS | 38,1 GiB | ja |
| webmp3/Sakura | IQ3_XXS | 28,8 GiB | ja |
| Hob-forge | Q4_K_M | 47,5 GB | ja |
| Hob-forge | Q5_K_M | 55,6 GB | ja |
| Hob-forge | Q6_K | 59,8 GiB | ja |
| Hob-forge | Q8_0 | ~83 GB / 77,4 GiB | **nein** (plus KV/Overhead) |
| Myric APEX | 22,7–41,9 GiB | ja |
| florentin-one/Elster-1 | FP8, 73,45 GiB | **knapp**; 1× H100 nur mit 0,95-Auslastung, riskant |

**vLLM-4-bit, das auf eine H100 80 GB passt — inklusive `prompt_logprobs`:**

| Repo | Format | Größe | 1× H100? | Bemerkung |
|---|---|---:|---|---|
| **Padakovec/Kolibri-1-W4A16-GPTQ** | GPTQ W4A16, vLLM | **41 GiB** | **ja** | ausdrücklich für 1× A100 80 GB; `aleph-alpha-inference`-Plugin |
| mbehr90/Kolibri-1-int4-w4a16 | INT4 W4A16, vLLM | ~41–44 GiB | ja | compressed-tensors, Plugin |
| mbehr90/Kolibri-1-nvfp4 | NVFP4 W4A16, vLLM | 44,4 GiB | ja | Marlin-W4A16 auf H100 |
| audreyt/Kolibri-1-NVFP4-W4A16 | NVFP4 W4A16 | ~44 GiB | ja | Marlin, H100 |
| MediSync-AI/Kolibri-1-REAP-40B-A3B-W4A16 | W4A16, 40B | ~25 GiB | ja | Experten-gepruned, Qualitätsverlust |
| MediSync-AI/Kolibri-1-REAP-31B-A3B-W4A16 | W4A16, 31B | kleiner | ja | stärker gepruned |
| florentin-one/Elster-1 | FP8, 73,45 GiB | 73,45 GiB | **knapp** | Fine-tune, 0,95-Auslastung, kurzer Kontext |
| Aleph-Alpha/Kolibri-1 (offiziell FP8) | FP8, ~73–78 GiB | – | **nein/2×** | offiziell 2× H100 |

**Das ist die Antwort auf die Frage:** Ja, es gibt eine passende
Kolibri-Quantisierung für **eine** H100: **Padakovec/Kolibri-1-W4A16-GPTQ**
(41 GiB) oder `mbehr90`/`audreyt` 4-bit. Sie laufen mit vLLM +
`aleph-alpha-inference>=1`, `--reasoning-parser kolibri1`, kurzem Kontext
und `prompt_logprobs`. Es ist aber **4-bit** und **keine Base** — die
Kolibri-1-Releases sind post-trained.

**Der eigentliche Blocker ist nicht die Größe, sondern `prompt_logprobs`:**
llama.cpp liefert bei `echo:true` + `logprobs` nur **generierte** Tokens,
keine Prompt-Token-Verteilung (Issue #27174; PR #27537 noch offen). Damit
kann man keine Soft-Targets über den ganzen Satz erzeugen. `distill.py`
spricht HF-Transformers, nicht llama.cpp. vLLM-GGUF mit dem
Aleph-Alpha-Kolibri-Plugin ist nicht der Community-GGUF-Pfad.

**Fazit:** Die GGUF-Dateien sind gut für eine **Generations-/Qualitätsprobe**
auf einer H100 (Q4/Q5/Q6), aber **nicht für die 1,2M-Soft-Targets**. Für
`prompt_logprobs` auf einer H100 ist **Padakovec/Kolibri-1-W4A16-GPTQ**
(41 GiB, vLLM + Plugin) der passende Kandidat; 4-bit-Qualität muss gegen
Qwen3.8-27B BF16/FP8 antreten. Elster-1 ist ein Fine-tune, keine Base, und
mit 73,45 GiB nur knapp. Offizielles Kolibri-FP8 braucht **2× H100**. Eine
öffentliche **Kolibri-Base** gibt es nicht; die beste echte Base bleibt
Qwen3.5-35B-A3B-Base.

## 4d. Kolibri vs. Qwen3.8-27B — kein Automatiksieg

**Beide sind post-trained, keine Base.** Der Base-Vorteil entscheidet hier
also nichts. Der Vergleich ist:

| | Kolibri-1 | Qwen3.8-27B |
|---|---|---|
| Parameter | 78B MoE, **3,46B aktiv** | **27B dense, 27B aktiv** |
| Deutsch | deutsch-fokussiert (23,9 % DE-Training) | stark gelobt, Benchmarks stark |
| 1× H100 | nur **4-bit** (41 GiB GPTQ) oder GGUF; FP8 = 2× H100 | **BF16/FP8**, eine H100 |
| Teacher-Logprobs | 4-bit-Risiko; vLLM-Plugin nötig | BF16/FP8, vLLM ohne Sonderplugin |
| Tokenizer | Kolibri 128k, DE/EN | Qwen 248k, passt zum Schüler |
| Durchsatz | 3,46B aktiv, sehr schnell | dense 27B, langsamer, aber batched |
| 1,2M | 4-bit ~0,5–1,7 h (€1–5); FP8 2× ~? | BF16 ~1,7–6,7 h (€5–19); FP8 ~0,8–3,3 h (€3–10) |

**Kolibri ist der bessere deutsche Spezialist**, besonders als offizielles
FP8 auf 2× H100. Auf **einer** H100 ist er aber nur 4-bit; die
Experten-Logprobs können sich verschieben, und das Aleph-Alpha-Plugin ist
zusätzlicher Aufwand. Qwen3.8-27B läuft dort in **BF16/FP8** und hat den
zum Schüler passenden Qwen-Tokenizer.

**Deshalb: nicht „in jedem Fall besser“.** Die Entscheidung ist:

1. **2× H100 + Kolibri FP8:** wahrscheinlich bester deutscher Lehrer; testen.
2. **1× H100 + Kolibri 4-bit vs. Qwen3.8-27B BF16/FP8:** 100-Satz-A/B;
   gewinnt Kolibri klar, nehmen; sonst Qwen wegen Präzision/Einfachheit.
3. **Base zwingend:** keiner von beiden; dann Qwen3.5-35B-A3B-Base.

## 4e. Qwen3.8-27B: welche Variante hilft?

**Für die H100 ist die wichtigste Variante die offizielle FP8-Version:**

| Variante | Größe | 1× H100 | Für Soft-Targets? |
|---|---|---:|---|
| **Qwen3.8-27B (BF16)** | ~55 GB | ja | **Referenz, beste Präzision** |
| **Qwen3.8-27B-FP8** | ~28 GB | ja | **offiziell, nahezu verlustfrei; 2× Batch, schneller** |
| Qwen3.8-27B-AWQ-INT4 | ~17 GB | ja | 4-bit; auf H100 unnötig, Qualitätsrisiko |
| NVFP4 / QUASAR / SLQ | 4-bit | teils Blackwell | nicht für H100 nötig; W4A4 braucht Blackwell |
| GGUF / MLX | – | GGUF ja, MLX nein | **kein `prompt_logprobs`** (llama.cpp) |
| MTP / EAGLE4 / DFlash2 | Drafts | – | beschleunigen Generierung, nicht Prompt-Logprobs; MTP aus |

**Deutsche Fine-tunes/Adapters:** Es gibt **keinen belastbaren deutschen
Qwen3.8-27B-Fine-tune**. `DragonBophades/Eintopf-Qwen3.8-27B` ist ein
Negativ-Ergebnis (9 fremde LoRAs, ARC +5, sonst nichts); `Wichtel-Qwen3.6-27B`
ist ein englischer Agenten-Merge. `LightOn Qwen3-8B-DE` ist deutsch-native,
aber nur 8B und Qwen3-Tokenizer. Ein eigener deutscher LoRA auf Rohtext wäre
möglich, aber ein zusätzliches Experiment; für den Lehrer zuerst BF16/FP8
testen.

**Wichtig:** Die deutsche Qualität von Qwen3.8-27B ist **nicht unumstritten**.
Ein Translator lobt sie stark; in der HF-Diskussion berichtet jemand, der
27B sei bei BF16/F16-KV **schlechter** als erwartet, und 4-bit-GGUF erfinde
Wörter. Deshalb: **A/B gegen Qwen3.5-35B-A3B-Base und ggf. Kolibri 4-bit**,
nicht blind auf „27B > 35B“ setzen.

**Empfehlung:** Qwen3.8-27B **BF16 als Referenz**, **FP8 als Laufvariante**;
wenn FP8 im 100-Satz-A/B nicht zurückfällt, FP8 für 1,2M (28 GB, 2× Batch,
~0,8–3,3 h, 3–10 €). Keine 4-bit/GGUF/Adapter für den Lehrer, solange
BF16/FP8 auf die H100 passen. Base bleibt Qwen3.5-35B-A3B-Base, falls
„Base“ zwingend ist.

## 4f. Cloud-init für die H100

Das Feld ist **optional**. Für einen 1-h-Benchmark würde ich es **leer
lassen** und ein Image mit NVIDIA-Treiber/CUDA nehmen; vLLM per SSH oder
per vLLM-Docker-Image starten. Cloud-init ist sichtbar und sollte **keine
Secrets** (HF-Token, SSH-Key) enthalten.

Wenn du es für reproduzierbare Setups nutzen willst:
[`h100-cloud-init.yaml`](h100-cloud-init.yaml). Es installiert nur
`tmux/htop/git/curl/rsync/python3-venv`, setzt `HF_HOME=/data/hf-cache`
und legt `/data/{hf-cache,out,corpus}` an. **Kein** vLLM/CUDA-Install in
cloud-init, kein Auto-Formatieren eines Block-Devices, kein Modelldownload.

Danach per SSH:

```bash
nvidia-smi
python3 -m venv /opt/vllm
/opt/vllm/bin/pip install -U pip
/opt/vllm/bin/pip install vllm hf_transfer
# oder: docker run --gpus all -p 8000:8000 \
#   -v /data/hf-cache:/root/.cache/huggingface \
#   vllm/vllm-openai:latest --model Qwen/Qwen3.8-27B-FP8
```

Für Daten/Modelle: Scratch-Volume nach `lsblk` manuell mounten; Korpus per
`rsync`/Object Storage hochladen, nicht in cloud-init. Ein 1-h-Benchmark
kostet ~3 €; Setup/Download kann länger dauern als der Benchmark.

## 5. Empfehlung

- **Zuerst:** `Qwen/Qwen3.5-9B-Base` in 8-bit; gleiche Familie, Base,
  besseres Deutsch als 4B. Wenn ROCm-8-bit scheitert, 4B-BF16 behalten.
- **Dann:** `empero-ai/Qwen3.8-9B-Distill` (8-bit) und
  `lightonai/Qwen3-8B-DE` (8-bit) im selben A/B.
- **Nicht:** 27B/35B lokal quantisieren, GGUF-Lehrer, SauerkrautLM/DiscoLM/
  LeoLM/Teuken als Qwen-Ersatz.
- **Zeit:** 9B Q8 ~6–9 Tage für 1,2M; 4B ~4,4 Tage. Der Lehrerwechsel muss
  den Qualitätsgewinn wert sein; sonst bleibt 4B-Base.

## 6. Pause fürs Gaming

Der Lehrer läuft in 5k-Chunks; `systemctl stop wmlm-teacher-1m2` gibt die
GPU frei, kostet höchstens den aktuellen Chunk (~27 min), und
`systemctl start wmlm-teacher-1m2` macht mit den gültigen Chunks weiter.
Der Schüler checkpointet alle 1000 Steps; `resume=out/de_run/last.pt`.
Vor dem Spielen `rocm-smi`/`nvidia-smi` prüfen, dass kein Prozess mehr läuft.
