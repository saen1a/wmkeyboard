"""DirectML gather/scatter probe.

Reproduces the historical crash from `cloud/scaleway/NEXT-SESSION-TEACHER-FREE.md`
and tests three scatter-free alternatives. Each variant runs in its own
try/except; PASS / `FAIL <text>` per variant. On `--device cpu` every
variant MUST pass — that is the reference profile (the crash is a DirectML
limitation, not our code). Exit 0 if the CPU reference passes, non-zero
otherwise. Never downloads anything.

CLI:
    python directml_probe.py [--device dml|cpu]
                             [--batch 8 --ctx 40 --vocab 24576 --k 24]
"""
from __future__ import annotations

import argparse
import sys
import traceback

import torch
import torch.nn.functional as F


def banner(s):
    print(f"=== {s} ===", flush=True)


def variant_gather(logits, ids, probs):
    """Variant 1: torch.gather on logits. Crashes backward on DirectML."""
    filled = probs.sum(-1) > 0
    lse = torch.logsumexp(logits, dim=-1)
    picked = torch.gather(logits, -1, ids)
    per_pos = -(probs * (picked - lse.unsqueeze(-1))).sum(-1)
    return per_pos[filled].mean()


def variant_flat_index(logits, ids, probs):
    """Variant 2: flattened advanced indexing. No scatter/gather used."""
    filled = probs.sum(-1) > 0
    B, T, V = logits.shape
    K = ids.shape[-1]
    flat_logits = logits.reshape(B * T, V)
    flat_ids = ids.reshape(B * T, K)
    # Gather-free picking: pair row indices with column indices.
    rows = torch.arange(B * T, device=logits.device).unsqueeze(1).expand(-1, K)
    picked_flat = flat_logits[rows, flat_ids]          # [B*T, K]
    picked = picked_flat.reshape(B, T, K)
    lse = torch.logsumexp(logits, dim=-1)
    per_pos = -(probs * (picked - lse.unsqueeze(-1))).sum(-1)
    return per_pos[filled].mean()


def variant_take_along(logits, ids, probs):
    """Variant 3: torch.take_along_dim. Forward supported on DirectML; backward?"""
    filled = probs.sum(-1) > 0
    lse = torch.logsumexp(logits, dim=-1)
    picked = torch.take_along_dim(logits, ids, dim=-1)
    per_pos = -(probs * (picked - lse.unsqueeze(-1))).sum(-1)
    return per_pos[filled].mean()


def variant_onehot_chunked(logits, ids, probs, chunk=4):
    """Variant 4: chunked one-hot matmul. No gather / scatter on the hot path.

    For each chunk we build an explicit [B*t, V] one-hot matrix (from
    `torch.eye(V)` + advanced indexing — no scatter) and matmul it against
    `logits.reshape(-1, V)` to recover the picked column values. The
    matmul forward/backward are dense linear ops that DirectML supports.

    Per-row, per-j the picked value is `flat_logits[i, ids[i, j]]`, and
    the per-row total is `sum_j picked[i, j] * probs[i, j]`. Memory:
    `[B*t, K, V]` per chunk; with chunk=4 and K=24 that's small.
    """
    filled = probs.sum(-1) > 0
    B, T, V = logits.shape
    K = ids.shape[-1]
    lse = torch.logsumexp(logits, dim=-1)
    per_pos = logits.new_zeros((B, T))
    eye = torch.eye(V, device=logits.device, dtype=logits.dtype)   # [V, V]
    n_chunks = (T + chunk - 1) // chunk
    for s in range(n_chunks):
        e = min(T, s * chunk + chunk)
        sub = logits[:, s:e]                                      # [B, t, V]
        sub_ids = ids[:, s:e]                                     # [B, t, K]
        sub_probs = probs[:, s:e]                                 # [B, t, K]
        t = e - s
        onehot = eye[sub_ids.reshape(-1)].reshape(B, t, K, V)       # [B, t, K, V]
        weighted = onehot * sub_probs.reshape(B, t, K, 1)           # [B, t, K, V]
        # picked[b, t, k] = sum_v sub[b,t,v] * weighted[b,t,k,v]
        picked = (sub.unsqueeze(2) * weighted).sum(-1)              # [B, t, K]
        lse_sub = lse[:, s:e]                                       # [B, t]
        per_pos[:, s:e] = -(sub_probs * (picked - lse_sub.unsqueeze(-1))).sum(-1)
    return per_pos[filled].mean()


