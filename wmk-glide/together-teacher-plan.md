# Together AI als deutscher Lehrer — Audit, Prinzipien, Entscheidung

Stand 2026-11-03. Scope: **nur der Lehrer-Pfad** (kein Schüler-Training, kein
Eingriff in `runs/G6P/90k`). Vorgänger: `kb-inference-providers.md` §1/§2b/§2c,
`wmlm-training-plan.md` §1.7. Skripte: `cloud/together/` (Runbook dort).
Schüler-Stand, gegen den das hier antritt: `cloud/local/STUDENT_V2.md`,
`plans/student-quality-audit.md`, `plans/gate-report.md`.

## 0. Kurzfassung

1. **Together ist als Lehrer nutzbar — aber nicht als top-24-Ersatz.** Der
   Endpunkt liefert **5 Alternativen** pro Position (harte Grenze) plus den
   Logprob des echten Tokens. Repetition, `temperature`/`n`/`seed`/`top_p`,
   `logit_bias`-Runden und Token-Id-Tricks **erweitern die Breite nicht**
   (alles live gemessen, §2).
2. **Was den Ausschlag gibt, ist `echo`:** jedes Prompt-Token wird bewertet,
   also ist `p(echtes Token)` für **100 %** der Positionen exakt bekannt. Das
   repariert genau den Defekt, der die Schüler-Audits dominiert: die 15,3 %
   Piece-Rows, auf denen der Top-24-Lehrer **Masse 0,0** hatte
   (`audit_signal.json`, `kb-student-architecture-de.md` §2).
3. **Betrieblich ist der Pfad extrem billig:** Array-Prompts (1000 pro Request)
   schaffen **498 Sätze/s** → 150k in ~5 min für **0,31 $**, 2M in ~1 h für
   ~4 $, gegen 12 h lokale 4B-Base und ~4,8 Tage Chutes.
4. **Die schmale Breite ist kein Selbstläufer.** Top-k-8-Masse des bisherigen
   Lehrers: 85,1 %; Top-k-4: 69,6 % (`kb-student-architecture-de.md` §2.1).
   Gemessen trägt eine API-Row (Top-5 + echtes Token) **0,62–0,755** Masse.
   Deshalb schreibt der Collector `mass` je Row mit — und die KD-Gewichtung
   nutzt sie.
5. **Entscheidung braucht einen A/B, nicht eine Meinung:** 8-wide
   (Together, mass-gewichtet) gegen 24-wide (bestehender Cache), 3 000 Steps,
   Gate wie `plans/gates.json` (Screen 0,05 nats). Kosten: < 1 h, < 1 €.

## 1. Was am Endpunkt wirklich gilt (live, 03.11.2026)

| Test | Ergebnis | Konsequenz |
|---|---|---|
| `/v1/completions` + `echo: true` + `logprobs: 5` | 200, `top_logprobs` **5/5** an allen nutzbaren Prompt-Positionen, Qwen3.5-9B **und** gpt-oss-120b | der Pfad existiert |
| `logprobs: 20` | **HTTP 400** `Validation error: range [{max:5, min:0}]` | der Befund vom 29.10. („1 Top-Eintrag / 422 / 403“) war eine **ungültige Breite**, kein API-Defekt |
| `top_logprobs`-Reihenfolge | nur 11 von 233 Positionen absteigend, wechselt zwischen identischen Requests | Rang **muss** aus dem Logprob kommen (`together_common.candidates`) |
| gleicher Request mit `temperature` 0/1,2, `n:3`, `seed:42`, `top_p:0,5` | bit-identisch | Wiederholen bringt keine Kandidaten |
| `logit_bias` über 151 000 von ~152 000 Ids auf −100 | Prompt-Logprobs **bit-identisch**, der Logprob des *generierten* Tokens springt −0,998 → −0,236 | Bias wirkt nur in der Generierung → Sperr-Runden (Ränge 6–10) sind unmöglich |
| `/v1/tokenize`, `/v1/models/{m}/tokenize` | 404 (HTML); `logit_bias`-Keys müssen Integer sein; `return_tokens_as_token_ids` wird ignoriert | keine Token-Ids → Mapping nur über Strings (`wordmap.py`) |
| `/v1/chat/completions` | kein Prompt-Logprob-Feld, nur Output-Top-5 | Chat-Pfad geschlossen |
| `prompt` als Array, 1000 Einträge | 200, `choices[i].index == i`, `choices[i].logprobs.tokens` = Tokens des i-ten Prompts (30er-Batch: 0 Abweichungen) | Batching ist der Durchsatzhebel |
| `usage.prompt_tokens` **bei Array-Prompts** | Summe über den Batch, **nicht** pro Choice (erste Client-Version teilte und kürzte damit jeden Prompt: 19/84 Wort-Map-Formen „unaligned“, 3/6 Sätze verworfen) | Prompt-Länge wird **aus der Antwort gemessen** (`client.prompt_len`), `usage` dient nur den Kosten |
| Generierung vs. Echo vs. Top-Liste | für 6 Präfixe **identisch** (Δ 0,00) | die zurückgegebene Prompt-Verteilung ist die echte Modellverteilung (kein MTP-artiger Defekt wie bei Chutes) |

