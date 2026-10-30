# Prompt für die nächste Session: Scaleway-H100-1,2M-Lauf

Du übernimmst die deutsche WMLM-Arbeit im wmkeyboard-Fork. Dein Ziel ist,
den 1,2M-Soft-Target-Lauf auf **einer Scaleway H100 80 GB** autonom
vorzubereiten und nach Erhalt der Zugangsdaten auszuführen. Arbeite
messend, checkpointend und kostenbewusst; keine unbelegten Annahmen.

## Zuerst lesen

1. `wmk-glide/HANDOFF.md`
2. `wmk-glide/state.md` §2.7
3. `wmk-glide/wmlm-training-plan.md` (besonders §1.3, §4, §4.3, §7)
4. `wmk-glide/kb-teacher-models.md` (Base-Verifikation, Qwen3.8-27B, H100)
5. `wmk-glide/kb-inference-providers.md` (Chutes-MTP, Retry/Validierung)
6. `wmk-glide/artifacts/README.md`
7. `wmk-glide/h100-cloud-init.yaml`
8. `wmk-glide/cloud/scaleway/README.md` (in dieser Session anzulegen)

Arbeitsort: `G:\C0ding\git\wmkeyboard-wmlm`, Branch
`wmlm-de-research`. Falls die Session in einem anderen Worktree läuft:
zuerst den im Prompt genannten Pfad prüfen; die Artefakte liegen dort.

## Gewählte Instanz (fix)

- **H100-1-80G**, Availability Zone **PAR2 / `fr-par-2`**.
- **Ubuntu Noble GPU OS 13 (Nvidia)**, 80 GB VRAM, 24 vCPU, 240 GB RAM,
  bis 10 Gbps.
- **125 GB Block Storage** + **3.000 GB Scratch**; ca. **2,88775 €/h**
  (Instanz 2,8665 + Block/Flexible IP).
- NVIDIA-Treiber/CUDA sind im GPU-OS vorinstalliert; **keine** normalen
  `apt`-NVIDIA-Treiber nachinstallieren. Zuerst `nvidia-smi`/`nvcc`
  prüfen. Bei CUDA-13-Image lieber das **vLLM-Docker-Image** nehmen, wenn
  der pip-Wheel nicht passt.
- **Scratch ist ephemer**: HF-Cache/Modelle/temporäre Soft-Targets nach
  `/scratch`; finale Checksummen/Soft-Targets/Ergebnisse nach `/data`
  (Block) oder Object Storage. Vor dem Stoppen alles Finale vom Scratch
  auf Block/Remote kopieren.
- 125 GB Block reichen für FP8 (~28 GB) + BF16 (~55 GB) + Soft-Targets
  (1,2M ~0,94 GB / 2M ~1,56 GB) + Repo/Checkpoints, wenn der HF-Cache
  auf Scratch liegt. 2M-Korpus/Prep passt bequem in 240 GB RAM.
- Image-UUID/Zone mit `scw instance image list zone=fr-par-2` verifizieren;
  keine andere GPU/Zone ohne Rückfrage.

## Ausgangslage (nicht neu entscheiden)

- Deutsches `de_context.wmlm`: d256/6/768, 10,86 MB, 77,40/83,42 auf 150k,
  78,48/84,85 mit 441k Komposita, 0,5/5,0; App/Harness-Gap geschlossen.
- Korpus bereits gebaut:
  `wmk-glide/artifacts/corpora/de_1m_200k_chat.tsv`,
  **1.200.000 Zeilen**, 640k Tatoeba/Chat + 560k News (53,3/46,7),
  0 Heldout-Leaks, SHA256
  `882cdd3137d071e1684dda79b746377caead6fb9a2d5c20690a2a0c20d8f9976`.
