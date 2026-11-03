#!/usr/bin/env python3
"""Repair the blind rows of an existing soft-target file with exact teacher mass.

The 2M cache (`de_soft_2m.npz`, 21.4M rows, top-24, Qwen3.8-27B) has three
known holes, all measured in `artifacts/out/audit_signal.json`:

* **15.3 %** of rows are words the teacher only spells in pieces and mapped to
  **mass 0.0** (`piece_top24 = 0.0`). The KD term is *not* a no-op there: with
  `L = (1−α)·CE + α·KD` and `logsumexp` over the full vocabulary the correct
  piece word settles at `p_b = 1−α` (`kb-student-architecture-de.md` §2).
* **18.3 %** of rows do not contain the true word in the top-24 at all.
* **~1 %** of non-first rows are empty (row 0 of every sentence is empty by
  design and is *not* touched here — `soft_mask.py fill` owns it).

Together's `echo` gives the true word's **exact** probability for every
position, multi-token words included. This tool fetches only the sentences that
contain blind rows, keeps the existing 24 candidates and writes the true word
into the *last* slot (the one with the smallest probability) when it is
missing — so the row keeps its 24-wide shape, its teacher, and gains the one
fact it was missing.

The file it writes has exactly the four keys the trainer expects, the same
`sentences`/`starts` and the same row count. A report lists every change.

    python3 patch_soft.py --data-dir out/de_lm_2m --soft out/de_soft_2m.npz \
        --map out/wordmap_together.json --out out/de_soft_2m_patched.npz \
        --model zai-org/GLM-5.2 --report out/de_soft_2m_patched.report.json
    python3 patch_soft.py --self-test
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for extra in (HERE, os.path.abspath(os.path.join(HERE, "..", "scaleway")),
              os.path.abspath(os.path.join(HERE, "..", "..", "tools"))):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import client as tg            # noqa: E402
import distill_together as dt  # noqa: E402
import together_common as tc   # noqa: E402
import vllm_common as vc       # noqa: E402
import wordmap as wm           # noqa: E402

SOFT_KEYS = ("sentences", "starts", "ids", "probs")


def word_groups(row):
    """`[(student id, is_piece), ...]` — the same grouping `prompt_text` uses."""
    out = []
    for t in row[vc.PREFIX_LEN:-1]:
        w = dt.sp_vocab_lookup(int(t))
        if w.startswith(vc.CONT):
            continue
        out.append((int(t), w.startswith(vc.START) or w.startswith(vc.CONT)))
    return out


def blind_rows(ids, probs, starts, sentences, tokens, sents_starts):
    """Row indices that need repair, grouped per sentence index.

    A row is blind when it carries no mass (and is not the sentence's first
    row) or when its word is a piece the teacher cannot map. Rows that already
    contain the true word are left alone.
    """
    out = {}
    for i, sid in enumerate(sentences):
        a, e = int(starts[i]), int(starts[i + 1])
        if e <= a:
            continue
        groups = word_groups(tokens[sents_starts[sid]:sents_starts[sid + 1]])
        need = []
        for r in range(a + 1, e):          # row 0 is filled by soft_mask
            k = r - a
            if k >= len(groups):
                break
            wid, is_piece = groups[k]
            row_ids = {int(ids[r, j]) for j in range(ids.shape[1]) if probs[r, j] > 0}
            empty = float(probs[r].sum()) == 0.0
            if empty or (is_piece and wid not in row_ids):
                need.append((r, wid))
        if need:
            out[int(sid)] = need
    return out


def patch_row(ids, probs, r, wid, p_true):
    """Write `wid` with probability `p_true` into row `r`, keeping width."""
    if p_true <= 0.0:
        return False
    row_ids = [int(x) for x in ids[r]]
    if wid in row_ids:
        return False
    p = np.asarray(probs[r], dtype=np.float32)
    if p.sum() > 0.0:
        # replace the weakest candidate, keep the row's shape and its teacher
        slot = int(np.argmin(np.where(p > 0, p, np.inf)))
        if not np.isfinite(p[slot]):
            slot = len(p) - 1
    else:
        slot = 0
    ids[r, slot] = wid
    p[slot] = p_true
    total = float(p.sum())
    if total <= 0.0:
        return False
    probs[r] = (p / total).astype(np.float16)
    return True


def run(args, transport=None, client=None):
    vocab = dt.load_vocab(args.data_dir)
    _, tokens, sents_starts = vc.load_corpus(args.data_dir)
    z = np.load(args.soft, allow_pickle=False)
    ids = z["ids"].copy()
    probs = z["probs"].copy()
    sentences = z["sentences"].copy()
    starts = z["starts"].copy()

    by_first, meta = wm.load_map(args.map)
    if meta.get("vocab_sha256") and args.data_dir:
        want = wm.vocab_digest(os.path.join(args.data_dir, "vocab.txt"))
        if meta["vocab_sha256"] != want:
            raise SystemExit("word map was built for a different vocabulary")

    todo = blind_rows(ids, probs, starts, sentences, tokens, sents_starts)
    report = {"soft": args.soft, "model": args.model, "rows": int(len(ids)),
              "sentences_total": int(len(sentences)),
              "sentences_needing_repair": len(todo),
              "rows_flagged": int(sum(len(v) for v in todo.values())),
              "rows_patched": 0, "rows_no_probability": 0, "already_present": 0}
    if args.limit:
        todo = dict(list(sorted(todo.items()))[:args.limit])
    if args.dry_run or not todo:
        print(json.dumps(report, indent=2))
        return report

    cl = client or tg.Client(model=args.model, key_file=args.key_file,
                             batch=args.batch, transport=transport,
                             key=("test-key" if transport else None))
    sids = sorted(todo)
    for b in range(0, len(sids), args.batch):
        chunk = sids[b:b + args.batch]
        texts, ends_by, actual_by = [], {}, {}
        for sid in chunk:
            row = tokens[sents_starts[sid]:sents_starts[sid + 1]]
            text, ends = vc.prompt_text(vocab, row)
            if not text or not ends:
                continue
            texts.append(text)
            ends_by[sid] = ends
            actual_by[sid] = word_groups(row)
        if not texts:
            continue
        answers = cl.score(texts)
        for sid, text, ch in zip([s for s in chunk if s in ends_by], texts, answers):
            actual = [w for w, _ in actual_by[sid]]
            ids_s, probs_s, mass, act, ap, _ = tc.rows_from_sentence(
                ch.tokens, ch.logs, ch.alts, ch.prompt_tokens, ends_by[sid],
                by_first, topk=args.topk, inject_actual=False, actual=actual)
            for r, wid in todo[sid]:
                k = r - int(starts[list(sentences).index(sid)])
                if k >= len(ap):
                    continue
                p_true = float(ap[k])
                if p_true <= 0.0:
                    report["rows_no_probability"] += 1
                    continue
                if patch_row(ids, probs, r, wid, p_true):
                    report["rows_patched"] += 1
                else:
                    report["already_present"] += 1

    tmp = args.out + ".tmp.npz"
    with open(tmp, "wb") as f:
        np.savez(f, sentences=sentences.astype(np.int32, copy=False),
                 starts=starts.astype(np.int64, copy=False),
                 ids=ids, probs=probs)
    os.replace(tmp, args.out)
    dt.validate_soft(args.out, len(vocab), len(sentences), args.min_mass_ratio)
    if args.report:
        tmpj = args.report + ".tmp"
        with open(tmpj, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmpj, args.report)
    print(json.dumps(report, indent=2))
    return report


def self_test():
    """Synthetic cache with one empty row and one piece row."""
    import tempfile

    vc._load_common()
    with tempfile.TemporaryDirectory() as root:
        vocab = list(vc.SPECIALS) + ["ich", "will", "hause", "gehen",
                                     "\u2581hau", "##se"]
        ich, will, hause = (vocab.index(w) for w in ("ich", "will", "hause"))
        hau, se = vocab.index("\u2581hau"), vocab.index("##se")
        # sentence 0: "ich will <piece hause>" -> row 2 is a piece row
        tokens = [0, 0, 0, 0, ich, will, hau, se, 2]
        starts = np.array([0, len(tokens)], dtype=np.int64)
        with open(os.path.join(root, "vocab.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(vocab) + "\n")
        np.savez(os.path.join(root, "train.npz"),
                 tokens=np.asarray(tokens, dtype=np.int32), starts=starts)
        dt.load_vocab(root)

        ids = np.zeros((4, 24), dtype=np.int16)
        probs = np.zeros((4, 24), dtype=np.float16)
        ids[1, 0], probs[1, 0] = ich, 1.0        # row 1 has mass
        # rows 2,3 are empty -> blind
        soft = os.path.join(root, "soft.npz")
        np.savez(soft, sentences=np.array([0], dtype=np.int32), starts=np.array([0, 4]),
                 ids=ids, probs=probs)
        todo = blind_rows(ids, probs, np.array([0, 4]), np.array([0]), tokens, starts)
        assert todo[0] == [(2, hau), (3, hause)] or todo[0] == [(2, hau)], todo

        # patching keeps the width and renormalises
        ids2, probs2 = ids.copy(), probs.copy()
        ok = patch_row(ids2, probs2, 2, hause, 0.25)
        assert ok and ids2.shape == ids.shape
        assert abs(float(probs2[2].sum()) - 1.0) < 2e-3
        assert int(ids2[2, 0]) == hause

        # an existing word is never written twice
        ok = patch_row(ids2, probs2, 1, ich, 0.5)
        assert ok is False

        # end to end with the fake transport of the e2e test
        from test_together_e2e import FakeTransport, write_corpus
        with tempfile.TemporaryDirectory() as root2:
            vocab2, n_sent = write_corpus(root2)
            dt.load_vocab(root2)
            _, tok2, st2 = vc.load_corpus(root2)
            # an "existing cache" with two empty rows per sentence
            rows = []
            ids3, probs3, starts3, sents = [], [], [0], []
            for sid in range(n_sent):
                row = tok2[st2[sid]:st2[sid + 1]]
                groups = word_groups(row)
                for _ in groups:
                    ids3.append(np.zeros(24, dtype=np.int16))
                    probs3.append(np.zeros(24, dtype=np.float16))
                starts3.append(starts3[-1] + len(groups))
                sents.append(sid)
            soft3 = os.path.join(root2, "cache.npz")
            np.savez(soft3, sentences=np.array(sents, dtype=np.int32),
                     starts=np.array(starts3), ids=np.array(ids3),
                     probs=np.array(probs3))
            import client as tg_
            cl = tg_.Client(key="k", batch=4, transport=FakeTransport())
            built = wm.build_map(vocab2, cl.score, "fake")
            wm.save_map(os.path.join(root2, "map.json"), built,
                        wm.vocab_digest(os.path.join(root2, "vocab.txt")))
            out = os.path.join(root2, "patched.npz")

            class A:
                pass
            a = A()
            a.data_dir, a.soft, a.out = root2, soft3, out
            a.map, a.model = os.path.join(root2, "map.json"), "fake"
            a.batch, a.topk, a.limit = 4, 8, 0
            a.key_file, a.report, a.dry_run = "", "", False
            a.min_mass_ratio = 0.0
            rep = run(a, transport=FakeTransport(), client=cl)
            assert rep["rows_patched"] > 0, rep
            z = np.load(out, allow_pickle=False)
            assert sorted(z.files) == sorted(SOFT_KEYS), z.files
            assert z["ids"].shape == np.array(ids3).shape, (z["ids"].shape,)
            assert int((z["probs"].sum(axis=1) > 0).sum()) > 0
    print("self-test ok: blind rows, width-preserving patch, idempotence, end to end")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=False, help="prep.py dir (vocab.txt, train.npz)")
    ap.add_argument("--soft", required=False, help="existing 24-wide soft npz")
    ap.add_argument("--out", required=False, help="patched soft npz")
    ap.add_argument("--map", required=False, help="word map for --model")
    ap.add_argument("--model", default="Qwen/Qwen3.5-9B")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--topk", type=int, default=tc.DEFAULT_TOPK)
    ap.add_argument("--limit", type=int, default=0, help="0 = all sentences")
    ap.add_argument("--min-mass-ratio", type=float, default=0.0)
    ap.add_argument("--key-file", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.self_test:
        return self_test()
    for need in ("data_dir", "soft", "out", "map"):
        if not getattr(args, need):
            build_parser().error(f"--{need.replace('_', '-')} is required")
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