Durchsatz (gemessen): 1 → 5,4 Sätze/s · 20 → 80 · 80 → 181 · 200 → 261 ·
1000 → **498**. Rate-Limit-Header schickt Together keine.

## 2. Warum 5 Alternativen trotzdem tragen können

Sei `S` die zurückgegebene Support-Menge (5 Alternativen + echtes Token),
`M = Σ_{v∈S} p_v` die getragene Masse, `R = 1 − M` der Rest.

**Der Collector rekonstruiert mehr als die Top-5:** für das *echte* Wort wird
`p(w) = ∏ p(token)` über die tatsächlichen Tokens des Wortes gebildet — die
stehen alle in `token_logprobs`, unabhängig von der Top-5-Grenze. Fehlt das
Wort in der Liste (Mapping-Tokenisierung ≠ Stream-Tokenisierung), wird `p(w)`
**injiziert**. Damit hat jede Zeile ein korrektes Ziel für das wahre Wort,
auch wenn dessen erster Token außerhalb der Top-5 lag — das ist der
15,3-%-Piece-Fall, den der Top-24-Cache mit 0,0 bewertet hat.

**Was fehlt, wird sichtbar statt still:** `mass` (= `M`) liegt neben dem npz.
Zwei Verwendungen, beide ohne Retraining-Experiment belegbar:

* **Gewichtung:** `weight = M` (Default `--weight-mode mass`). Eine Zeile, deren
  Kandidaten 40 % der Lehrerverteilung erklären, soll nicht wiegen wie eine mit
  99 %. Das ist das „true per-row tail“-Signal, das
  `plans/student-quality-audit.md:251-255` fordert.
* **Residual-Bucket (Trainer-Erweiterung, nicht in diesem Branch):** mit
  `R` exakt bekannt ist die Zerlegung
  `KL(p‖q) = Σ_{v∈S} p_v log(p_v/q_v) + R · log(R / q_rest)` mit
  `q_rest = 1 − Σ_{v∈S} q_v` — der Bucket ist exakt berechenbar, weil der
  Schüler `q` über sein ganzes Vokabular hat. Genau so rechnet die
  Praxisstudie `arXiv 2608.03796` §3.2 (K=100, **keine** Renormierung,
  Masse `M ≤ 1` wird exakt mitgeführt), und so empfiehlt es die eigene
  Schüler-Audit („residual/OTHER bucket“).
  **Renormieren** (was `train.py`/`train_v2.py` mit `distill_topk>0` tut)
  behauptet stattdessen, der Rest sei null — bei 0,62 Masse ist diese Lüge
  sechsmal so groß wie bei 0,906. Deshalb: `distill_topk=0` und `mass`-Gewicht.

**Temperatur:** `--temperature T` rechnet `p^(1/T)` vor Ranking und
Renormierung (KD-Empfehlung 1,5–2,0, `plans/student-quality-audit.md` §3.2);
`mass` bleibt bewusst die **rohe** Masse, damit das Tail-Signal bei jedem T
dasselbe bedeutet.

**Grenzen, die bleiben** (und im A/B adressiert werden): 15,3 % Piece-Rows
haben jetzt ein echtes Ziel, aber der Lehrer ist **post-trained** (kein
Base-Qwen im Serverless-Katalog), und 8-wide ist schmaler als 24 — beides
kann nur der A/B entscheiden, keine Kennzahl am API-Rand.

