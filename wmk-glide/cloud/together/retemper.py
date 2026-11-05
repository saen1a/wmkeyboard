#!/usr/bin/env python3
"""Re-temperature an existing soft-target file — no teacher, no API, no GPU.

The KD recipe in `plans/student-quality-audit.md` §3.2 asks for T ≈ 1,5–2,0 on
the teacher distribution, "aus dem Cache nur approximativ".  This tool applies
exactly that to a cached file, so the A/B costs a file rewrite instead of a
teacher pass: a 2M cache is ~2 GB and the rewrite takes minutes on CPU.

    p'_i = p_i^(1/T),  renormalised over the row's stored candidates

Two honest caveats, both reported:

* Rows are **renormalised** over their top-k (that is what `distill.py` and
  `distill_vllm.py` write). Re-tempering the truncated row is the documented
  approximation; with an un-renormalised collector file (`<soft>.audit.npz`
  carrying `mass`) the tool first restores absolute probabilities, tempers
  those, and writes the row back renormalised — the better variant.
* T > 1 flattens; the *support* does not grow. Missing mass stays missing, so
  T is not a substitute for the residual bucket.

    python3 retemper.py --soft out/de_soft_2m.npz --check --sweep 1,1.5,2
    python3 retemper.py --soft out/de_soft_2m.npz --out out/de_soft_2m_T1.5.npz \\
        --temperature 1.5 --report out/de_soft_2m_T1.5.report.json
    python3 retemper.py --self-test
"""
import argparse
import json
import os
import sys

import numpy as np

SOFT_KEYS = ("sentences", "starts", "ids", "probs")


def entropy_row(p):
    p = p[p > 0].astype(np.float64)
    if p.size == 0:
        return 0.0
    return float(-(p * np.log(p)).sum())


def temper_row(p, temperature, mass=None):
    """`(p^(1/T))` renormalised; `mass` restores absolute p first when given."""
    p = p.astype(np.float64)
    if mass is not None and mass > 0:
        p = p * mass
    out = np.zeros_like(p)
    nz = p > 0
    if not nz.any():
        return out
    out[nz] = p[nz] ** (1.0 / temperature)
    total = out.sum()
    if total <= 0.0:
        return np.zeros_like(p)
    return out / total


def stats(probs, ids, temperature, mass=None):
    rows = len(probs)
    h_before = h_after = 0.0
    top_before = top_after = 0.0
    filled = 0
    for r in range(rows):
        p = probs[r]
        if float(p.sum()) <= 0.0:
            continue
        filled += 1
        h_before += entropy_row(p)
        q = temper_row(p, temperature, None if mass is None else float(mass[r]))
        h_after += entropy_row(q)
        top_before += float(np.max(p))
        top_after += float(np.max(q))
    if not filled:
        return {"rows": rows, "filled": 0}
    return {"rows": rows, "filled": filled,
            "entropy_before": h_before / filled,
            "entropy_after": h_after / filled,
            "top_prob_before": top_before / filled,
            "top_prob_after": top_after / filled}


def load_sibling_mass(soft):
    sib = soft[:-4] + ".audit.npz" if soft.endswith(".npz") else soft + ".audit.npz"
    if not os.path.exists(sib):
        return None, None
    z = np.load(sib, allow_pickle=False)
    return (z["mass"].astype(np.float64) if "mass" in z.files else None), sib


def run(args):
    z = np.load(args.soft, allow_pickle=False)
    missing = [k for k in SOFT_KEYS if k not in z.files]
    if missing:
        raise SystemExit(f"{args.soft}: missing {missing}")
    ids = z["ids"]
    probs = z["probs"]
    mass, sib = load_sibling_mass(args.soft)
    report = {"soft": args.soft, "rows": int(len(ids)), "topk": int(ids.shape[1]),
              "absolute_mass_available": mass is not None,
              "mass_sibling": sib}

    if args.check or args.sweep:
        temps = ([float(t) for t in args.sweep.split(",") if t.strip()]
                 if args.sweep else [args.temperature])
        report["sweep"] = {str(t): stats(probs, ids, t, mass) for t in temps}
        print(json.dumps(report, indent=2))
        if args.report:
            write_report(args.report, report)
        return report

    t = float(args.temperature)
    if t <= 0:
        raise SystemExit("--temperature must be > 0")
    out = np.zeros_like(probs)
    for r in range(len(probs)):
        p = probs[r]
        if float(p.sum()) <= 0.0:
            continue
        out[r] = temper_row(p, t, None if mass is None else float(mass[r])).astype(np.float16)
    report.update(stats(probs, ids, t, mass))
    report["temperature"] = t
    tmp = args.out + ".tmp.npz"
    with open(tmp, "wb") as f:
        np.savez(f, sentences=z["sentences"].astype(np.int32, copy=False),
                 starts=z["starts"].astype(np.int64, copy=False),
                 ids=ids, probs=out)
    os.replace(tmp, args.out)
    report["out"] = args.out
    print(json.dumps(report, indent=2))
    if args.report:
        write_report(args.report, report)
    return report