- **Zusätzlich 2M-Datensatz vorbereiten** (ohne GPU, vor dem H100-Start):
  Ziel **2.000.000 eindeutige Zeilen**, Gewichtung wie bisher
  **53,3 % Chat / 46,7 % News** (1.066k / 934k). Der vorhandene
  `de_all.tsv` hat nur **1.784.711** Zeilen; für 2M ist eine zusätzliche
  lizenzierte Chat-Quelle nötig (z. B. OpenSubtitles DE, ~282k Zeilen).
  **Nicht duplizieren.** Wenn keine zusätzliche Quelle verfügbar ist:
  maximal eindeutige 1,78M bauen, Ist-Zahlen/SHA melden und den 2M-Wunsch
  als offen markieren. 2M-Soft-Targets sind wiederverwendbar; später nur
  den Schüler anpassen, nicht den Lehrer erneut laufen lassen.
- Bestehendes 20k-Heldout: `wmk-glide/artifacts/data/heldout.tsv`
  (4 Spalten; Satz in Spalte 4). Aus dem Training ausschließen.
- Lehrer-Entscheidung: **Qwen3.8-27B** (BF16 Referenz, FP8 Laufvariante),
  eine H100 80 GB, vLLM, `prompt_logprobs=24`, **MTP/Speculative Decoding
  aus**. Qwen3.5-35B-A3B-Base ist die Base-Referenz; Qwen3.8-27B hat keine
  Base. Base ist **nicht zwingend** (Qwen3-Report, DeepSeek-R1, Gemma 2;
  wmkeyboard-Englisch nutzte Qwen2.5-1.5B Base). Ein student-gemappter
  A/B entscheidet, nicht das Etikett.
- Kein Chutes-27B (silent corruption), kein GGUF/llama.cpp
  (keine Prompt-Logprobs), kein MLX (Apple-only).

## Harte Randbedingungen

- **Keine Secrets ins Repo.** Zugangsdaten nur aus einer Datei außerhalb
  des Repos, z. B. `C:\Users\saenta\.scw\wmlm-h100.env` (gitignored).
- **Kein Commit/Push** ohne ausdrückliche Aufforderung.
- **Kostenkontrolle:** H100 80 GB ≈ 2,8665 €/h, per Minute. Nach jedem
  Phase-Gate Instanz stoppen; Block-Volume nur so lange wie nötig.
  Standard-Stop bei `MAX_BUDGET_EUR` (Default 50 €) und bei >12 h Laufzeit
  ohne Gate; dann berichten, nicht weiterlaufen.
- **Keine destruktiven Aktionen** (Volume löschen, Instanz neu erstellen,
  Daten überschreiben) ohne Rückfrage.
- **MTP aus:** `--speculative-config` nicht setzen bzw. deaktivieren.
  `prompt_logprobs` muss an jeder Position plausibel sein.
- **Retry/Validierung:** 400 NaN, 429, 5xx, Timeout, fehlende/zu schmale
  Logprobs, nicht-finite Werte, fehlendes tatsächliches Token und mittlere
  NLL > 12 sind retryable. 401/402/403 sind fatal. Jede Zeile validieren;
  HTTP 200 ist kein Beweis für korrekte Soft-Targets.

## Scaleway-Doku live lesen

Lies vor dem Bauen die aktuellen Scaleway-Dokumente (nicht raten):
- GPU-Instanzen/H100-1-80G, Image **Ubuntu Noble GPU OS 13 (Nvidia)**,
  NVIDIA-Treiber/CUDA-Version
- Cloud-init (User-Data, `#cloud-config`, SSH-Keys)
- Block Storage 125 GB / Scratch 3 TB, Mount-Pfad, Snapshot, Löschen
- Security Groups/Firewall, öffentliche IP, SSH
- Scaleway CLI `scw` und API (Instanz starten/stoppen, Preise, Zone)
- Availability Zone **PAR2 / `fr-par-2`** und H100-Verfügbarkeit
- Preise/Preis pro Minute und Abbuchung (≈2,88775 €/h)