## 3. Skript-Audit (was war falsch, was ist behoben)

Der Audit lief über alle Probe-Skripte in `wmk-glide/tools/` (10 Skripte,
~4 Befunde je Skript). Die für den Lehrer-Pfad relevanten Punkte:

| Befund | Ort (vorher) | Status |
|---|---|---|
| **PASS bei halb fehlendem Body:** die Breitenprüfung sah nur *vorhandene* `top_logprobs`-Einträge; ein Body ohne Top-Sets passierte | `tools/deepinfra_echo_probe.py:117-147`, geerbt von Together/Nebius | **behoben**: fehlende Einträge zählen als 0 Alternativen |
| **Crash bei `--min-top 0`** (`max()` auf leerer Liste) | ebd.:145 | **behoben** (`max(1, min_top)`) |
| Chat-Probe meldete **falsches PASS** (Heuristik `len(content) > completion_tokens`) und behauptete `echo` sei dort dokumentiert | `tools/together_chat_probe.py:143-145, :37` | **entfernt**; `probe.py --mode chat` *misst* das Fehlen der Prompt-Logprobs |
| Kein Skript prüfte **Top-1 = Argmax** (der billige Korruptions-Test, der den Chutes-MTP-Bug gefunden hätte) | alle Probes | **neu**: `probe.py`/`token_test.py` berichten `argmax_agreement`; der Collector gated auf `mean_nll` |
| **Keine Retries** außer bei Chutes; `Retry-After` nirgends gelesen | Together/DeepInfra/Nebius | **behoben** in `client.py` (Backoff + Jitter, nur transiente Codes) |
| 4 Kopien des Request-Bodys, 6 Key-Loader mit zwei Präzedenzen, 7 UA-Builder, 4 Exit-Code-Schemata | `tools/*` | **konsolidiert**: `client.py` + ein Exit-Code-Vertrag in `probe.py` |
| Cloudflare-`403 code 1010` wurde nicht erkannt (UA fehlt bei `urllib`-Default) | alle | `client.py` setzt UA; 1010 landet als klare Meldung |
| `merge_soft.py` warf **jede** zusätzliche Per-Row-Spalte weg | `tools/merge_soft.py:36-62` | **behoben**: zusätzliche 1-D-Arrays werden mitgeführt, gemischte Chunks abgelehnt (verifiziert) |
| `check_soft.py` nannte Zeilen-**Coverage** „mass_ratio“, obwohl die KB von Lehrer-**Masse** spricht | `tools/check_soft.py:90-96` | **behoben**: `row_coverage` + `mean_mass`, `mass_ratio` bleibt als Alias |

Nicht angefasst (dokumentierte Schuld, andere Baustelle): `chutes_echo_probe.py`
(überschreibt seine Failure-Datei, `parts[-1]`-Spaltenfehler),
`chutes_concurrency.py` (Erfolgskriterium `max(widths) < 2`, immer Exit 0),
`nebius_echo_probe.py` (kein `--extra-body`, kann seinen eigenen Test nicht
fahren), `wmlm_token_coverage.py` (Div-by-zero, nicht-deterministische
Form-Iteration).

## 4. Was der Collector genau tut (`cloud/together/`)

Pipeline in einem Satz: `prep.py`-Korpus → Prompt-Text je Satz (identisch zu
`distill.py`) → Array-Request → pro Position 5 Alternativen + echtes Token →
String-Mapping (`wordmap.py`, über den Endpunkt selbst gemessen) →
Multi-Token-Kette → wahres Wort exakt + ggf. injiziert → Top-`topk` (8),
renormiert → npz (4 Arrays) + Audit-Sibling (`mass`, `actual`, `actual_p`,
`weight`, `piece`).

Invarianten, die der Collector durchsetzt:

* Zeilen = Wortgruppen des Satzes (Row 0 leer) — `soft_mask.py` verlangt
  exakt diese Zählung.
* `ids ≥ 0`, `ids.shape == probs.shape`, `topk` global, `probs` finit,
  Zeilensumme ≤ 1,001.
* `"".join(tokens) == prompt` je Antwort (Echo-Ausrichtung) — sonst harter
  Fehler statt stiller Verschiebung.
* Shards atomar, `.sha256`, Resume nur bei identischer Member-Liste;
  `run.json` pinnt Korpus-/Vocab-Hashes, Modell, topk, Map, Injection und
  Weight-Modus.
