# KB: Gehostete Lehrer für `distill.py` — Anbieter, Live-Tests, Kosten

Stand: 29.10.2026. Ergänzt [`wmlm-training-plan.md`](wmlm-training-plan.md)
§1.7 und §7. Ziel: `prompt_logprobs` mit **mindestens 10–20 Alternativen pro
Prompt-Position**, Qwen-Tokenizer-Familie, zuverlässig, ohne 4 Tage lokal.

## 0. Ergebnis

**Chutes** (`https://llm.chutes.ai/v1`) ist der neue erste Kandidat, aber
nur **`Qwen/Qwen3.8-27B-TEE`** ist dafür geeignet: vLLM,
`allow_logprobs: true`, `prompt_logprobs` 0–20, Qwen-Tokenizer. 1M deutsche
Sätze kosten **~2–3 $**; gemessen sind es aber **~4,8 Tage** bei 8
Workern/Retries (4 Worker ~6,6 Tage), nicht 3–12 h. Die stärkere
**`Qwen3.5-397B-A17B-TEE`** läuft auf **SGLang** und
liefert über den OpenAI-Gateway **keine** Prompt-Logprobs; Qwen3.6-27B
genauso, 2.4T/Max sind extern. Together und DeepInfra sind live
durchgefallen; Together liefert live gemessen (03.11.2026, §2b) **genau 5**
Alternativen pro Position und bleibt damit unter der Anforderung von §1,
DeepInfra 1–2. Der Chutes-Key liegt; die Balance war **0 $** (HTTP 402),
ist inzwischen aber aufgeladen. **Wichtig:** Qwen3.8-27B lief im korrekten
100-Satz-Lauf **99/100** (Completions und Chat), 98/99 beim ersten Versuch;
der Rest war NaN/502. Frühere 1/10-Serien waren lastabhängig. Ursache ist
der vLLM-MTP-Bug #53488. **Noch wichtiger:** 9 von 10 Wiederholungen eines
einfachen Prompts kamen mit **HTTP 200, aber falschen** Prompt-Logprobs
(Top-1 `mehr`/`ools`, echtes ` will` auf Rang 70.733). Der 100-Satz-Lauf
ergab top-1 3,6 % / NLL 1e36. **Qwen3.8-27B ist damit als Lehrer unbrauchbar,
bis MTP deaktiviert oder vLLM auf #53520 gehoben ist.** Kimi ist stabil
(20/20), hat aber den schlechteren Deutsch-Tokenizer. Details §3b/§3d.

## 1. Anforderungen

- Prompt-Logprobs für **jede** Position, nicht nur generierte Tokens.
- Top-k **≥ 10**, ideal 16–24, pro Position; `top_logprobs` allein reicht
  nicht, wenn es nur für Output-Tokens gilt.
- Qwen-Tokenizer-Familie für den Qwen3.5-4B-Schüler (sonst Multi-Token-
  Mapping); ACS/Llama ist möglich, aber ein Bruch.
- Zuverlässig, wiederholbar, mit Key außerhalb des Repos.
- Kosten und Laufzeit für 1M Sätze im Rahmen.

## 2. Live-Tests (29.10.2026, vorhandene Keys)

| Anbieter | Modell | Ergebnis | Exit |
|---|---|---|---:|
| Together | `Qwen/Qwen3.5-9B` | Prompt-Logprobs da, aber nur **1** Top-Eintrag (gesendet: `logprobs: 20`, laut Support 3.11. ungültig) | 1 |
| Together | `openai/gpt-oss-120b` | **HTTP 422** Unprocessable Entity (= der heute bestätigte Validierungsfehler für `logprobs > 5`) | 3 |
| Together | `Qwen/Qwen3.8-*` | **HTTP 403** (früherer Test) | 3 |
| DeepInfra | `Qwen/Qwen3.5-9B` | `top_logprobs` nur **2** Einträge | 1 |
| DeepInfra | `Qwen/Qwen3.8-Flash` | keine Logprobs | 1 |
| Chutes | Qwen3.8/3.5 | Doku: `prompt_logprobs` 0–20; Key liegt; Balance war 0 → 402, inzwischen aufgeladen | 3 |
| Together | `Qwen/Qwen3.5-9B` | 03.11. mit `logprobs: 5`: **200**, 5/5 Alternativen, alle nutzbaren Prompt-Positionen (§2b) | 0 mit `--min-top 5` |
| Together | `openai/gpt-oss-120b` | 03.11. mit `logprobs: 5`: **200**, 5/5 — die 422 vom 29.10. war die Breite | 0 mit `--min-top 5` |

**Chutes-Live-Test 29.10.2026:** Der Key ist vorhanden
(`C:\Users\saenta\chutesai.key`), aber das Konto hatte zum Testzeitpunkt **0,0 $** Guthaben (inzwischen aufgeladen).
`Qwen/Qwen3.8-27B-TEE` antwortet **HTTP 402** („Quota exceeded and account
balance is $0.0“). Auch die mit 0,0000 $/1M gelisteten Modelle
(Qwen3.8-Max, DeepSeek-V4.1-Flash, GLM-5.3, Qwen3.8-2.4T) verlangen
„a positive balance for external provider execution“. **Ohne Aufladung
läuft bei Chutes keine Inferenz**, auch nicht auf den 0-$-Modellen.

