"""Honest training-throughput probe for `tools/wmlm/train.py`.

Imports the *real* WordLm/Data/Soft/distill_loss/teacher_row_offsets from
`tools/wmlm/` (the repo path is inserted on `sys.path`; no model or loss code
is copied, so a benchmark cannot drift from what training runs). Runs a
warmup, then times `--steps` training steps and reports steps/s, tokens/s,
loss at the start and end, the device name, and (on GPU) peak
`torch.cuda.max_memory_allocated`. No checkpoint is written.

Options mirror `train.py`: `--data/--distill/--align/--mask/--weight`,
`--batch/--ctx/--d/--layers/--heads/--ff/--steps/--alpha/--share`, plus
`--impl gather|index|onehot` (the same three picks `train.distill_loss`
supports) and `--device auto|cpu|cuda|dml`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

import torch

# Locate the trainer. `tools/wmlm/` must be importable; we never copy code.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TOOLS_WMLM = os.path.join(REPO, "tools", "wmlm")
if not os.path.isdir(TOOLS_WMLM):
    raise SystemExit(f"tools/wmlm not found at {TOOLS_WMLM}")
sys.path.insert(0, TOOLS_WMLM)

# The single source of truth: model, batching, row offsets, gates, loss.
import train  # noqa: E402  (path set above)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--distill", default="")
    p.add_argument("--align", default="")
    p.add_argument("--mask", default="")
    p.add_argument("--weight", default="")
    p.add_argument("--steps", type=int, default=200)
    p.add_argument("--batch", type=int, default=256)
    p.add_argument("--impl", choices=["gather", "index", "onehot"], default="gather")
    p.add_argument("--device", choices=["auto", "cpu", "cuda", "dml"], default="auto")
    p.add_argument("--ctx", type=int, default=40)
    p.add_argument("--d", type=int, default=256)
    p.add_argument("--layers", type=int, default=6)
    p.add_argument("--heads", type=int, default=4)
    p.add_argument("--ff", type=int, default=768)
    p.add_argument("--warmup", type=int, default=10)
    p.add_argument("--json", default="")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--share", type=float, default=0.5)
    return p.parse_args()


def pick_device(name):
    if name != "auto":
        return train._pick_device(name)
    return train._pick_device("auto")


def main():
    args = parse_args()
    dev = pick_device(args.device)
    print(f"device {dev} torch {torch.__version__}", flush=True)

    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    torch.manual_seed(args.seed)
    gen = torch.Generator().manual_seed(args.seed)

    vocab = sum(1 for _ in open(os.path.join(args.data, "vocab.txt"), encoding="utf-8"))
    train_data = train.Data(os.path.join(args.data, "train.npz"), dev)

    soft = None
    if args.distill:
        try:
            soft = train.Soft(args.distill, align_path=args.align or None)
        except Exception as exc:
            raise SystemExit(f"--distill set but train.Soft failed: {exc}")
        print(f"distill from {args.distill} over {len(soft.sentences)} sentences "
              f"({'with' if soft.align is not None else 'without'} align)", flush=True)
    elif args.mask or args.weight:
        raise SystemExit("--mask/--weight require --distill")
    keep_kd, keep_ce, weight_kd = train.load_gates(soft, args.mask, args.weight)

    from model import WordLm  # type: ignore

    model = WordLm(vocab, d=args.d, layers=args.layers, heads=args.heads,
                   ff=args.ff, ctx=args.ctx).to(dev)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"params {n_params} train_sentences {train_data.n} vocab {vocab}", flush=True)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1,
                            betas=(0.9, 0.95))

    def one_step():
        from_teacher = soft is not None and torch.rand((), generator=gen).item() < args.share
        if from_teacher:
            idx = soft.sentences[
                torch.randint(0, len(soft.sentences), (args.batch,), generator=gen).numpy()
            ].tolist()
        else:
            idx = torch.randint(0, train_data.n, (args.batch,), generator=gen).tolist()
        x = train_data.batch(idx, args.ctx, gen)
        logits = model(x[:, :-1])
        tgt = x[:, 1:].clone()
        tgt[:, :3] = train.PAD
        if from_teacher:
            ids, probs = soft.batch(idx, x.shape[1], dev)
            use_gates = keep_kd is not None or keep_ce is not None or weight_kd is not None
            offsets = train.teacher_row_offsets(soft, idx, ids.shape[1]) if use_gates else None
            blocked_np, mask_sl, weight_sl = train.gates_for_batch(offsets, keep_kd, keep_ce, weight_kd)
            if blocked_np is not None:
                tgt = tgt.masked_fill(torch.from_numpy(blocked_np).to(dev), train.PAD)
            ce = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.shape[-1]), tgt.reshape(-1), ignore_index=train.PAD)
            m_t = torch.from_numpy(mask_sl).to(dev) if mask_sl is not None else None
            w_t = torch.from_numpy(weight_sl).to(dev) if weight_sl is not None else None
            kd = train.distill_loss(logits, ids, probs, mask=m_t, weight=w_t, impl=args.impl)
            loss = (1 - args.alpha) * ce + args.alpha * kd
        else:
            loss = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.shape[-1]), tgt.reshape(-1), ignore_index=train.PAD)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        return float(loss.detach().item())

    for _ in range(args.warmup):
        loss = one_step()
    if dev.type == "cuda":
        torch.cuda.synchronize()
    loss_start = loss

    t0 = time.time()
    for _ in range(args.steps):
        loss = one_step()
    if dev.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.time() - t0

    steps_per_s = args.steps / elapsed if elapsed > 0 else float("nan")
    tokens_per_s = steps_per_s * args.batch * args.ctx
    peak_mem_mb = (torch.cuda.max_memory_allocated() / 1e6) if dev.type == "cuda" else None

    print(f"steps {args.steps} elapsed {elapsed:.2f}s "
          f"steps/s {steps_per_s:.3f} tokens/s {tokens_per_s:.0f} "
          f"loss_start {loss_start:.4f} loss_end {loss:.4f}", flush=True)
    if peak_mem_mb is not None:
        print(f"peak_cuda_mem_mb {peak_mem_mb:.1f}", flush=True)

    if args.json:
        record = dict(
            device=str(dev),
            torch_version=torch.__version__,
            impl=args.impl,
            steps=args.steps,
            warmup=args.warmup,
            batch=args.batch,
            ctx=args.ctx,
            d=args.d,
            layers=args.layers,
            heads=args.heads,
            ff=args.ff,
            vocab=vocab,
            n_params=n_params,
            distill=args.distill,
            align=args.align,
            mask=args.mask,
            weight=args.weight,
            loss_start=loss_start,
            loss_end=float(loss),
            elapsed_s=elapsed,
            steps_per_s=steps_per_s,
            tokens_per_s=tokens_per_s,
            peak_cuda_mem_mb=peak_mem_mb,
        )
        with open(args.json, "w", encoding="utf-8") as fp:
            json.dump(record, fp, indent=2)
        print(f"wrote {args.json}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(2)