* Ein fehlgeschlagener Chunk lässt den Shard **unwritten** (kein Loch im
  Merge).
* Erwartungswert für die Abdeckung: der 24-wide-Cache lag bei 90,6 % Rows mit
  Masse (9,4 % davon ist allein Row 0). Eine 6-Kandidaten-Row wird häufiger
  leer, weil keiner der Kandidaten ein ganzes Schülerwort ist — deshalb ist
  `--min-mass-ratio` für diesen Collector bewusst ein **expliziter** Parameter
  (z. B. 0,85) und nicht stillschweigend 0,90; leere Rows wiegen ohnehin 0.

Tests: 21 Offline-Unit-Tests + ein End-to-End-Lauf über einen synthetischen
Korpus mit Fake-Transport, der das Ergebnis mit `check_soft.validate_soft`
prüft (inkl. Resume: zweiter Lauf macht **0** Requests). Alle Selbsttests:
`python3 cloud/together/{client,together_common,wordmap,probe,token_test}.py --self-test`.

## 5. Research-Einordnung

| Quelle | Punkt | Konsequenz hier |
|---|---|---|
| `arXiv 2608.03796` (Offline Top-K Logits) | Offline-Cache erreicht Online-Qualität; **nicht** renormieren, `M ≤ 1` exakt mitführen; K=100 | `mass` + Residual-Bucket-Formel; `distill_topk=0` |
| BiLD (COLING 2025) | Top-k beider Seiten filtert Tail-Rauschen, besser als volles KL | 8-wide mit Masse ist kein Nachteil per se |
| „When Top-K Misses the Decision“ (2026) | Top-k allein verfehlt Entscheidungen; Top-p/breitere Kerne nötig | echtes Token immer im Ziel (`actual`/Injection) |
| `kb-student-architecture-de.md` §2 | Piece-Rows erzeugen positiven KD-Gradienten (`p_b = 1−α`), Maskieren/Weights nötig | der Collector liefert für Piece-Rows echte Masse — die Ursache entfällt |
| ebd. §2.1 | Top-k-Masse: k=4 69,6 %, k=8 85,1 %, k=16 97,4 % | 8-wide nur mit `mass`-Gewichtung sinnvoll |
| `plans/student-quality-audit.md:251-255` | Tail-aware KD, Residual/OTHER-Bucket als Standard-Fix | deckungsgleich mit §2 |

## 6. Modell-Katalog: was von 190 Textmodellen wirklich taugt

`GET /v1/models` listet **269 Modelle**, davon 190 Text (`chat`/`language`).
Am 03.11.2026 durchgemessen (`cloud/together/model_ab.py`, 200 A/B-Sätze +
500 Wortformen) — es gibt vier Ausschlussgründe, drei davon im Client
behandelt:

| Blocker | Modelle (gemessen) | Konsequenz |
|---|---|---|
| `Unable to access non-serverless model …` | **alle** `language`-Basismodelle (`Qwen3-{0.6,1.7,4,8,14}B-Base`, `Qwen3-30B-A3B-Base`, `Qwen2{-1.5,7,72}B`, `gemma-3-{1b,27b}-pt`, `Llama-3.2-3B`, `Meta-Llama-3.1-8B`, `Mixtral-8x7B-v0.1`) **und** `Qwen3.5-397B-A17B`, `Qwen3-235B-A22B-Instruct-2507-FP8`, `GLM-4.5-Air-FP8`, `GLM-4.7`, `GLM-5.1`, `GLM-4.6`, `Ministral-3-14B-Instruct`, `Llama-3.3-70B-Instruct-Turbo`, `DeepSeek-V3.1`, `gemma-3-27b-it`, `gemma-4-31B-it`, `Mistral-Small-24B`, `Qwen3-4B-Instruct-2507` | nur mit **dediziertem Deployment** (GPU-Stunden). Damit gilt weiter: **kein Base-Lehrer und kein 397B auf dem Pay-per-Token-Pfad** |
| Datenfreigabe aktiviert, aber **Completions ist chat-only** | `Qwen/Qwen3.8-Flash` | mit neuem Key und allen drei Privacy-Schaltern an: statt 403 jetzt zuerst `only supports streaming`, mit `stream: true` dann `Role must be in ["user","assistant",…]` → **kein Prompt-Scoring**, also keine Prompt-Logprobs. Chat liefert nur Top-1 pro Position |
| Echo wird nicht erfüllt | `zai-org/GLM-5.3-Flash` (Antwort `'\n\n'`), `deepseek-ai/DeepSeek-V4.1-Flash` (Antwort `'?'`) | **keine** Prompt-Logprobs; der Client bricht hart ab („a misaligned row is worse than a missing one“) |
| `batch_prompts_not_supported` bzw. 200 mit nur 1 Choice | `openai/gpt-oss-120b`, `GLM-5.3-Flash` | Client erkennt beide Formen und schaltet auf **Einzel-Prompt** um (String statt Array — auch ein 1-Element-Array wird abgelehnt) |