VARIANTS = [
    ("gather",       variant_gather,       "torch.gather on logits, -1, ids (the historical crash)"),
    ("flat_index",   variant_flat_index,   "logits.reshape(-1,V)[flat_ids] (no scatter/gather)"),
    ("take_along",   variant_take_along,   "torch.take_along_dim(logits, ids, dim=-1)"),
    ("onehot_chunk", variant_onehot_chunked, "chunked one-hot matmul per row"),
]


def run_variant(name, fn, logits, ids, probs, loss_buf):
    """Each variant runs a forward + backward in its own try/except."""
    try:
        # fresh leaf so backward is a real op, not a no-op shared graph
        logits = logits.detach().clone().requires_grad_(True)
        loss = fn(logits, ids, probs)
        loss.backward()
        grad_norm = float(logits.grad.norm().item())
        loss_buf[name] = (float(loss.item()), grad_norm)
        print(f"PASS  {name:14s}  loss={loss.item():.4f}  grad_norm={grad_norm:.4f}")
        return True
    except Exception as exc:
        text = (f"{type(exc).__name__}: {exc}").replace("\n", " | ")
        first = text.splitlines()[0] if isinstance(exc, Exception) and exc.__traceback__ else text
        first = first.split("|")[0].strip()
        print(f"FAIL  {name:14s}  {first[:200]}")
        return False


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--device", choices=["dml", "cpu"], default="cpu")
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--ctx",   type=int, default=40)
    p.add_argument("--vocab", type=int, default=24576)
    p.add_argument("--k",     type=int, default=24)
    p.add_argument("--seed",  type=int, default=0)
    return p.parse_args()


def pick_device(args):
    if args.device == "cpu":
        return torch.device("cpu")
    # dml
    try:
        import torch_directml  # noqa: F401
    except Exception as exc:
        print(f"torch_directml not importable: {exc}", file=sys.stderr)
        raise SystemExit(2)
    return torch_directml.device()


def main():
    args = parse_args()
    print(f"torch {torch.__version__} device_request {args.device}", flush=True)
    try:
        import torch_directml
        print(f"torch_directml {torch_directml.__version__ if hasattr(torch_directml, '__version__') else 'present'}", flush=True)
        has_dml = True
    except Exception as exc:
        print(f"torch_directml NOT installed ({type(exc).__name__}: {exc})", flush=True)
        has_dml = False
    if args.device == "dml" and not has_dml:
        raise SystemExit(2)

    dev = pick_device(args)
    print(f"using device {dev}", flush=True)

    torch.manual_seed(args.seed)
    B, T, V, K = args.batch, args.ctx, args.vocab, args.k
    logits = torch.randn(B, T, V, device=dev, dtype=torch.float32) * 0.01
    ids = torch.randint(0, V, (B, T, K), device=dev, dtype=torch.long)
    probs = F.softmax(torch.randn(B, T, K, device=dev, dtype=torch.float32), dim=-1)

    passed = []
    failed = []
    loss_buf = {}
    for name, fn, _desc in VARIANTS:
        banner(name)
        ok = run_variant(name, fn, logits, ids, probs, loss_buf)
        (passed if ok else failed).append(name)

    print()
    print(f"summary passed={passed}  failed={failed}", flush=True)
    if args.device == "cpu":
        # CPU is the reference: every variant must pass.
        if failed:
            print("CPU REFERENCE FAILED — at least one variant is broken on CPU", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    # dml: gather is *expected* to fail; the script's job is to capture the
    # exact string. We always exit 0 here — the caller decides.
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(2)
