# H100-Lauf 1,2M — Handoff für die nächste Session

Stand: **30.10.2026, 12:35 UTC**. Diese Datei ist das gesamte Wissen der
vorherigen Session. Ziel der nächsten Session: **H100-1-80G in `fr-par-2`
anlegen, sobald verfügbar, und den 1,2M-Prefix destillieren.**
Alles andere ist fertig; nichts läuft, nichts wird abgerechnet.

---

## 0. Status in einem Satz

2M-Korpus gebaut und verifiziert (0 Heldout-Leaks), Toolchain zweimal live
gelaufen (L40S), Lehrer-A/B gemessen (27B schlägt 9B/4B), alle Skripte
auditiert — **offen ist nur der H100-Lauf selbst**, blockiert durch
GPU-Bestand.

| Was | Wert |
|---|---|
| Instanzen/Volumes/IPs offen | **keine** (verifiziert, 12:32) |
| Cron-Jobs | **keine** (gelöscht) |
| Ausgaben bisher | **~2,5 €** von 50 € (Smoke 1,8 € + A/B 0,66 €) |
| Korpus | `wmk-glide/artifacts/corpora/de_2m_mix.tsv`, SHA `a3b7cd04b8b98ecca82d01c3f4bb87ee10969103b249e8c7e2f6770f296fa61c`, 2.000.000 Zeilen, 1.066.000 Chat / 934.000 News, 0 Leaks |
| Prepped | `wmk-glide/artifacts/out/de_lm_2m` (1.980.000 Sätze, 40.556.654 Tokens, Vokabular 24.576) |

---

## 1. Entscheidungen, die stehen (nicht neu aufrollen)

- **Lehrer: Qwen3.8-27B-FP8** auf H100. BF16 nur als Referenzzeile im A/B,
  nie als Laufzeit-Variante (2× langsamer/teurer).
- **1,2M = Prefix des 2M-Korpus** (`TOTAL=1200000` → 240 Shards), **nicht**
  `de_1m_200k_chat.tsv` — das alte 1,2M-File hat 12.368 Heldout-Leaks und ein
  anderes Vokabular.
- **Kein Wikipedia** im Korpus (Nutzerentscheidung).
- **Keine L40S** mehr (Nutzerentscheidung).
- Mischung bleibt 53,3/46,7 (liegt zwischen Eval 44,6/55,4 und
  Mobilnutzung ~60/35; Aioli/Data-Mixing-Laws: stratified sampling schlägt
  Reweighting).

## 2. Gemessene Zahlen (für Berichte, nicht neu messen)

**Teacher-A/B, 100 Chat + 100 News, feste Sätze
(`wmk-glide/artifacts/out/ab_sentences.tsv`), identische Projektion:**

| Modell | Chat top-1 | News top-1 | Chat top-8 | News top-8 |
|---|---:|---:|---:|---:|
| 27B-FP8 | 35,03 % | 38,30 % | 81,96 % | 85,98 % |
| 9B-Base (BF16) | 31,29 % | 34,28 % | 78,61 % | 83,08 % |
| 4B-Base (BF16) | 29,87 % | 33,07 % | 78,47 % | 82,68 % |

Rohdaten `artifacts/out/ab_3way.json`; 27B↔9B Top-1-Agreement nur 50,2 %.

**L40S-Smoke (72 min, 1,8 €):** 59,45 Prompts/s · 1.029 Prompt-Tokens/s ·
Distill 55,8 Sätze/s, Masse 90,6 % · Schüler 2k Steps → Glide-Blend 0,7566.
Diente nur der Tooling-Prüfung; **nicht** als Qualitätsbenchmark zitieren.

**Quellen-Profile (10k Smoke-Targets, 27B):** Lehrer-Entropie News 1,939 ·
OpenSubtitles 1,918 · Tatoeba 2,019. OOV vs. 24.576er-Vokabular: Chat 13,4 %,
News 16,4 %.

---

## 3. Sofort-Ablauf (copy/paste-fähig)

```bash
# 0) scw (Windows)
$env:PATH = "C:\Users\saenta\AppData\Local\Microsoft\WinGet\Packages\Scaleway.cli_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:PATH"
scw instance server-type list zone=fr-par-2 | Select-String "^H100-1-80G"
```

**Anlegen — und sofort den Zustand prüfen:**

```powershell
scw instance server create type=H100-1-80G zone=fr-par-2 `
  image=ubuntu_noble_gpu_os_13_nvidia name=wmlm-h100 `
  root-volume=block:125GB ip=new `
  "cloud-init=@G:\C0ding\git\wmkeyboard-wmlm\wmk-glide\cloud\scaleway\cloud-init.yaml" -o json