**Vollständiger Sweep (03.11.2026, `catalog_sweep.py`):** 77 Modelle mit
Preis > 0 (das Serverless-Signal) je eine Echo-Anfrage. Ergebnis: **55
non-serverless**, **7** verweigern Array-Prompts, **7** erfüllen das Echo
nicht, **1** ist chat-only, **7** sonstiges — und **genau ein zusätzliches
Modell ist nutzbar: `zai-org/GLM-5.2`**. Damit sind es **drei**, und das neue
ist das beste gemessene:

| Modell | Breite | NLL ↓ | top-1 ↑ | Masse ↑ | Wort-Rate ↑ | tok/Wort | Preis in/out | Betrieb |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `zai-org/GLM-5.2` | 4–5,5 | **4,327** | **0,358** | **0,638** | 57,8 % | 1,72 | 1,4 / 4,4 | Array, 42 Sätze/s |
| `Qwen/Qwen3.5-9B` | 5–5,5 | 4,527 | 0,296 | 0,544 | **63,5 %** | 1,56 | **0,17 / 0,25** | Array, 121–498 Sätze/s |
| `openai/gpt-oss-120b` | 5–5,7 | 6,124 | 0,177 | 0,376 | 57,8 % | 1,62 | 0,15 / 0,60 | nur Einzel-Prompt |

GLM-5.2 gewinnt auf allen Qualitätsmaßen (NLL, top-1, Masse), kostet aber
**8× mehr pro Token**: 150k Sätze ≈ **2,52 $** statt 0,31 $, 2M ≈ **34 $**
statt 4 $. In absoluten Zahlen bleibt beides billig; die Wahl ist
Qualität gegen Faktor 8 im Preis und Faktor 3 in der Zeit.

Zum Vergleich, **gleiche 200 Sätze**, lokale Base-Lehrer aus
`artifacts/out/ab_3way.json` (Token-NLL, dieselbe Metrik): `Qwen3.5-4B-Base`
**5,24** · `Qwen3.5-9B-Base` **5,03** · `Qwen3.8-27B-FP8` **4,95**. Das
Together-9B liegt mit **4,53** darunter — mit zwei Vorbehalten: es ist
**post-trained** (nicht Base) und seine Tokenisierung ist nicht bitgleich mit
dem lokalen 9B-Base, die Zahlen sind also indikativ, nicht exakt.

**Gibt es ein Modell in der 27B-Klasse?** Im Katalog steht **kein**
`Qwen3.8-27B`. Die 27B-Einträge sind `gemma-3-27b-pt/-it`, `medgemma-27b`,
`gemma-2-27b-it` (alle non-serverless) und
`Prism-ML/Ternary-Bonsai-27B` — das läuft, ist aber mit **NLL/Token 7,505**
und top-1 0,076 deutlich schlechter als das 9B (4,527 / 0,296).
`Qwen/Qwen3.8-2.4T-A95B` liefert kein Echo (`'.'`), `Qwen3.8-Flash` ist
chat-only.

**Qualität tokenizer-unabhängig (bits/Zeichen, 40 Sätze):** `Qwen3.5-9B`
**0,930** · `gpt-oss-120b` **1,214**. Aus `ab_3way.json` lässt sich das für
die lokalen Lehrer **nicht** ausrechnen (keine Zeichenzahlen gespeichert);
mit gleicher Zeichen/Token-Rate ergäbe der 27B-FP8 (NLL/Token 4,95) grob
0,98 — der Together-9B wäre also **nicht schlechter**, nur schmaler
[INFERENCE]. Genau dafür müsste der 27B-Lauf auf Scaleway die Zeichenzahlen
mitschreiben.