Dokumentiere die verwendeten Links und die tatsächlich gewählte
Image-ID/Zone in `cloud/scaleway/README.md`. Wenn H100-1-80G in der Zone
nicht verfügbar ist, stoppe und berichte; nicht auf eine andere GPU
ausweichen, ohne zu fragen.

## Credentials, die du vom Nutzer brauchst

Lege eine Vorlage `cloud/scaleway/credentials.example.env` an. Der Nutzer
füllt später **eine** Datei außerhalb des Repos:

```dotenv
SCW_ACCESS_KEY=
SCW_SECRET_KEY=
SCW_DEFAULT_PROJECT_ID=
SCW_DEFAULT_ZONE=fr-par-2
SCW_INSTANCE_TYPE=H100-1-80G
SCW_IMAGE_NAME=Ubuntu Noble GPU OS 13 (Nvidia)
SCW_INSTANCE_ID=
SCW_INSTANCE_IP=
SCW_SSH_USER=root
SCW_SSH_KEY_PATH=C:\Users\saenta\.ssh\id_ed25519
MAX_BUDGET_EUR=50
HF_TOKEN=            # optional; Qwen ist öffentlich
```

Ohne diese Werte: alles vorbereiten, dann **stoppen und genau diese Liste
anfordern**. Keine Platzhalter erfinden, keine Keys in Prompts/Logs
schreiben.

Wenn noch **keine Instanz existiert**, darfst du sie mit dem
Scaleway-CLI/API aus Access-Key/Secret/Project/Zone selbst anlegen —
aber nur **H100-1-80G**, nur in der verfügbaren Zone, und erst nach
Bestätigung von Preis/Zone durch den Nutzer. Keine andere GPU als
Ausweichlösung.

## Aufgaben

### 1. Scaffold und Skripte

Lege unter `wmk-glide/cloud/scaleway/` an:

- `README.md` — Runbook, Doku-Links, Image/Zone, Kosten, Credential-Felder.
- `credentials.example.env` — obige Vorlage, keine echten Werte.
- `.gitignore` — `credentials.env`, `*.key`, `*.pem`, `data/`, `out/`.
- `cloud-init.yaml` — minimal, secret-frei: `tmux`, `htop`, `git`,
  `curl`, `rsync`, `python3-venv`, `HF_HOME=/data/hf-cache`, Verzeichnisse.
  Kein vLLM/CUDA-Install, kein Modelldownload, kein Auto-Format.
- `setup_h100.sh` — prüft `nvidia-smi`, Disk, CUDA; legt venv an;
  installiert `vllm`, `hf_transfer`, `transformers`; lädt das gewählte
  Qwen-Modell nach `/data/models`; schreibt `env.sh`.
- `prepare_2m.py` (oder erweitertes `mix_chat_corpus.py`) — baut den
  **2M-Datensatz** lokal/CPU: alle vorhandenen Quellen (Tatoeba, News,
  zusätzlich lizenzierte Chat-Quelle), 53,3/46,7-Gewichtung, Dedup,
  Heldout-Ausschluss, Manifest/SHA, `corpora/de_2m_mix.tsv`. Bei fehlender
  Quelle nicht duplizieren, sondern Ist-Stand melden.
- `benchmark_quick.py` — **erster kurzer Durchsatztest**. Nur
  Qwen3.8-27B-FP8, vLLM offline, `prompt_logprobs=24`, `max_tokens=1`,
  Batch 32, 1 Warmup-Batch, dann 100–200 Prompts; misst Prompts/s,
  Tokens/s, Latenz und grobe Plausibilität. Keine BF16-/35B-Läufe, keine
  Qualitätsbewertung. Ziel: in **1–2 Minuten Messung** nach dem Modell-Load
  entscheiden, ob die H100 überhaupt schnell genug ist.