scw instance server get <id> zone=fr-par-2 -o json     # state MUSS "running" sein
```

- `state != running` → **einmal** `scw instance server start <id> zone=fr-par-2`.
- Bleibt es `stopped`: **sofort löschen**
  `scw instance server delete <id> zone=fr-par-2 with-volumes=all with-ip=true --wait`
  und später neu versuchen. Ein gestoppter Server ist **keine Reservierung**
  und kostet Storage (~0,33 €/Tag + IP).

Dann wie unten in §5.

---

## 4. Fallstricke, die schon Zeit gekostet haben (bitte nicht wiederholen)

1. **`scw` heißt nicht `scw`:** Binary ist `scaleway-cli.exe`; in dem
   WinGet-Verzeichnis liegt ein selbst angelegtes `scw.cmd`-Shim, das
   Verzeichnis steht im PATH.
2. **scw-Default-Zone ist `fr-par-1`** → **immer** `zone=fr-par-2` mitgeben.
3. **Image nur als Label** `ubuntu_noble_gpu_os_13_nvidia` übergeben.
   Die Marketplace-UUID `741cfd27-…` führt bei `server create` zu
   „instance_image with ID … is not found".
4. **Gestoppte Instanz lässt sich nicht `terminate`n** („invalid state
   'stopped'"). Dafür `scw instance server delete <id> zone=fr-par-2
   with-volumes=all with-ip=true --wait` (Achtung: `with-volumes` akzeptiert
   `none|local|block|root|all`, **nicht** `true`).
5. **IP wird wiederverwendet** (wir hatten 3× dieselbe 78.232.7.210) → alter
   Host-Key. Vor dem Verbinden `ssh-keygen -R <ip>` in **Windows und WSL**.
   Das ist bei einer frisch erstellten Instanz normal, kein Angriff.
6. **`/data` ist kein Mountpoint** — die 125-GB-Block-Root-Volume *ist* der
   persistente Speicher. `setup_h100.sh` bricht deshalb ab; mit
   `ALLOW_ROOT_DISK=1` laufen lassen (bewusste Entscheidung, dokumentiert).
7. **Inline-Quoting zerstört Remote-Befehle** (PowerShell frisst `\"`, `\$`,
   `;`). Immer: Skript lokal schreiben → `rsync` → `setsid nohup bash …`
   → Log pollen. Kein `ssh host "…&&…&&…"` für etwas Längeres.
8. **Lange SSH-Kommandos blockieren den Turn.** Setup/Distill immer als
   `setsid nohup … > log 2>&1 < /dev/null &`, dann alle 30 s pollen
   (max. 5 Versuche), **keine Endlos-Wartezeiten**.