Der Streaming-Weg ist im Client eingebaut (`stream: true`, SSE-Stitching in
`parse_sse`, automatischer Retry, wenn ein Modell „only supports streaming“
meldet) — er hat Qwen3.8-Flash nur bis zur chat-only-Grenze gebracht.

**Was daraus folgt:** ein Basismodell ist auf Together nicht zu bekommen
(dediziertes Deployment = GPU-Stunden, also Scaleway-Pfad). Für den
API-Lehrer bleibt `Qwen3.5-9B`; `gpt-oss-120b` ist als Zweitlehrer nur
interessant, wenn man eine 2-Lehrer-Mixtur wollte, und ist pro Satz ~25×
teurer an Zeit (Einzel-Prompt).

## 7. Zwei Lehrer parallel — gemessen, und nur in einer Richtung sinnvoll

Token-Ebene geht nicht (Qwen-BPE vs. o200k), **Wort-Ebene schon**: jedes Modell
bekommt eine eigene Wort-Map, und `p(echtes Wort)` ist bei beiden exakt. Also
ist eine Mischung oder Auswahl pro Zeile möglich (`ensemble_probe.py`,
`distill_together.py --extra-model`).

Messung (`ab_together_ensemble.json`, 40 Sätze, 304 Wort-Rows, 232-Wörter-
Stand-in-Vokabular — absolute Massen sind dadurch niedrig, die Deltas zählen):

| Größe | Qwen3.5-9B | gpt-oss-120b | Mischung / Union |
|---|---:|---:|---:|
| Wort-NLL | **6,517** | 7,399 | **6,445** bei π=0,8 (−0,072) |
| getragene Masse | 0,183 | 0,185 | Union (max): **0,272** (+0,089) |
| Kandidaten-Überlappung | – | – | 86,5 % der Rows, Jaccard 0,59 |
| Rows mit ≥0,10 Massengewinn | – | – | **11,8 %** |

Zwei Schlüsse:

1. **Mischen (blend) bringt fast nichts und kostet Masse.** Der schwächere
   Lehrer (1,21 bits/Zeichen gegen 0,93) zieht jede Zeile nach unten; Wort-NLL
   −1,1 % bei π=0,8, getragene Masse sogar *schlechter* (0,114 gegen 0,125 im
   Live-Smoke).
2. **Auswählen (fill) ist der richtige Modus.** Nur Zeilen, in denen der
   Primärlehrer blind ist, kommen vom Zweitlehrer; Masse im Live-Smoke
   **0,125 → 0,154 (+23 %)**. Das ist genau die Union-by-max-Kopfraum-Zahl, und
   sie kann per Konstruktion nicht schaden.

Kosten: `gpt-oss-120b` nimmt **keine Array-Prompts** (Einzel-Request), ist also
~40× langsamer pro Satz. Deshalb holt der Collector in `fill`-Modus den
Zweitlehrer **nur für die Sätze, die blinde Zeilen haben** (`--fill-below`);
`blend` bräuchte ihn überall und ist damit wirtschaftlich unsinnig
(150k Sätze: 5 min gegen 3–5 h für −1 % NLL).

**Empfehlung:** Primär `Qwen3.5-9B`, Zweitlehrer nur als `fill`
(`--extra-mode fill --fill-below 0.5`). Ein dritter Lehrer wäre genauso
anschließbar; der Grenznutzen fällt mit dem Gewicht des Zweiten schon auf
~1 %.

## 8. Den 2M-Cache ergänzen oder reparieren?

Der bestehende Cache (`de_soft_2m.npz`, 1 979 982 Sätze, 21 378 590 Rows,
top-24, Qwen3.8-27B) hat drei gemessene Löcher (`audit_signal.json` 2m):

| Loch | Umfang | Wirkung im Training |
|---|---:|---|
| Piece-Rows mit Lehrermasse **0,0** | **15,17 %** = 3,24 Mio. Rows (in 75,7 % der Sätze) | KD unterdrückt das richtige Piece-Wort auf `p_b = 1−α` |
| echtes Wort **nicht** in top-24 | 18,3 % = 3,9 Mio. Rows | KD kennt die Wahrheit nicht |
| leere Rows (ohne Row 0) | ~1 % = ~0,2 Mio. Rows | kein KD-Signal |