Chutes-Katalog (ohne Key abrufbar, `GET /v1/models`): Qwen3.8-27B-TEE,
Qwen3.5-397B-A17B-TEE und Qwen3.6-27B-TEE sind live, `owned_by: vllm`,
`allow_logprobs: true`, TEE. Qwen3.8-27B hatte **60 aktive Instanzen**.

## 2b. Together-Antwort des Supports (03.11.2026) — Cap bei 5 Alternativen

Was Together zusagt: Prompt-Top-k-Logprobs funktionieren heute auf bezahlten
Serverless-Modellen über `/v1/completions` mit `echo: true`, `logprobs: 5`,
`max_tokens: 1`. Die Verteilung steht in `choices[0].logprobs`
(`tokens`, `token_logprobs`, `top_logprobs`), ein Eintrag pro Prompt-Token
(das erste ohne), danach der eine generierte Token. Zwei Grenzen:

1. **Maximal 5 Alternativen pro Position.** Werte > 5 sind ein
   Validierungsfehler; die API-Referenz mit 0–20 ist falsch (Support räumt
   das ein).
2. `/v1/chat/completions` liefert pro Prompt-Position **nur die eine
   Top-Alternative** (und zusätzlich die Chat-Template-Tokens) — für
   Soft-Targets also unbrauchbar, nur `/v1/completions` zählt.

**Was das an den Messungen vom 29.10. erklärt.** Beide Probes haben
`logprobs: 20` gesendet (`tools/together_echo_probe.py`,
`tools/together_token_test.py`) — ein Wert, den Together ablehnt. GPT-OSS-120B
→ **422** war dieser Validierungsfehler; die frühere Schlussfolgerung
„Prompt-Logprobs kaputt“ war damit nie belegt.

**Live nachgemessen 03.11.2026** (`tools/together_echo_probe.py`, frischer
Key; 20 deutsche Sätze über die Probe, Masse/Recall über ein Wegwerfskript
mit 233 Prompt-Positionen):

| Test | Ergebnis |
|---|---|
| `Qwen/Qwen3.5-9B`, `logprobs: 5`, `echo: true` | **200**, Verteilung da: 6 von 6 nutzbaren Prompt-Positionen mit Logprob, `top_logprobs` **5 / 5** (min/median) → Probe `PASS` mit `--min-top 5` |
| `openai/gpt-oss-120b`, gleicher Request | **200**, ebenfalls **5 / 5** — die 422 vom 29.10. war die Breite, nicht das Modell |
| `logprobs: 20` (wie am 29.10.) | **HTTP 400** `logprobs: Validation error: range [{"max": 5, "value": 20, "min": 0}]` |
| Masse in den 5 Alternativen | Mittel **0,755** (min 0,184, max 1,000) — bei top-24-Zeilen sind es **0,906** |
| Recall des echten Tokens (Token-Ebene, 233 Positionen) | top-1 **0,489**, top-5 **0,760** |
| `logprobs`-Spanne Rang 1…5 | im Mittel **3,55 nats** |
| Reihenfolge der `top_logprobs` | **unsortiert** (nur 11 von 233 Positionen kamen absteigend, zwischen zwei gleichen Requests wechselt sie) → Rang kommt aus dem Logprob, nie aus der Position |
| Prompt-Logprobs vs. Generierung | für 6 Präfixe identisch: `token_logprobs` des generierten Tokens = Top-Eintrag = erzwungene Echo-Zeile (Δ 0,00) → die Prompt-Verteilung ist die echte Modellverteilung |
| `/v1/chat/completions` | kein Prompt-Logprob-Feld in der OpenAI-Shape; nur Output-Top-5 der generierten Tokens |

Damit ist der Support-Anspruch **bestätigt**: completions + `echo` + `logprobs: 5`
liefert echte Prompt-Top-5, und der alte Ein-Eintrag-Befund war ein Artefakt
der ungültigen Breite.

**Reicht mehrfaches Wiederholen nicht?** Nein — gemessen:

- **Identischer Request:** dasselbe Ergebnis. Auch `temperature` 0 vs. 1,2,
  `n: 3`, `seed: 42` und `top_p: 0,5` ändern die Prompt-Logprobs **nicht**
  (alle 5 Läufe bit-gleich; nur die Reihenfolge gleichwahrender Einträge
  wechselt) — sie entstehen im Prefill, nicht im Sampler.
- **`logit_bias`-Runden** wären der mathematisch richtige Hebel (Top-5 sperren
  → Ränge 6–10; der Renormierungsfaktor ist die bekannte Masse der gesperrten
  Kandidaten, also exakt invertierbar). Together wendet ihn aber **nicht auf
  Prompt-Positionen** an: mit `−100` auf **151 000 von ~152 000** Token-Ids
  bleiben die Prompt-Logprobs bit-identisch (`-3.154554`, `-5.3268757`, …),
  während der Logprob des generierten Tokens im selben Response von
  `−0,998` auf `−0,236` springt — der Bias greift also erst in der
  Generierung.
- **Token-Ids fehlen zusätzlich:** `return_tokens_as_token_ids: true` wird
  akzeptiert, liefert aber weiter Strings; `/v1/tokenize` und
  `/v1/models/{model}/tokenize` sind 404 (HTML). Ohne passenden lokalen
  Qwen-Tokenizer gibt es also keine Keys für `logit_bias`.