def write_report(path, report):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        f.write("\n")
    os.replace(tmp, path)


def self_test():
    import tempfile
    ids = np.zeros((3, 4), dtype=np.int16)
    probs = np.zeros((3, 4), dtype=np.float16)
    probs[1] = np.array([0.7, 0.2, 0.1, 0.0], dtype=np.float16)
    probs[2] = np.array([0.4, 0.3, 0.2, 0.1], dtype=np.float16)

    # T = 1 is the identity (up to float16)
    q = temper_row(probs[1], 1.0)
    assert np.allclose(q, probs[1], atol=2e-3), q
    # T > 1 flattens: lower top prob, higher entropy
    hot = temper_row(probs[1], 2.0)
    assert hot.max() < probs[1].max()
    assert entropy_row(hot) > entropy_row(probs[1])
    # T < 1 sharpens
    cold = temper_row(probs[1], 0.5)
    assert cold.max() > probs[1].max()
    # rows always renormalise
    for t in (0.5, 1.0, 2.0):
        assert abs(temper_row(probs[2], t).sum() - 1.0) < 1e-9
    # an empty row stays empty
    assert float(temper_row(probs[0], 2.0).sum()) == 0.0
    # absolute mass is honoured: a row with mass 0.5 keeps 0.5 as its total
    q = temper_row(probs[1], 2.0, mass=0.5)
    assert abs(q.sum() - 1.0) < 1e-9           # written back renormalised
    raw = probs[1].astype(np.float64) * 0.5
    assert abs(sum(raw[i] ** 0.5 for i in range(4) if raw[i] > 0)) > 0.0

    with tempfile.TemporaryDirectory() as root:
        soft = os.path.join(root, "s.npz")
        np.savez(soft, sentences=np.array([0, 1], dtype=np.int32),
                 starts=np.array([0, 1, 3], dtype=np.int64), ids=ids, probs=probs)
        out = os.path.join(root, "t.npz")
        rep = os.path.join(root, "r.json")
        a = argparse.Namespace(soft=soft, out=out, temperature=1.5, check=False,
                               sweep="", report=rep)
        r = run(a)
        assert r["filled"] == 2, r
        assert r["entropy_after"] > r["entropy_before"], r
        z = np.load(out, allow_pickle=False)
        assert sorted(z.files) == sorted(SOFT_KEYS), z.files
        assert np.allclose(z["probs"].astype(np.float64).sum(1)[1:], 1.0, atol=2e-3)
        assert os.path.exists(rep)
        # --check writes nothing and reports a sweep
        b = argparse.Namespace(soft=soft, out=out + ".none", temperature=1.5,
                               check=True, sweep="1,1.5,2", report="")
        c = run(b)
        assert set(c["sweep"]) == {"1.0", "1.5", "2.0"}, c["sweep"]
        assert not os.path.exists(out + ".none")
    print("self-test ok: identity, flat/sharp, renormalisation, mass, sweep, no write")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--soft", required=False, help="existing soft npz")
    ap.add_argument("--out", default="", help="re-tempered soft npz")
    ap.add_argument("--temperature", type=float, default=1.5)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    ap.add_argument("--sweep", default="", help="e.g. 1,1.5,2 — entropy curve, no write")
    ap.add_argument("--report", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.soft:
        ap.error("--soft is required")
    if not (a.check or a.sweep) and not a.out:
        ap.error("--out is required unless --check/--sweep")
    run(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