**Weg A — ergänzen (neue Sätze).** Verifiziert: ein Together-File auf
`--topk 24` gepolstert (6 echte Kandidaten, Rest Nullen) wird von
`merge_soft.py` mit dem 27B-Cache **akzeptiert** (gleiche 4 Keys, gleiches
topk, disjunkte Sentence-IDs) — Test mit synthetischen Chunks gelaufen. Kosten:
150k Sätze ≈ 5 min / 0,31 $ (Qwen) bzw. ~1 h / 2,52 $ (GLM-5.2). Effekt: mehr
Rows eines **schmaleren** Lehrers; mit `weight = mass` automatisch
niedriger gewichtet.
Wichtig: nur **neue** Sätze einspeisen — dieselben Sätze mit einem zweiten
Lehrer zu überschreiben gäbe widersprüchliche Ziele.

**Weg B — reparieren (die blinden Rows).** `patch_soft.py` holt nur die Sätze
mit blinden Rows, behält die 24 Kandidaten des 27B und schreibt das **echte
Wort mit exakter Wahrscheinlichkeit** (aus `echo`, auch mehrteilig) in den
letzten Slot. Breite, Zeilenzahl und Reihenfolge bleiben identisch, das File
bleibt vier Schlüssel; ein Report zählt jede Änderung. Selbsttest plus
Live-Lauf gegen die echte API (14 von 14 geflaggten Rows gepatcht).

```bash
python3 cloud/together/patch_soft.py --data-dir out/de_lm_2m \
    --soft out/de_soft_2m.npz --map out/wordmap_glm52.json \
    --out out/de_soft_2m_patched.npz --model zai-org/GLM-5.2 \
    --report out/de_soft_2m_patched.report.json
```

Kosten für Weg B: nur die betroffenen Sätze (1,50 Mio. von 1,98 Mio.) →
~40 min / ~3 $ mit Qwen3.5-9B, ~10 h / ~25 $ mit GLM-5.2.

**Empfehlung:** **B vor A.** B entfernt den Suppressions-Defekt
(`p_b = 1−α`) an genau den Zeilen, an denen er entsteht, kann per Konstruktion
nicht schaden (es kommt nur die Wahrheit hinzu) und ist mit dem bestehenden
Gate-Vertrag verträglich — der Schüler sieht dieselbe Zielbreite wie bisher.
A ist danach eine reine Mengenfrage und mit `weight = mass` sauber dosiert.

## 9. Preis/Leistung: welcher Mix ist der beste?

Durchsatz bei Array-Prompts (`client.py`, batch 1000, gemessen 04.11.2026):
**Qwen3.5-9B 533 Sätze/s · GLM-5.2 196 Sätze/s** — GLM skaliert sauber mit
dem Batch (32 → 79, 128 → 128, 256 → 172, 1000 → 196 Sätze/s) und verweigert
Arrays **nicht**.

Qualität, gleiche 200 A/B-Sätze, token-NLL pro Klasse:

| Lehrer | chat | news | Mittel | Wort-NLL (Wort-Ebene) |
|---|---:|---:|---:|---:|
| `Qwen3.8-27B-FP8` (vorhanden, GPU) | 5,278 | 4,616 | 4,947 | – |
| `Qwen3.5-9B-Base` (lokal) | 5,244 | 4,816 | 5,030 | – |
| `Qwen3.5-9B` (Together) | **4,596** | 4,497 | 4,546 | 6,97 (chat **6,47**, news 7,24) |
| `GLM-5.2` (Together) | 4,897 | **4,082** | **4,490** | 6,77 (chat 6,74, news **6,78**) |

Wort-Ebene mit beiden Lehrern (`ensemble_probe.py`, 50 chat + 50 news,
1081 Wort-Rows, Stand-in-Vokabular → absolute Werte niedrig, Vergleiche gültig):

| | Qwen | GLM | **Blend** | bestes π | Union-Masse |
|---|---:|---:|---:|---:|---:|
| alle | 6,967 | 6,768 | **6,157** (−11,6 %) | 0,4 | 0,341 statt 0,256 (+33 %) |
| chat | **6,472** | 6,742 | **5,820** (−10,1 %) | 0,5 | 0,328 |
| news | 7,238 | **6,782** | **6,341** (−6,5 %) | 0,4 | 0,348 |