- **Erzwungene Fortsetzung** funktioniert und ist exakt: `prompt = Präfix +
  Kandidat` liefert `p(Kandidat | Präfix)` in `token_logprobs` (Wegwerftest:
  `p(" früh" | …) = −0,9984`, drei Wege identisch). Damit lässt sich jeder
  **benannte** Kandidat exakt bewerten — aber Ränge 6+ lassen sich so nicht
  *enumerieren*, weil man die Kandidaten vorher kennen muss.

Selbst wenn all das ginge, wären es **5 Requests pro Satz** (5 × Input-Tokens
= 1,8–6,8 $ pro 150k und 5 × Laufzeit) für genau die Breite, die Chutes in
einem Request liefert.

**Warum es trotzdem nicht reicht.** 5 < 10. §1 verlangt ≥10, ideal 16–24;
das Rezept trainiert `topk=24`. An den vorhandenen Top-24-Zielen gemessen
(`artifacts/out/audit_soft.json`, `audit_signal.json`, 2M-Zeilen):

| Größe | Wert |
|---|---|
| Kandidaten pro Zeile | Mittel **16,79**, p10 = 8 |
| Zeilen mit ≤5 Kandidaten | **5,19 %** (≤3: 2,54 %) |
| Trefferquote des echten nächsten Worts (Wort-Ebene) | top-1 **20,6 %**, top-8 **48,2 %**, top-24 **81,7 %** |
| Masse in den Zeilen | **0,906** im Mittel (5 breit: 0,755) |

Ein 5-weiter Lehrer drückt also **jede** Zeile auf das Niveau der heutigen
Ausnahmefälle (≤5 Kandidaten) und verliert gemessen rund **15 Prozentpunkte**
der Lehrer-Masse pro Zeile. Dazu kommt, dass ≤3-Kandidaten-Zeilen heute
**wie eine 24-Kandidaten-Zeile** gewichtet werden — genau der Defekt, den
`plans/teacher-free-plan.md` §1 reparieren will; ein 5-weiter Lehrer würde
ihn auf alle Zeilen ausdehnen. Und Together hat weiterhin **kein Base-Qwen**
im Serverless-Katalog (die Modelle sind post-trained), also den falschen
Verteilungstyp für eine Destillation.

**Verdikt:** Request-Form bestätigt brauchbar, Anbieter nicht. Together ist
damit in derselben Klasse wie Fireworks/OpenAI/Novita („nur mit `topk<=5`
denkbar, nicht empfohlen“) und ersetzt weder Chutes (20) noch Nebius noch
die GPU. Nützlich bleibt es als billigster 5-weitiger Test (0,36–1,35 $ pro
150k), falls je eine `topk<=5`-Schülervariante untersucht wird. Die Probes
sind darauf eingestellt: `--top-n 5` (Together-Maximum) und `--min-top 10`
(Projektanforderung, damit ein korrektes 5-weites Ergebnis ehrlich `FAIL`
meldet); `--min-top 5` zeigt die Obergrenze als `PASS`. Die Variante
„5 Alternativen + echtes Token, per Array-Batch gesammelt“ steht in §2c.

## 2c. Ist Together als Lehrer trotzdem nutzbar? (5 Alternativen + echtes Token)

Der entscheidende Unterschied zu DeepInfra & Co.: `echo` bewertet **jedes**
Prompt-Token. Damit ist `p(echtes Token | Präfix)` für **100 % der Positionen**
exakt bekannt — auch wenn das echte Token nicht unter den Top-5 ist. Die
vorhandenen top-24-Ziele decken das echte Wort nur zu **81,7 %**.

Gemessen (20 Sätze, 216 Positionen, Satz für Satz):

| Größe | Wert |
|---|---|
| Masse in den Top-5 | **0,6214** (langer Kontext: 0,755) |
| echtes Token unter den Top-5 | 0,611 |
| `p(echtes Token)`, exakt | **0,2631** im Mittel, 100 % Abdeckung |
| Masse Top-5 + echtes Token (6 Slots) | **0,6249** — der Zusatz bringt fast keine Masse (außerhalb der Top-5 ist `p(true)` nur 0,0092) |
| unmodellierter Rest | **0,375** (bei top-24: 0,094) |

Durchsatz und Kosten (`prompt` als **Array**, gemessen):

| Batch | Antwort | Zeit | Sätze/s |
|---:|---:|---:|---:|
| 1 | 1 choice | 0,19 s | 5 |
| 20 | 20 | 0,25 s | 80 |
| 80 | 80 | 0,44 s | 181 |
| 200 | 200 | 0,77 s | 261 |
| 1000 | 1000 | 2,01 s | **498** |

Das sind **~5 Minuten für 150k Sätze** (2M ≈ 1 h) und **0,31 $** bzw. **4,08 $**
Input-Kosten bei Qwen3.5-9B — gegen 12 h lokale 4B-Base und ~4,8 Tage bei
Chutes. Ausrichtung geprüft: `choices[i].index == i`, und
`choices[i].logprobs.tokens` sind genau die Tokens des i-ten Prompts
(30er-Batch: 0 Abweichungen). Rate-Limit-Header schickt Together keine mit.

**Was dafür am Ziel geändert werden muss:**

- Zielarray **6 Slots**: die 5 Alternativen + das echte Token (falls nicht
  enthalten), pro Zeile **nicht** renormalisiert, plus `covered_mass` als
  Spalte. Der Leser kann variable Breite schon (`share_le5` 5,19 % der
  heutigen Zeilen).
- KD-Gewicht pro Zeile = `covered_mass`. Heute werden ≤3-Kandidaten-Zeilen wie
  24er gewichtet (Defekt aus `plans/teacher-free-plan.md` §1); bei 5 Breite
  wird das der Regelfall.
