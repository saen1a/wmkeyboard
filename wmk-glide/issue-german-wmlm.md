# [FEAT]: Train and publish a German context model (`de_context.wmlm`)

> **Status 2026-11-09:** published as the G6P 90k; the canonical release
> identity is `state.md` §2.7 and `data/de/de_context.md`. The local Phase 1
> `e921…` is not the release artifact. The data card records the CC BY-NC /
> OpenSubtitles attribution and non-commercial notice.

## Summary

At filing time (2026-10) German had no neural context model.
`ContextModelCatalog` published `en` and `bn_rom` only, so on a German device
`contextModel` was null: next-word predictions from the model, the context
ranking of the strip, the learned autocorrect gate's model view, phrase
suggestions, re-checking the previous word, and the glide score-space blend
were all inert. The status block above records the 2026-11 publication. The
German n-gram pack is
not a substitute: on FUTO's 2,588 German swipes its rank-unit rerank is +0.45
top-1, its score-space blend is negative, and a pack top-N context source has
only 0.4–1.2 % headroom.

This requests a German model trained with the existing `tools/wmlm` and
published to `wasi-master/wmkeyboard-data` as `data/de/de_context.wmlm`, with
the catalog entry and a held-out evaluation.

## Why

- #966 measured the glide decoder on German and found the context blend is the
  largest remaining lever, but it cannot run on a German device without a
  model. The current +10 points are a corpus-bigram proxy; a held-out split of
  that proxy gives only +0.2, so the real model is the missing measurement.
- The English model is the reference: on held-out sentences it raises
  next-word top-1 from 14 % to 20 % (top-3 23 % to 34 %), and the strip's first
  word from 87.2 % to 87.5 % on careful, 79.5 % to 82.7 % on fast and 72.1 % to
  76.0 % on sloppy typing.
- German is a major language for the keyboard, and the n-gram pack already
  ships; the neural model is the missing half of the context story.

## How large was the English dataset?

The repository documents the recipe, not the exact final row count. The
standard recipe is:

| Source | File | Size / count |
|---|---|---|
| Tatoeba English | `eng_sentences.tsv.bz2` | 24.9 MB compressed |
| Leipzig English news | `eng_news_2023_1M.tar.gz` | 1,000,000 sentences, 288 MB archive |
| held-out | `prep.py` default | 20,000 sentences |

The larger recipe adds OpenSubtitles English (`lines:opensub_en.txt:1:1`,
casual chat) and uses `vocab=24576 pieces=2048 ctx=40`. The published
`en_context.wmlm` header confirms the larger configuration: `d=256, layers=6,
heads=4, ff=768, ctx=40, vocab=24576, step=28000`, 10.8 MB. Distillation reads
150,000 sentences (Qwen2.5-1.5B in `remote/run_en2.sh`).

So the English training set is **1M+ Leipzig sentences plus Tatoeba and,
optionally, OpenSubtitles**; order of tens of millions of tokens. The exact
number is not stored in the repo — `prep.py` prints `N sentences, M tokens`
when it runs. For German the comparable set is Tatoeba German
(`deu_sentences.tsv.bz2`, 12.1 MB) plus Leipzig `deu_news_2023_1M` (1M
sentences), optionally OpenSubtitles German.

## Proposed German recipe

```bash
cd tools/wmlm

python corpus.py tatoeba:deu_sentences.tsv.bz2 \
                 leipzig:deu_news_2023_1M.tar.gz \
                 lines:opensub_de.txt:1:1 > de_sentences.tsv

# seed_words must be the keyboard's own German list, not a generic 150k list
# (205,888 words in data/de/de_aosp.txt.gz)
python prep.py de_sentences.tsv de_lm \
    vocab=24576 pieces=2048 ctx=40 seed_words=de_aosp.txt

python distill.py de_lm de_soft.npz \
    teacher=Qwen/Qwen2.5-1.5B sentences=150000 topk=24

python train.py de_lm de_run steps=30000 batch=384 \
    d=256 layers=6 ff=768 ctx=40 \
    distill=de_soft.npz distill_alpha=0.5

python export.py de_run/best.pt de_lm/vocab.txt de_context.wmlm \
    --langs=de --name=German
```

A smaller first model is the standard recipe: `vocab=16384 ctx=32`,
`steps=8000 batch=256`, defaults for `d/layers/ff`. The large recipe needs a
CUDA card; the English d256 run with the 1.5B teacher takes under two hours on
an RTX 3090/4090 (`remote/setup.sh`, `remote/run_en2.sh`).

## Acceptance criteria

- `data/de/de_context.wmlm` is published and loads with `lm_probe`:
  `cargo run --release --example lm_probe -- de_context.wmlm "ich will nach" ...`
- The header is `langs=["de"]`, the configured vocab/ctx, and the file is
  within the catalog's expected size.
- `typing_eval` on `de_lm/heldout.tsv` reports next-word top-1/top-3, strip
  top-1 on careful/fast/sloppy typing, autocorrect precision/recall, and the
  new-word rewrite rate, against the same run without the model.
- The glide measurement from #966 is repeated on FUTO's 2,588 German swipes
  with the real model on a held-out sentence split: top-1/top-4 with and
  without the score blend, so the device gain is a measured number, not the
  in-sample corpus-bigram proxy.
- English and Banglish models are unchanged; the new catalog entry does not
  affect languages without a model.

## Publishing

1. Upload `de_context.wmlm` to `wasi-master/wmkeyboard-data/data/de/`.
2. Add the entry to `ContextModelCatalog.kt`:
   `ContextModelEntry(languageId = "de", repoCode = "de", stem = "de_context", approxBytes = <size>)`.
3. Optional `de_context_large` variant if both sizes are trained; the catalog
   already models standard/large.
4. No engine code: `lm.rs` reads the header, `ContextModel.kt` loads the file,
   and `ContextModelDownloadManager` picks up the catalog entry.

## Licensing and notes

- Tatoeba is CC BY 2.0 FR / CC0; Leipzig and OpenSubtitles/OPUS carry their own
  terms. Attribute them in the data repo as the existing models do.
- `pieces=2048` matters for German compounds and names; `seed_words` must be
  `de_aosp` so the model has an opinion about the words the strip can offer.
- The German n-gram pack stays; evaluate `lm+pack`, not one instead of the
  other.
- The FUTO glide harness does not load `.wmlm` today; the typing harness and
  `lm_probe` are the first checks, and the glide blend needs either a model
  score dump or an on-device run.

## Not in scope

- A multilingual model (one language slot is enough for German).
- Bundling the model in the APK.
- Changing the engine or the model format.
- Training a teacher from scratch; the existing Qwen2.5 distillation path is
  enough for the first model.
ng Qwen2.5 distillation path is
  enough for the first model.