- `benchmark_prompt_logprobs.py` — 100 Chat-/News-Sätze, BF16 und FP8,
  `/v1/completions` oder vLLM offline, `prompt_logprobs=24`; misst
  Prompts/s, Tokens/s, Latenz, Top-k-Breite, tatsächliches Token/Rang/NLL;
  prüft MTP/Plausibilität; schreibt JSON.
- `distill_vllm.py` — vLLM-Offline-Collector. Muss dieselben `.npz`-Chunks
  wie `tools/wmlm/distill.py` erzeugen (Student-Vokabular, `topk=24`,
  `multi=1`), damit `merge_soft.py`/`train.py` unverändert funktionieren.
  Sharding, Checkpoint pro Zeile/Shard, Resume per Prompt-ID, Failure-JSONL,
  Retry/Backoff, Validierung. Kein Chat-Template; Roh-Prompt.
- `run_distill_1m2.sh` — 1,2M in Shards, 1. Pass `attempts=3`,
  2. Pass nur Failures `attempts=10`; Merge + `check_soft.py`.
- `prep_train_eval.sh` — `prep.py` auf dem 1,2M-Korpus, 30k Schüler-Steps,
  Export, `typing_eval`, Glide-Messung; Resume-fähig.
- `transfer.sh` — Korpus/Modelle hochladen, Ergebnisse/Checksummen
  herunterladen; `rsync`/Object Storage; keine Secrets in Logs.

Wiederverwenden: `tools/wmlm/distill.py`, `distill_multi.py`,
`merge_soft.py`, `check_soft.py`, `prep.py`, `train.py`, `export.py`,
`merge_soft.py`. Prüfe vor dem Bau, ob ein vLLM-Backend in `distill.py`
sauber ergänzt werden kann, statt Logik zu duplizieren.

### 1b. Phase -1: 2M-Datensatz vorbereiten (ohne GPU)

Vor dem H100-Start, unabhängig vom Benchmark:

1. Vorhandene Quellen prüfen: `corpora/de_all.tsv` (1.784.711 Zeilen),
   Tatoeba/News, plus eine **lizenzierte Chat-Quelle** (z. B. OpenSubtitles
   DE) für die fehlenden ~282k Zeilen. **Nicht duplizieren.**
2. Ziel: **2.000.000 eindeutige Zeilen**, **53,3 % Chat / 46,7 % News**
   (1.066k / 934k); alle Quellen, gleiche Gewichtung wie bisher.
3. Dedup, bestehendes 20k-Heldout ausschließen, Manifest + SHA256,
   `corpora/de_2m_mix.tsv`; `de_1m_200k_chat.tsv` bleibt erhalten.
4. Optional `prep.py` auf 2M nach `out/de_lm_2m`; keine Soft-Targets vor
   dem Quick-Gate.
5. Verifizieren: Zeilen, Registeranteile, 0 Heldout-Leaks, eindeutige Texte.
6. Wenn keine zusätzliche Quelle verfügbar ist: maximal eindeutige 1,78M
   bauen, Ist-Stand/SHA melden, 2M als offen markieren; nicht auffüllen.

### 2. Phase 0a: Kurzer Durchsatztest (zuerst, so kurz wie sinnvoll)

1. Instanz: H100-1-80G, PAR2 (`fr-par-2`), Ubuntu Noble GPU OS 13 (Nvidia), Cloud-init optional.
2. Nur **Qwen3.8-27B-FP8** laden (28 GB, nicht BF16); `setup_h100.sh`.
3. `benchmark_quick.py`: 1 Warmup-Batch, dann **100–200 Prompts**,
   Batch 32, `prompt_logprobs=24`, `max_tokens=1`, vLLM offline.
   Messung **60 s** (oder 100 Prompts), keine Chat-Template-/Qualitätsläufe.
4. Gate: **≥35 Prompts/s sustained**; Ziel 100+. Bei <35 sofort stoppen,
   Kosten/Alternative berichten; keine 100-Satz-/BF16-Läufe mehr.
5. Bei ≥35: grobe Plausibilität prüfen (tatsächliches Token/Rang/NLL,
   keine 200er-Korruption), dann Phase 0b.