Kandidaten-Überlappung 89,7 % der Rows, Jaccard **0,51** — die beiden Lehrer
widersprechen sich bei der Hälfte der Kandidaten, und genau daraus kommt der
Blend-Gewinn. 16,6 % der Rows gewinnen ≥ 0,10 Masse durch die Vereinigung.

**Kosten und Zeit für 150k Sätze** (12,3 Token/Satz, gemessene Durchsätze):

| Variante | Kosten | Zeit | Qualität |
|---|---:|---:|---|
| Qwen3.5-9B allein | **0,34 $** | 4,7 min | Basis (chat-sieger) |
| GLM-5.2 allein | 3,18 $ | 12,8 min | −2,9 % Wort-NLL, +38 % Masse gegen Qwen |
| Register-Routing (chat→Qwen, news→GLM) | 1,76 $ | 8,7 min | ≈ −4,5 % |
| **Blend π≈0,45 (Qwen+GLM)** | 3,52 $ | 17,5 min | **−11,6 %** |
| Qwen + GLM als `fill` (nur blinde Sätze) | ≈1,9 $ | ≈10 min | +0,085 Masse, kein NLL-Gewinn |

Für 2M Sätze ×13,3: Qwen 4,5 $ / 1 h · GLM 42 $ / 2,8 h · Blend 47 $ / 3,9 h ·
Routing 23 $ / 1,9 h.

**Empfehlung — drei Regeln, nach Ziel:**

1. **Bestehende 2M-Daten reparieren: `patch_soft.py` mit Qwen.** Die Reparatur
   braucht nur die *exakte Wahrscheinlichkeit des echten Worts*, nicht die
   Breite — dafür ist das billigste Modell genug. 1,5 Mio. betroffene Sätze ≈
   **3,4 $ / 47 min**. Das ist der beste Preis/Leistungs-Punkt überhaupt: es
   entfernt den `p_b = 1−α`-Defekt (15,17 % Piece-Rows), ohne Schema, Breite
   oder Gate zu ändern.
2. **Neue Daten, Qualität first: Blend Qwen+GLM bei π≈0,45** (`--extra-model
   zai-org/GLM-5.2 --extra-mode blend --extra-share 0.45`). −11,6 % Wort-NLL
   für 3,5 $/150k; beide Modelle sind gebatcht, also kein Zeitproblem.
3. **Neue Daten, Kosten first: Qwen allein** (0,34 $/150k) **plus GLM als
   `fill`** für blinde Zeilen (≈1,9 $): gleiche Masse wie der Blend, ohne
   NLL-Gewinn. Register-Routing (chat→Qwen, news→GLM; `--only-field`) ist der
   Mittelweg und lohnt nur, wenn man die Klassenzuordnung ohnehin im Korpus
   hat — der Blend ist bei ähnlichem Preis besser.

**Was nicht lohnt:** `gpt-oss-120b` als Partner (nur Einzel-Prompt, 1,21
bits/Zeichen, Blend-Gewinn −1,1 % → Zeitkosten 40×).

## 10. Nächste Schritte (in der Reihenfolge des Gate-Vertrags)

1. **100k-Slice sammeln** (Together, 8-wide, `--weight-mode mass`):
   ~1 min, ~0,21 $. Vorher `wordmap.py` einmal.
2. **Sanity**: `check_soft.py` (Coverage und `mean_mass` getrennt lesen),
   `token_test.py` auf denselben 100 Sätzen wie der bestehende Lehrer.
3. **Screen 3 000 Steps** gegen die 24-wide-Referenz auf `slice100k`
   (`distill_topk=0`, `distill_align` aus `soft_mask.py build`, `alpha` 0,3),
   Gate 0,05 nats (Screen) / 0,02 (Confirm).
4. **Nur bei Grün:** 150k/2M-Pass ziehen (~5 min/~1 h), dann die bestehenden
   Gates G5–G7.

Offen und bewusst nicht hier entschieden: post-trained statt Base (kostet
Authentizität der Verteilung), 8-wide gegen 16-wide (Chutes nach MTP-Fix),
Residual-Bucket im Trainer (Schüler-Branch, Gate-Kette).