- Rest (0,375) entweder ignorieren (wie heute, dann aber 4× so groß) oder als
  „other“-Slot mit Unigram-Masse füllen — die V8-Reparatur greift bereits.
- Ungelöst bleiben: 15,3 % Piece-Zeilen (top-24-Recall dort **0,0**, bei 5
  Breite schlechter), 9,4 % leere Zeilen, und der Lehrer ist **post-trained**
  (kein Base-Qwen im Katalog).

**Verdikt:** prinzipiell nutzbar — aber als *eine* von zwei Optionen, nicht als
Ersatz per Dekret. Ob 0,62 gegen 0,91 Masse den Schüler schlechter macht,
beantwortet nur ein A/B: 100k Sätze sammeln (~5 min, 0,21 $), Schüler 3 000
Steps auf `slice100k` (≈38–45 min lokal), Gate wie in
`plans/student-quality-plan.md` (Screen 0,05 nats, Confirm 0,02). Kosten des
A/B: **unter 1 h Rechenzeit, unter 1 €**. Bis dahin bleibt die lokale
4B-Base der Referenzlehrer, Chutes (20 breit) das Ziel, sobald der MTP-Bug
(#53520) draußen ist.

## 3. Anbieter-Matrix

| Anbieter | Prompt-Logprobs | Top-k | Modell / Tokenizer | Preis | Urteil |
|---|---|---|---:|---|---|
| **Chutes** | **ja, OpenAPI** | **20** | Qwen3.8-27B-TEE / Qwen; Qwen3.5-397B / Qwen | 0,039/1,25 $; 0,45/3,00 $ pro 1M | **erste Wahl**; 4–8 Worker, 429-Limit |
| **Nebius Token Factory** | `echo`+`logprobs`; `prompt_logprobs` nur evtl. über `extra_body` | 20? | Qwen3.5-397B / Qwen | 0,60/3,60 $ | zweite Wahl; **60 RPM Basis, ×1,2/15 min bis 20×**; Live-Test offen |
| **Neuralwatt** | **nein** (nur Output-`logprobs`/`top_logprobs`; Chat/Responses, kein `/v1/completions`) | 5? | Qwen3.8-27B (MTP), Qwen3.6-35B | 0,45/3,20 $; flex 0,29/2,08 $ | **für Soft-Targets ungeeignet**; 2–15 Concurrent |
| **ACS Infra** | **ja, `prompt_logprobs: -1`** | **voll** | Llama-8B/405B, Trinity / Llama | frei für Forschung | Approval; Llama-Tokenizer |
| **Cloudflare Workers AI** | Antwortfeld `prompt_logprobs` bei Qwen3-30B; Request-Param unklar | ? | Qwen3-30B, Qwen3.8-27B | 0,05/0,34 $ | sehr zuverlässig, aber unbestätigt |
| **Baseten** | vLLM; `topk_prompt_logprobs` im Sampling-SDK | 20+ | Qwen3.5-4B/9B | H100/GPU-Stunden | zuverlässig, aber Deployment |
| **Scaleway GPU** | vLLM `prompt_logprobs` / `distill.py` | voll | Qwen3.5-9B-Base / Qwen | L4 ~0,79 €/h | zuverlässig, IaaS |
| **Hugging Face TGI** | `details.prefill` | **nur tatsächliches Token?** | beliebig | L4/GPU | Top-k für Prompt unklar |
| Fireworks / OpenAI / Novita | `echo` | **5** | Qwen/Llama/GPT | – | zu sparse |
| Groq / Cerebras / Vertex | – | 5 / kein Prompt | – | – | fällt aus |
| Together | ja auf `/v1/completions` (`echo`) | **5 (harte Grenze)** | Qwen/GPT-OSS | 0,36–1,35 $/150k | 5 breit → für top-24 untauglich; als „5 + echtes Token“-Ziel A/B-würdig (§2c) |
| DeepInfra | `echo` | 1–2 | Qwen/GPT-OSS | – | **live FAIL** |

**Nebius:** Der Completion-Endpunkt hat `extra_body` als freies Feld; das ist
der einzige Weg, `prompt_logprobs` an das vLLM-Backend zu geben. Dokumentiert
ist es nicht, also **Live-Test mit Key nötig**. Rate-Limits: **60 RPM /
400k TPM Basis**, dynamisch **×1,2 pro 15-min-Fenster** bei ≥80 % Auslastung,
maximal **20×** (~1.200 RPM / 8M TPM). Das ist anfangs 1 req/s, wächst aber
nach 2 h auf ~4,3/s und nach 4 h in die Nähe des Maximums. Qwen3.5-397B
(0,60/3,60 $) ist der Qualitätskandidat, Qwen3.8-27B (0,45/3,00 $) der
günstigere. Bei funktionierendem `extra_body` wären 1,2M in ~1,5–2 Tagen
möglich, Kosten ~15 $ (397B) bzw. ~7 $ (27B).

**Neuralwatt:** OpenAI-kompatibel (`https://api.neuralwatt.com/v1`), aber
nur `/v1/chat/completions`, `/v1/messages`, `/v1/responses`; **kein
`/v1/completions`** und **keine Prompt-Logprobs**. Ausgabe-`logprobs`/
`top_logprobs` helfen für Soft-Targets nicht. Concurrency: Trial 2,
Pay-as-you-go 2–10, Pro 10, Max 15; 1M/Min-Token. Qwen3.8-27B ist da
(0,45/3,20 $, flex 0,29/2,08 $), aber für diese Pipeline ungeeignet.

## 3a. Modellwahl bei Chutes (geprüft 29.10.2026)

Nicht jedes Chutes-Modell, dessen generische Doku `prompt_logprobs` nennt,
liefert die Verteilung auch wirklich. Entscheidend sind Backend und
`allow_logprobs` im Live-Katalog:

| Modell | Backend | `allow_logprobs` | Prompt-Logprobs | Tokenizer | Urteil |
|---|---|---|---:|---|---|
| **Qwen3.8-27B-TEE** | **vLLM** | **true** | **ja** | Qwen | **beste nutzbare Wahl** |
| Qwen3.5-397B-A17B-TEE | SGLang | null | **nein** | Qwen | stärker, aber SGLang-OpenAI rechnet keine Prompt-Logprobs |
| Qwen3.6-27B-TEE | SGLang | null | nein | Qwen | älter/teurer als 3.8-27B, dominiert |
| Kimi-K2.6-TEE | vLLM | true | ja | Kimi (nicht Qwen) | Fallback, kein Qwen-Tokenizer |
| Qwen3.8-2.4T-A95B | `chutes` (extern) | null | unklar | Qwen | kein vLLM, keine Metadaten, nicht geeignet |
| Qwen3.8-Max-0902 | `chutes` (extern) | null | unklar | Qwen | extern, keine Metadaten, nicht geeignet |

**Warum Qwen3.5-397B ausfällt:** SGLangs OpenAI-Endpunkt berechnet laut
Quellcode keine Prompt-Logprobs; `echo` + `logprobs` wird ausdrücklich als
inkompatibel behandelt, die Prompt-Verteilung gibt es nur über das native
`/generate` mit `logprob_start_len`. Chutes stellt nur den OpenAI-Gateway
bereit. Der Live-Katalog führt Qwen3.5-397B als `owned_by: sglang` und ohne
`allow_logprobs`; die generische `prompt_logprobs`-Zeile in `llms.txt` ist
irreführend. Zum Testzeitpunkt lieferte ein Live-Test ohne Guthaben ohnehin 402.

**Warum Qwen3.8-27B die bessere Wahl ist:** vLLM, `allow_logprobs: true`,
`prompt_logprobs` 0–20, Qwen-Tokenizer, 262k Kontext, 60 aktive Instanzen,
**0,039/1,25 $** pro 1M. Deutsch: IFEval-de 94,2 % (xhigh), 89,0 % (medium),
83,4 % (off); im deutschen Büro-Test 215/215 Details korrekt, keine
chinesischen Zeichen. Es ist ein post-trained 27B, kein Base-Modell; für
Soft-Targets ist die rohe Completion-Verteilung trotzdem brauchbar. Ein
Base-Qwen gibt es bei Chutes nicht — dafür bleibt ACS (Llama-Base, frei)
oder lokal Qwen3.5-4B-Base.

**Vergleich zum lokalen 4B:** Qwen3.8-27B ist die neuere Generation, 27B
dense statt 4B, und im deutschen Benchmark deutlich stärker. Ob der
Distillationsgewinn den Wechsel rechtfertigt, entscheidet der 100-Satz-A/B;
die 397B ist jedenfalls **kein** nutzbarer Chutes-Lehrer, solange SGLang
keine Prompt-Logprobs liefert.

## 3b. Stabilität im Live-Test (29.10., korrigiert)

**Korrektur:** Ein früherer „100/100“-Lauf war ein **Testfehler**, kein
API-Ergebnis. Das Prüfskript las aus `heldout.tsv` die dritte Spalte („1“)
statt der vierten (Satz) und zählte Fehlversuche als Erfolg. Die Zahl ist
zurückgezogen; der 200-Satz-Lauf lief aus demselben Grund nur gegen den
Prompt „1“ und ist ungültig. Der 500er-Lauf wurde abgebrochen.

**Belastbarer 100-Satz-Lauf (korrekte Spalte, 4 Threads):**

- **Qwen3.8-27B, `/v1/completions`, `prompt_logprobs=20`:** **99/100 OK**,
  98 beim ersten Versuch, 1 nach zwei, 1 blieb nach 3 Versuchen **HTTP 400
  NaN**. Breite 20–21, median 1,80 s, 55 s Wandzeit.
- **Qwen3.8-27B, `/v1/chat/completions` (`reasoning_effort:none`),
  `prompt_logprobs=20`:** **99/100 OK**, 99 beim ersten Versuch, 1×
  **HTTP 502**; Breite 20–21, median 1,86 s, 57 s Wandzeit.
- **Kimi-K2.6, `/v1/completions`, `prompt_logprobs=20`:** **20/20** (10/10
  früher), Breite 20–21, median ~1,2 s, kein NaN. Der frühere Kimi-100/100
  ist dagegen ungültig (derselbe Parse-Fehler).

**Silent-Corruption-Test 27B (29.10., entscheidend):** Zehn Wiederholungen
von `ich will nach Hause gehen und morgen früh` mit `prompt_logprobs=20`:
nur **eine** Antwort war plausibel (` habe`/` bin`/` hab` als Top-1); neun
lieferten fremde Top-Tokens (`mehr`, `ools`, chinesische Tokens). Das echte
` will` lag in der ersten Antwort auf **Rang 70.733** mit Logprob −12,47.
Das ist **HTTP 200 mit falschen Logprobs**, kein NaN. Ein 100-Satz-Lauf
gegen diese API ergab top-1 3,6 % und NLL ≈1e36 — das ist die Korruption,
keine Modellqualität. **Chutes Qwen3.8-27B ist damit als Lehrer unbrauchbar**,
solange MTP nicht deaktiviert oder vLLM auf #53520 gehoben ist. Die
99/100-HTTP-Erfolgsquote sagt nichts über die Korrektheit.

Die früheren 1/10- und 9/10-NaN-Serien waren also **kein Dauerzustand**,
sondern last-/batch-/instanzabhängig. Mit 3 Versuchen bleiben ~1 % Ausfälle;
mit 10 Versuchen sinkt das weiter, aber ein einzelner Prompt kann auch
dauerhaft scheitern. **Wichtig:** Der Bug kann auch **HTTP 200 mit falschen**
Logprobs liefern (siehe §3c); ein reiner Retry/HTTP-Check genügt nicht.

**Fazit:** Qwen-Completions ist mit 2–3 Retries für 1M praktisch nutzbar
(99 %), behält den Qwen-Tokenizer und braucht keinen Chat-Template-Prefix.
Kimi ist der stabile Fallback, hat aber den schlechteren Tokenizer (§3d).
Der 100-Satz-A/B entscheidet; parallel jeden Rückgabevektor validieren.

## 3c. Woher kommen die NaN-Fehler bei Qwen?

Der Fehler ist ein **bekannter vLLM-Bug mit MTP-Speculative-Decoding**, nicht
unser Request und nicht die Modellgewichte:

- vLLM Issue **#53488** (Qwen3.8-27B, MTP, chunked prefill): Der gepolsterte
  MTP-Drafter läuft vor `_bookkeeping_sync()` und überschreibt über den
  gemeinsamen CUDA-Graph-Pool die Hidden States, aus denen
  `prompt_logprobs` berechnet werden. Folge: **falsche** Prompt-Logprobs,
  teils still mit HTTP 200, teils **NaN** und dann HTTP 400 „Out of range
  float values are not JSON compliant: nan“.
- Der Fix ist **PR #53520**: Snapshot der Target-Hidden-States vor dem
  Drafter. Ohne MTP (`--speculative-config` aus) oder mit dem Patch ist der
  Pfad sauber; Generation war nie betroffen, nur `prompt_logprobs`.
- Chutes serviert Qwen3.8-27B (MTP-Head) auf vLLM mit CUDA-Graphs; die
  beobachteten NaN-Schübe passen genau. Retries landen mal auf einem sauberen
  Batch/Instanz, mal nicht. **Empfehlung:** Chutes bitten,
  MTP für Qwen3.8-27B zu deaktivieren oder vLLM auf #53520 zu heben; sonst
  einen eigenen vLLM-Host ohne Speculative Decoding nutzen.
- **Live bestätigt (29.10.):** 9 von 10 Wiederholungen desselben Prompts
  lieferten HTTP 200 mit fremden Top-Tokens; das echte Token lag auf Rang
  70.733. Der 100-Satz-Lauf ergab top-1 3,6 % / NLL 1e36. Das ist die
  stille Korruption, keine Lehrerqualität. Chutes-27B ist so **nicht** als
  Lehrer einsetzbar, bis MTP aus oder vLLM gepatcht ist.
- **Validierung im Collector:** pro Zeile endliche Logprobs, Breite ≥ k,
  tatsächliches Token vorhanden, mittlere NLL plausibel; Ausreißer
  verwerfen/retry. Ein 200er allein beweist keine korrekten Soft-Targets.

## 3d. Kimi-K2.6-Tokenizer: schlechter für Deutsch als Qwen

Kimi K2.6 nutzt `TikTokenTokenizer` (`tiktoken.model`), ein byte-level BPE
mit **163.584 Basistokens + 256 Spezialtokens**. Der Regex ist wortbasiert
(Buchstaben inkl. Umlaute/ß bleiben zusammen), aber die Merges sind
englisch/chinesisch-lastig; deutsche Wörter werden öfter zerteilt.

Gemessen mit `wmlm_token_coverage.py` bzw. demselben `" "+word`-Kriterium
(Typen = distinkte Wörter, gewichtet = laufender Text):

| Tokenizer | `de_150k` Typen | `de_150k` gewichtet | Komposita gewichtet | Schüler-Vokabular | Stücke/Wort |
|---|---:|---:|---:|---:|---:|
| **Qwen3.5-4B / Qwen3.8-27B** | **11,0 %** | **84,6 %** | ~84 % | **23,1 %** | **~2,6–2,8** |
| **Kimi K2.6** | 7,3 % | 59,8 % | 59,4 % | 10,8 % | 3,28 |
| Kimi, Komposita | 2,2 % | 59,4 % | – | – | 3,97 |

Beispiele: Kimi zerlegt `haus` → `ha|us`, `hallo` → `hall|o`,
`straße` → `stra|ße`, `größe` → `gr|ö|ße`; Qwen hält diese Wörter ganz.
Kimi kann zwar **jedes** Wort spellen (byte-level, 100 % Multi-Token), aber
`distill.py` verliert bei jedem zusätzlichen Stück Wahrscheinlichkeitsmasse
und erzeugt mehr Positionen. Der größere Kimi-Vokabular hilft Deutsch
**nicht**; Qwen ist für den Qwen-Schüler klar besser.

**Konsequenz:** Kimis Stabilität ist real, aber der Tokenizer-Nachteil ist
messbar. „Qwen unzuverlässig ⇒ automatisch Kimi“ gilt nicht. Bessere Wege:
Qwen-Chat mit 5–10 Retries (gleicher Tokenizer), oder ein zuverlässiger
Qwen-vLLM-Host (Scaleway/Baseten/Modal) statt Chutes. Kimi nur, wenn der
100-Satz-A/B zeigt, dass die Lehrerqualität den Tokenizer-Verlust schlägt.

## 3e. Retry- und Collect-Plan (im Probe implementiert)

`tools/chutes_echo_probe.py` wiederholt Fehlschläge jetzt automatisch und
macht sie sichtbar:

- **Retry:** `--attempts 5 --backoff 0.5 --backoff-max 20 --jitter 0.25`;
  exponentielle Backoff mit Jitter.
- **Retryable:** HTTP 400 mit `nan`/`out of range float`, 408/409/425/429/
  500/502/503/504, Timeout/Transport, fehlende oder zu schmale
  `prompt_logprobs`, nicht-finite Werte, fehlendes tatsächliches Token,
  `prompt_token_ids`-Längenfehler und mittlere NLL > `--max-nll` (Default
  12, fängt die stille MTP-Korruption).
- **Fatal:** 401/402/403 und andere 4xx; keine sinnlosen Retries.
- **Sichtbarkeit:** jeder Fehlversuch auf `stderr`; am Ende
  `first_try/retried/failed/attempts`; `--failures-out file.jsonl` schreibt
  `{index,prompt,attempts,error}` für einen zweiten Pass; Exit 1 bei
  Restfehlern, 3 bei Totalausfall.
- **Validierung:** Position 0 wird korrekt übersprungen (der alte Probe
  zählte sie als Breite 0), Token-ID-Länge, tatsächliches Token vorhanden,
  Breite ≥ `--min-top`, endliche Logprobs.

**Live 20 Sätze:** 20/20 first try, Breite 20–21, median 1,87 s. **Self-Test:**
zwei simulierte 400-NaN, dann 200 → automatisch Versuch 3; dauerhafter
400-NaN nach 2 Versuchen wird als Fehler geloggt.

**1M-Plan:**

1. **Pass 1:** 16 Worker, `attempts=3`, Validierung, Checkpoint-JSONL pro
   Prompt-ID; bereits geschriebene IDs überspringen.
2. **Pass 2:** nur `failures.jsonl`, `attempts=10`, optional Chat-Fallback
   gegen den MTP-Bug.
3. **Pass 3:** verbleibende IDs an Kimi/ACS oder mit Grund verwerfen.
4. 100k-Shards, `Retry-After` respektieren, 16/32-Thread-Durchsatz messen;
   Kosten steigen durch Retries nur um ~1–2 %.

Der 1M-Collector (`distill_api.py`) ist noch nicht gebaut; der Probe ist
serial und für 20–100 Sätze gedacht. Die Retry-/Validierungslogik ist die
Vorlage dafür.

## 4. Kosten für 1M Sätze

Annahme: ~20 Input-Tokens/Satz, `max_tokens=1` (1 Output-Token), 10–20 %
Retries. 1M Sätze = 20M Input + 1M Output.

| Anbieter/Modell | Input | Output | Summe |
|---|---:|---:|---:|
| Chutes Qwen3.8-27B | 0,78 $ | 1,25 $ | **2,03 $** |
| Chutes Qwen3.5-397B | 9,00 $ | 3,00 $ | **12,00 $** (SGLang: **keine** Prompt-Logprobs) |
| Nebius Qwen3.5-397B | 12,00 $ | 3,60 $ | **15,60 $** |
| ACS Llama-405B | 0 | 0 | **0 $** (Approval, Rate-Limit) |
| Scaleway L4, Qwen3.5-9B | – | – | **~8 €** (10 h × 0,79 €) |

Bei 25 Tokens/Satz steigt Chutes 27B auf ~2,4 $, 397B auf ~14 $.
Selbst mit dreifachem Retry bleibt Chutes 27B unter 7 $.

### 4a. Mehr als 1M Sätze

Der aktuelle Korpus hat **1.784.711 Sätze**. Bei gleicher Annahme
(20 Input-Tokens, 1 Output):

| Sätze | Input | Output | Chutes 27B | 8 Worker/Retries | 4 Worker sauber |
|---:|---:|---:|---:|---:|---:|
| 1M | 20,0M | 1M | 2,03 $ | ~4,8 Tage | ~6,6 Tage |
| **1,2M (1M + 200k Chat)** | **24,0M** | **1,2M** | **2,44 $** | **~5,8 Tage** | **~7,9 Tage** |
| 1,78M | 35,6M | 1,78M | **3,62 $** | ~8,6 Tage | ~11,7 Tage |
| 2,0M | 40,0M | 2,0M | 4,06 $ | ~9,6 Tage | ~13,2 Tage |
| 2,2M | 44,0M | 2,2M | 4,47 $ | ~10,6 Tage | ~14,5 Tage |

16/32-Worker-Bursts sind **kein sustained Betrieb** (16 mit Retries: 0/100
wegen 429); Details §5. Soft-Targets: ~0,78 GB pro 1M, also ~0,94 GB bei
1,2M.

**Entscheidung 29.10.: 1M Basis + 200k Chat = 1,2M.** Basis stratifiziert
440k Tatoeba + 560k News; +200k aus dem Tatoeba-Rest (oder OpenSubtitles,
falls das Chat-Heldout es verlangt). Ergebnis 640k Chat / 560k News
(53/47), 1,2M Soft-Targets. Der Schüler braucht für 30k Steps weiterhin
~6,3 h (1,2M ≈ 6,4 Epochen bei batch 256); 50k Steps ~10,5 h, falls der
Val-Loss nicht sättigt. 1,78M nur, wenn 1,2M noch deutlich gewinnt.

## 5. Laufzeit und Concurrency (gemessen 29.10.)

Chutes limitiert **nicht nur die Threads, sondern die Request-Rate**. Gemessen
mit `tools/chutes_concurrency.py`, 100–300 Sätze, Qwen3.8-27B,
`prompt_logprobs=20`, ohne/mit Retries:

| Worker | OK (300) | Durchsatz | 429 | NaN | Urteil |
|---:|---:|---:|---:|---:|---|
| 1 | – | 0,40/s | 0 | 2/100 | serial |
| 2 | – | 0,80/s | 0 | 0/100 | sauber |
| **4** | **296/300** | **1,75/s** | **0** | 4 | **sicher sustained** |
| 6 | 259/300 | 2,25/s | 0 | **40** | kein Sweetspot |
| **8** | **299/300 mit 3 Retries** | **2,40/s** | absorbed | 46 Retries, 1 Fail | **praktikables Maximum** |
| 16 | 0/100 mit 4 Retries | 0 | **hart** | – | **nicht sustained** |
| 32 | 96/100 (Burst) | 11,7/s | 4 | 0 | nur Burst, danach 429 |

Der 16er/32er-Burst ist eine **Token-Bucket-Illusion**: Nach ~600 schnellen
Requests folgt eine 429-Welle; 16 Worker mit Retries lieferten **0/100**.
8 Worker mit 3 Retries sind der beste sustained Punkt (99,7 % final, 2,40/s);
4 Worker sind sauber, aber langsamer (1,75/s). 16/32 sind für 1,2M unbrauchbar.

**1,2M-Laufzeit:** bei 8 Workern/Retries **~5,8 Tage**, bei 4 Workern
**~7,9 Tage** — nicht 1–2 Tage. 1,78M wären ~8,6 bzw. ~11,7 Tage. Damit ist
Chutes bei den aktuellen Limits **nicht schneller als der lokale 4B**
(1,2M ≈ 4,4 Tage), nur billiger und mit besserem Lehrer. Für <4 Tage braucht
es eine Rate-Limit-Erhöhung bei Chutes (Support/Plan), einen anderen
Anbieter (Nebius/ACS) oder eine dedizierte GPU.

## 6. Empfehlung

1. **Chutes Qwen3.8-27B-TEE** für den 1M-Lauf: gleiche Tokenizer-Familie,
   starkes Deutsch, 20 Top-k, TEE, ~2–3 $. Key bei `chutes.ai` anlegen
   (Google/GitHub/Benutzername), `cpk_`-Key nach
   `C:\Users\saenta\chutesai.key` (nicht ins Repo). Kein Free-Tier, keine
   Mindestbindung.
2. **Nebius** als zweite Wahl, falls Chutes-Latenz/Verfügbarkeit nicht
   reicht: Qwen3.5-397B, 0,60/3,60 $, 1 $ Testguthaben, 25 $ Builder-Credit;
   `prompt_logprobs` über `extra_body` testen, da nicht dokumentiert.
3. **ACS Infra** nur, wenn 0 € und volle Verteilung wichtiger sind als der
   Qwen-Tokenizer: Llama-405B, `prompt_logprobs: -1`, Approval; Top-k ohne
   Prompt-Längen-Cap, 600 Requests/min.
4. **Cloudflare** testen, wenn ein Account vorhanden ist: sehr zuverlässig
   und billig, aber der Request-Parameter für `prompt_logprobs` ist nicht
   dokumentiert.

## 7. Nächster Test

```powershell
# Key außerhalb des Repos, niemals committen
python wmk-glide\tools\chutes_echo_probe.py `
  --key-file C:\Users\saenta\chutesai.key `
  --model Qwen/Qwen3.8-27B-TEE `
  --top-n 20 --min-top 10 --sentences 20
```

`PASS` nur, wenn **jede** Prompt-Position ≥ 10 Alternativen hat. Danach
100 Sätze aus `wmk-glide/artifacts/data/heldout.tsv` gegen den lokalen Lauf
A/B messen (`topk=20`, Qwen-Tokenizer) und erst dann `distill_api.py` für
1M bauen. Die Probe ist read-only und sendet nur die 20 Beispielsätze.

## 8. Grenzen

- Chutes ist ein dezentrales Netzwerk (Bittensor SN64); TEE und 60 Instanzen
  sprechen für Verfügbarkeit, aber es ist kein Major-Cloud-SLA. Retries und
  ein Failover-Modell einplanen.
- Die 20 Beispielsätze sind kein A/B; sie prüfen nur die API-Form.
- `prompt_logprobs` liefert pro Position die Top-k; Position 0 ist `None`.
  Für `distill.py` zählt die Token-ID-zu-Text-Zuordnung, nicht nur der
  Logprob-Wert.
- Keine Keys, keine Prompts und keine Nutzerdaten ins Repo.
