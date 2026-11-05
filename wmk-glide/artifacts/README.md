# German WMLM artifacts

Local training artifacts copied from the research worktree on 29.10.2026.
They live here so the German work can continue in the wmk fork. Most large
files are intentionally **not** tracked; see `.gitignore`.

| Path | Size | Contents |
|---|---:|---|
| `models/de_context.wmlm` | 10,86 MB | the shippable d256/6/768 model; SHA256 `e9212c5d…` |
| `models/de_context_d288.wmlm` | 12,82 MB | rejected d288/6/896 experiment (no Glide gain) |
| `out/de_soft_150k.npz` | 112 MB | 150k teacher soft targets, 91,3 % rows with mass |
| `out/de_soft_150k.npz.sha256` | 87 B | SHA256 of the soft targets |
| `out/train.npz` | 160 MB | prepared corpus (Tatoeba + Leipzig, 20k held out) |
| `out/heldout.npz`, `out/heldout.tsv` | 1,8 / 1,7 MB | held-out split |
| `out/best.pt` | 40 MB | d256 training checkpoint |
| `data/vocab.txt` | 234 KB | 24.576-token student vocabulary |
| `data/de_150k.txt` | 2,0 MB | keyboard word list |
| `data/de_150k_comp3.txt` | 8,4 MB | 150k + 441k observed compounds |
| `data/de_aosp.txt.gz` | 1,1 MB | AOSP German list (seed) |
| `data/de_full.txt.gz` | 5,3 MB | full German list (compound source) |
| `data/de_swipes.jsonl` | 19 MB | FUTO German glide pool (evaluation only) |
| `data/german.json` | 5,7 KB | German keyboard layout for the harness |
| `corpora/de_all.tsv` | 152 MB | Tatoeba DE + Leipzig News 2023, one sentence per line |
| `corpora/de_1m_200k_chat.tsv` | 101 MB | 1.2M rows, 640k chat / 560k news (53.3/46.7), SHA256 `882cdd31…` |
| `corpora/de_2m_mix.tsv` | 168 MB | 2.0M rows, 1,066k chat / 934k news (53.3/46.7), SHA256 `a3b7cd04…`; manifest + `.sha256` beside it |
| `corpora/opensubtitles_de_v2018.txt.gz` | 476 MB | OPUS OpenSubtitles DE mono, chat top-up for the 2M mix (CC BY-NC-style; see `cloud/scaleway/README.md`) |
| `out/de_lm_2m/` | 181 MB | `prep.py` on the 2M mix: 1,980,000 train sentences / 40.56M tokens, 20k heldout, vocab 24,576 |

`MANIFEST.sha256` contains the hashes of the model and the large `.npz`/`.pt`
files. `de_swipes.jsonl` comes from FUTO and is evaluation data; do not use it
for training.

## Not tracked

`corpora/`, `out/*.npz`, `out/*.pt`, `logs/` and `data/de_swipes.jsonl` are
ignored because of their size. The model and word lists are left untracked so
they can be added deliberately (ideally with Git LFS). Do not commit API keys
or `.togetherai.key`/`.deepinfra.key` files.

## Reproduce

The corpus and soft targets were produced in the research worktree with:

```sh
python3 tools/wmlm/corpus.py --lang=1 tatoeba:deu_sentences.tsv.bz2 > de_sentences.tsv
python3 tools/wmlm/corpus.py --lang=1 leipzig:deu_news_2023_1M.tar.gz > de_news.tsv
cat de_sentences.tsv de_news.tsv > de_all.tsv
python3 tools/wmlm/prep.py de_all.tsv out/de_lm_full \
  vocab=24576 pieces=2048 ctx=40 seed_words=de_aosp.txt heldout=20000
python3 tools/wmlm/distill.py out/de_lm_full out/de_soft_150k.npz \
  teacher=Qwen/Qwen3.5-4B-Base sentences=150000 topk=24 batch=16 device=cuda \
  multi=1 dtype=float16
python3 tools/wmlm/train.py out/de_lm_full out/de_run steps=30000 batch=256 \
  d=256 layers=6 heads=4 ff=768 ctx=40 distill=out/de_soft_150k.npz \
  distill_alpha=0.5 distill_share=0.5
python3 tools/wmlm/export.py out/de_run/best.pt out/de_lm_full/vocab.txt \
  out/de_context.wmlm --langs=de --name=German
```

The multi-token distill patch is `wmk-glide/patches/0005-distill-multitoken.patch`.
`wmk-glide/tools/check_soft.py` validates a soft-target file;
`wmk-glide/tools/merge_soft.py` stitches chunked runs.




