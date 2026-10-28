# Experimente zur nächsten Stufe (Nachtrag zu §2.6)

Forschungs-Code, nicht ausgeliefert. Die Ergebnisse stehen in
[`../experiments-followup.md`](../experiments-followup.md); hier liegt, wie man
sie neu zieht.

## N-Gramm-Analyse (Stand 27.10.)

```sh
# zusätzlich zu de_swipes/de_150k/de_full aus dem ZIP/Data-Repo:
curl -L -o data/deu_sentences.tsv.bz2 \
  https://downloads.tatoeba.org/exports/per_language/deu/deu_sentences.tsv.bz2
curl -L -o data/deu_wikipedia_2021_1M.tar.gz \
  https://downloads.wortschatz-leipzig.de/corpora/deu_wikipedia_2021_1M.tar.gz
mkdir -p data/wiki && tar -xzf data/deu_wikipedia_2021_1M.tar.gz -C data/wiki
# de_bigrams.txt.gz / de_trigrams.txt.gz aus wasi-master/wmkeyboard-data/data/de/
```

Die Skripte laufen aus `wmk-glide/` und erwarten die Daten unter `data/`.
`build_wiki_pack.py` schreibt `wiki_pack.pkl`; `compare_packs.py` liest es.
Die Analyse steht in [`../ngram-analysis.md`](../ngram-analysis.md).

## Vorbereitung

```sh
# Daten wie im ZIP: de_swipes.jsonl, german.json, de_150k.txt
# zusätzlich die Voll-Liste für die Komposita-/Unigramm-Versuche:
curl -L -o de_full.txt \
  https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_full.txt

# Harness mit den Patches 0000–0002 + 0004 bauen
cd /pfad/zu/wmkeyboard/native/wm-engine
cargo build --release --example glide_beam_eval
```

Die Python-Skripte werden aus `wmk-glide/` gestartet und erwarten `data/` und
die Dumps dort: `data/de_swipes.jsonl`, `data/de_150k.txt`, `data/de_full.txt`,
`data/german.json`, `pool.jsonl`/`pool32.tsv` usw.

## Dumps

```sh
# Top 32 ohne Join
ALL=1 THREADS=8 RESULTS=32 COLS=11 DUMP=pool32.tsv \
  ./target/release/examples/glide_beam_eval \
  data/de_swipes.jsonl data/german.json data/de_150k.txt

# Guard-Pool (deutsches Profil)
printf 'freq_weight=0.5 gap_weight=2.0 join_cost=8 join_min_part=4 join_part_penalty=0.1\n' \
 | COLS=11 ALL=1 THREADS=8 RESULTS=32 DUMP=pool_guard32.tsv \
   ./target/release/examples/glide_beam_eval \
   data/de_swipes.jsonl data/german.json data/de_150k.txt
```

Der Dump ist `ziel \t top \t hit \t in_liste \t wort:score|...` (siehe
`patches/0000-eval-harness.patch`).

## Skripte

| Skript | Was es misst |
|---|---|
| `common.py` | Laden, Tokenisieren, Unigramm/Bigramm/Trigramm, Satz-Split |
| `pool_blend.py` | Pool 4…32 × Deckel/Gewicht, Top-1 |
| `features.py` | Bigramm/Trigramm, Deckel-Sweep |
| `fair_ngram.py` | 20-%-Satz-Split, Bigramm vs Trigramm |
| `fair_full_uni.py` | Voll-Liste als Unigramm (negativ) |
| `logit.py` | 9-Feature-conditional-Logit, Satz-Split |
| `compound.py` | Voll-Listen-Bonus auf dem Guard-Pool |
| `compound_pair.py` | Teil-Paar-Tabelle (471k Paare) |
| `compound_guard.py` | Voll-Listen-Filter/Bonus auf Join-Pools |
| `lm_recall.py` | Wie oft steht das Ziel in LM-Top-N, aber nicht im Pool? |
| `gen_lm_source.py`, `gen_lm_source_lp.py` | Per-Stroke-Top-50 für die Kontextquelle |
| `diacritic.py` | Wortlisten-Restaurierung auf dem a–z-Gitter |
| `glide_lm_source_eval.rs` | Per-Stroke-LM-Quelle als zusätzliche `Source` |
| `glide_lm_blend_eval.rs` | Echter `.wmlm`-Blend auf dem Glide-Pool (der Prototyp für `blendGlideContextModel`) |
| `freq-exponent.patch` | `freq_exponent` im Rust-`Tuning` (verworfen; auf 0000–0002 + 0004 anwenden) |
| `pack_quality.py` | Pack-Abdeckung auf FUTO, roh vs. normalisiert/Backoff |
| `pack_features.py` | Class-/Skip-Gramme auf dem Pack (neutral/negativ) |
| `build_wiki_pack.py` | Wikipedia-Pack aus Leipzig `deu_wikipedia_2021_1M` |
| `compare_packs.py` | web/news vs Wikipedia vs kombiniert, Deckel |
| `chat_pack.py` | Tatoeba-Chat-Pack vs web/news, Next-Word-Bigramm |
| `chat_pack_tri.py` | Trigramm auf Chat |
| `chat_pack_tri_caps.py` | Trigramm-Deckel 50k–1M |
| `chat_web_tri.py` | web-Trigramm auf Chat (Domänen-/Ordnungsvergleich) |
| `chat_pack_4.py` | 4-Gramm auf Chat, Backoff 4→3→2→1 |
| `german-umlaut-keys.patch` | QWERTZ mit echten `ü ö ä ß`-Tasten (optional, **nicht empfohlen**; +1,36 synthetisch) |

## Fairer Split

`fair_ngram.py`, `logit.py` und die LM-Quelle teilen die Sätze per
`sha256(sentence|session) % 5 == 0` in 20 % Test; das LM wird nur auf den
restlichen 80 % gebaut. Das ist der Unterschied zu den in-sample-Zahlen in
`state.md` §2.6.1: dort sieht das Bigramm den Test-Satz selbst.

## Kontextquelle

`glide_lm_source_eval.rs` nach `native/wm-engine/examples/` kopieren, bauen:

```sh
cargo build --release --example glide_lm_source_eval
EXTRA_ONLY=1 EXTRA_SCALE=1e6 COLS=11 THREADS=8 RESULTS=8 \
  ./target/release/examples/glide_lm_source_eval \
  test_records.jsonl data/german.json data/de_150k.txt test_extra50_lp.jsonl
```

`test_records.jsonl` und `test_extra50_lp.jsonl` erzeugen
`gen_lm_source.py` / `gen_lm_source_lp.py` (die Pfade dort anpassen).

Die Skripte sind bewusst klein und lesbar, keine Produktionswerkzeuge; für eine
Veröffentlichung die Pfade parametrisieren und die Fair-Split-Läufe in den
Harness aufnehmen.