9. **vLLM 0.32 braucht für dieses Modell drei Einstellungen** (sind in den
   Skripten bereits gesetzt, nicht „wegoptimieren"):
   `max_num_seqs=64` (Qwen3.8 belegt einen Mamba-Cache-Block pro Sequenz,
   256 passt nicht in 48 GB), `max_logprobs=24` (Default 20) und
   `VLLM_USE_FLASHINFER_SAMPLER=0` (Image hat kein `nvcc`, FlashInfer-JIT
   scheitert sonst beim ersten `generate`).
10. **Rust fehlt im Image** — `setup_h100.sh` installiert rustup automatisch
    (verifiziert: cargo 1.99.1), `~/.cargo/bin` landet im `/data/env.sh`.
11. **`transfer.sh up` lädt die Roh-Korpora nicht** (nur `out/de_lm_*`,
    `ab_sentences.tsv`, Harness, Code) — `CORPORA=1` nur, wenn `prep.py`
    auf der Box laufen soll.
12. **`transfer.sh down` zieht keine Modelle** (`MODELS=1` erzwingt es).
    Die 29 GB bleiben auf der Box; lokal liegt noch ein Altbestand von
    28,8 GB unter `wmk-glide/artifacts/models/` (löschbar).
13. **Teardown nur verifiziert:** `teardown.sh <host>` → prüft sha256 jedes
    Remote-Artefakts → schreibt `artifacts/teardown-verified` → erst
    `teardown.sh <host> --terminate <id>`.
14. **`TOTAL=` nicht `COUNT=`** (das Skript liest `TOTAL`). Ohne `TOTAL`
    sammelt es alle 396 Shards.

---

## 5. Der eigentliche Lauf

```bash
# auf der Box, nach transfer.sh up + setup_h100.sh
cd /root/wmk && . /data/env.sh

# 1) Gate (60 s, muss >= 35 Prompts/s liefern; Exit 3 = Stop)
"$VLLM_PY" wmk-glide/cloud/scaleway/benchmark_quick.py \
  --data wmk-glide/artifacts/out/de_lm_2m --model "$TEACHER_MODEL" \
  --seconds 60 --eur-per-hour 2.88775 --out /data/out/bench_h100.json

# 2) Quantisierungs-A/B (Pflicht, ~15 min): FP8 vs BF16 vs FP8_DYNAMIC
"$VLLM_PY" wmk-glide/cloud/scaleway/benchmark_prompt_logprobs.py \
  --data wmk-glide/artifacts/out/de_lm_2m \
  --models "/data/models/Qwen3.8-27B-FP8,Qwen/Qwen3.8-27B,Qwen/Qwen3.8-27B|quantization=fp8_per_tensor" \
  --sentences-file wmk-glide/artifacts/out/ab_sentences.tsv \
  --per-class 100 --batch 16 --out /data/out/ab_quant.json
# Regel: FP8 gilt als gleichwertig bei Top-1-Agreement >= 95 % UND
# Top-8-Delta < 1 pp gegenueber BF16. Sonst fp8_per_tensor, wenn naeher an
# BF16; nur wenn beide abfallen BF16 (~7 h / ~20 EUR).

# 3) 1,2M-Prefix (240 Shards, ~3,5 h mit FP8), als nohup starten
TOTAL=1200000 PARTIAL_MERGE=1 ROOT=/root/wmk \
  bash wmk-glide/cloud/scaleway/run_distill_1m2.sh \
  /data/out/de_soft_1m2.npz wmk-glide/artifacts/out/de_lm_2m

# 4) Schueler (30k Steps) auf dem Teil-NPZ
STEPS=30000 SKIP_PREP=1 \
  bash wmk-glide/cloud/scaleway/prep_train_eval.sh \
  /data/out/de_soft_1m2.npz wmk-glide/artifacts/out/de_lm_2m /data/out/de_run_1m2

# 5) Sichern und erst dann loeschen
bash wmk-glide/cloud/scaleway/teardown.sh root@<ip>
bash wmk-glide/cloud/scaleway/teardown.sh root@<ip> --terminate <id>
```

Zeit-/Kostenrahmen: Setup ~10 min, Gate ~5 min, A/B ~15 min, 1,2M ~3,5 h,
Schüler ~30 min, Export/Eval ~10 min → **~4,5 h ≈ 13 €**. Deckel:
`MAX_BUDGET_EUR=50`, `MAX_HOURS=12`.

## 6. Dateien (alle geprüft und auditiert)

`wmk-glide/cloud/scaleway/`: `prepare_2m.py`, `vllm_common.py`,
`distill_vllm.py`, `benchmark_quick.py`, `benchmark_prompt_logprobs.py`,
`run_distill_1m2.sh`, `prep_train_eval.sh`, `setup_h100.sh`, `transfer.sh`,
`teardown.sh`, `cloud-init.yaml`, `README.md`, `credentials.example.env`,
`.gitignore`, `_e2e_distill_test.py`.

Verifikation: `bash -n` (6 Skripte), `py_compile` (5 Module), YAML-Parse,
`vllm_common.py --self-test`, `_e2e_distill_test.py` (Shards, Resume,
Repair, Pass 2, Staging, Identitäts-Guard) — grün. `teardown.sh` und die
`|quantization=…`-Spezifikation sind auditiert und offline getestet, aber
**noch nie auf einer echten GPU gelaufen** — der erste Lauf ist der Test.

Details: `README.md` (Runbook, gemessene Zahlen, Open Items),
`wmlm-training-plan.md` §1.3/§4.1, `kb-teacher-models.md` §4a.1.

## 7. Offene Punkte (nicht blockierend)

- OpenSubtitles-Lizenz (CC BY-NC) vor Veröffentlichung eines 2M-Modells klären.
- `de_1m_200k_chat.tsv` hat 12.368 Heldout-Leaks → **nicht verwenden**;
  bei Bedarf mit `prepare_2m.py --chat 640000 --news 560000` neu bauen.
- 28,8 GB Altbestand in `wmk-glide/artifacts/models/` (löschbar).
- BF16-Referenzzeile im A/B ist optional (Modell existiert: `Qwen/Qwen3.8-27B`).

## 8. Regeln

Keine Secrets ausgeben, nichts committen oder pushen, nie ohne verifizierte
Hashes terminieren, gestoppte Instanzen nie stehen lassen, Budget-Deckel
einhalten, bei Gate-Fehlschlag nicht weiterlaufen.