6. **Datensatzwahl:** Bei **≥100 Prompts/s** und projiziertem 2M-Lauf
   **<6 h / <20 €** direkt den vorbereiteten **2M-Datensatz** nehmen
   (einmal groß destillieren, später nur Schüler anpassen). Bei 35–100
   Prompts/s den **1,2M-Datensatz** nehmen. Bei <35 stoppen.

Der kurze Test ist **nicht** der volle A/B: Er beantwortet nur, ob sich
die H100 für 1,2M/2M überhaupt lohnt. Modell-Download/Load dominieren die
Wandzeit; die Messung selbst bleibt bei ~1–2 Minuten. Instanz danach
stoppen, wenn Phase 0b nicht direkt folgt.

### 2b. Phase 0b: 100-Satz-A/B (nur nach Quick-Gate)

1. Qwen3.8-27B FP8 (und BF16 als Referenz) laden.
2. 100 Sätze Chat + 100 News: BF16 vs FP8, topk=24, MTP aus.
3. Top-k-Breite, tatsächliches Token/Rang/NLL, Durchsatz.
4. Kosten/Zeit für 1,2M hochrechnen; bei >10 h oder >Budget stoppen.
5. Instanz stoppen.

### 3. Phase 1: 100-Satz-A/B

- Qwen3.8-27B BF16 vs FP8 vs Qwen3.5-35B-A3B-Base (falls Zeit/Budget).
- Top-1/Top-8/NLL auf Chat/News; Student-Mapping.
- Entscheide BF16 vs FP8 und ob 27B den Base-Lehrer schlägt.

### 4. Phase 2: 10k-Soft-Target-A/B

- 10k Sätze, topk=24, multi=1, Retry/Validierung.
- Schüler 3k–5k Steps auf denselben Daten; Heldout-Verlust,
  `typing_eval`/Glide.
- Nur bei klarem Gewinn (~>0,3 top-1) den 1,2M/2M-Lauf starten.

### 5. Phase 3: 1,2M- oder 2M-Lauf

- **2M**, wenn Quick-Gate ≥100 Prompts/s und projiziert <6 h/<20 €;
  sonst **1,2M**. Beide Korpora sind vorbereitet, Soft-Targets werden
  wiederverwendet.
- Shards, Checkpoint/Resume, 16 Worker (Benchmark-Ergebnis anpassen),
  Pass 1 `attempts=3`, Pass 2 Failures `attempts=10`.
- Nach jedem Shard: `check_soft.py`, Failure-Zähler, Kosten/Zeit.
- Merge atomar; Soft-Targets validieren.
- Schüler 30k Steps, Export, volle Messung.
- Instanz stoppen, Ergebnisse/Checksummen sichern, Bericht.

## Akzeptanz und Stop

- **Go:** Quick-Gate ≥35 Prompts/s, Logprobs plausibel, 100-Satz-A/B
  positiv, 10k-Schüler-A/B positiv; 2M-Datensatz vorbereitet/validiert
  (oder 1,78M-Ist-Stand dokumentiert, falls keine Quelle).
- **No-Go:** Quick-Gate <35 Prompts/s, >10 h für 1,2M/2M ohne Aussicht,
  >Budget, NLL-Ausreißer/fehlendes Token trotz Retries, H100 nicht
  verfügbar.
- Bei No-Go: stoppen, Zahlen und Alternativen berichten
  (35B-A3B-Base, lokal 9B Q8, Kolibri 4-bit/2×H100).
- **2M:** Wenn der Quick-Gate ≥100 Prompts/s zeigt, den 2M-Lauf nehmen;
  die Soft-Targets sind wiederverwendbar, später nur Schüler anpassen.
- Jede Phase mit Kosten, Dauer, Fehlerraten und Checksummen berichten.
- Keine Commits/Pushes; Änderungen bleiben im Worktree.
