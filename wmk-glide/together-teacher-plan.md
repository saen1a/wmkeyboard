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

## 6. Nächste Schritte (in der Reihenfolge des Gate-Vertrags)

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
