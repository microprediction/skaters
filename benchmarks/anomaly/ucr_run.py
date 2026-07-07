"""UCR Anomaly Archive runner for the parade Mahalanobis detector.

Protocol (see RESEARCH.md): each of the 250 series contains exactly one
anomaly; the filename encodes ``<trainLen>_<anomStart>_<anomEnd>``. We run
strictly causally over the whole series, use the anomaly-free prefix
[0, trainLen) for state warm-up only, and report the argmax of the score over
the scored region [trainLen, n). A series is a hit iff the argmax falls inside
the anomaly range extended by tolerance max(100, anomaly length). Accuracy is
the fraction of series hit.

Three scorers are computed in the same pass:
    mah:  -log10 p-value of the streaming Mahalanobis detector (the method)
    z1:   |z_1| — the 1-step parade surprise from the SAME forecaster
          (ablation: multivariate geometry vs per-horizon rule)
    mz:   EWMA z-score of the raw series (the community-mandatory trivial
          baseline; no forecaster at all)

Usage:
    python benchmarks/anomaly/ucr_run.py --limit 40 --k 3 --workers 8
    python benchmarks/anomaly/ucr_run.py            # full 250, long run
"""

from __future__ import annotations
import argparse
import json
import math
import os
import re
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "src"))

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "data", "UCR_Anomaly_FullData")
_NAME = re.compile(r"^(\d+)_UCR_Anomaly_(.+)_(\d+)_(\d+)_(\d+)\.txt$")


def parse_name(fname: str):
    m = _NAME.match(fname)
    assert m, f"unparseable UCR filename: {fname}"
    sid, name, train_len, a_start, a_end = m.groups()
    return int(sid), name, int(train_len), int(a_start), int(a_end)


def load_series(path: str) -> list:
    vals = []
    with open(path) as f:
        for line in f:
            vals.extend(float(tok) for tok in line.split())
    return vals


def run_one(args):
    fname, k = args
    sid, name, train_len, a_start, a_end = parse_name(fname)
    ys = load_series(os.path.join(DATA, fname))
    n = len(ys)

    from skaters import laplace
    from skaters.anomaly import mahalanobis

    f = mahalanobis(laplace(k), k=k)
    state = None
    # trivial baseline state: EWMA mean/var of raw y
    mz_m, mz_v, mz_n = 0.0, 0.0, 0
    ALPHA = 0.02
    # scan-statistic buffers: windowed mean of -log10 p (anomalies are
    # intervals, not ticks; w in {8, 64} spans the labeled lengths)
    from collections import deque
    WINDOWS = (8, 64)
    wbuf = {w: deque() for w in WINDOWS}
    wsum = {w: 0.0 for w in WINDOWS}

    best = {"mah": (-1.0, -1.0, -1), "mahS": (-1.0, -1.0, -1),
            "z1": (-1.0, -1.0, -1), "mz": (-1.0, -1.0, -1)}
    t0 = time.time()
    for t, y in enumerate(ys):
        _, state = f(y, state)
        # trivial baseline (causal: score with current estimate, then update)
        mz_n += 1
        a = max(ALPHA, 1.0 / mz_n)
        sd = math.sqrt(mz_v) if mz_v > 0 else 1e-8
        mz_score = abs(y - mz_m) / sd if mz_n > 3 else 0.0
        d = y - mz_m
        mz_m += a * d
        mz_v = (1 - a) * mz_v + a * d * (y - mz_m)

        if t < train_len:                      # warm-up: never scored
            continue
        p = state["pvalue"]
        if p is not None:
            d2 = state["d2"]
            s = -math.log10(max(p, 1e-300))
            if (s, d2) > best["mah"][:2]:      # d2 breaks saturation ties
                best["mah"] = (s, d2, t)
            for w in WINDOWS:
                wbuf[w].append(s)
                wsum[w] += s
                if len(wbuf[w]) > w:
                    wsum[w] -= wbuf[w].popleft()
                if len(wbuf[w]) == w:
                    sc = wsum[w] / w
                    if sc > best["mahS"][0]:
                        best["mahS"] = (sc, 0.0, t - w // 2)
        z = state["base"]["z"][0] if isinstance(state["base"], dict) else None
        if z is not None:
            if abs(z) > best["z1"][0]:
                best["z1"] = (abs(z), 0.0, t)
        if mz_score > best["mz"][0]:
            best["mz"] = (mz_score, 0.0, t)

    tol = max(100, a_end - a_start)
    lo, hi = a_start - tol, a_end + tol
    res = {"sid": sid, "name": name, "n": n, "train_len": train_len,
           "anom": [a_start, a_end], "seconds": round(time.time() - t0, 1)}
    for key, (score, _tie, loc) in best.items():
        res[key] = {"loc": loc, "score": round(score, 3),
                    "hit": bool(lo <= loc <= hi)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="run only the N shortest series (0 = all 250)")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    files = sorted(os.listdir(DATA))
    files = [f for f in files if _NAME.match(f)]
    files.sort(key=lambda f: os.path.getsize(os.path.join(DATA, f)))
    if args.limit:
        files = files[:args.limit]

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"ucr_results_k{args.k}_n{len(files)}.jsonl")

    results = []
    with Pool(args.workers) as pool:
        for i, res in enumerate(pool.imap_unordered(
                run_one, [(f, args.k) for f in files])):
            results.append(res)
            hits = {m: sum(r[m]["hit"] for r in results) for m in ("mah", "mahS", "z1", "mz")}
            print(f"[{i+1}/{len(files)}] {res['sid']:03d} {res['name'][:30]:30s} "
                  f"n={res['n']:7d} {res['seconds']:6.1f}s  "
                  f"mah={'HIT ' if res['mah']['hit'] else 'miss'} "
                  f"mahS={'HIT ' if res['mahS']['hit'] else 'miss'} "
                  f"z1={'HIT ' if res['z1']['hit'] else 'miss'} "
                  f"mz={'HIT ' if res['mz']['hit'] else 'miss'}  "
                  f"running: mah {hits['mah']} mahS {hits['mahS']} "
                  f"z1 {hits['z1']} mz {hits['mz']} of {i+1}", flush=True)

    with open(out_path, "w") as fh:
        for r in sorted(results, key=lambda r: r["sid"]):
            fh.write(json.dumps(r) + "\n")

    n = len(results)
    print("\n=== UCR accuracy ===")
    for m, label in (("mah", "parade Mahalanobis (single tick)"),
                     ("mahS", "parade Mahalanobis (scan w=8/64)"),
                     ("z1", "per-horizon |z1| (same forecaster)"),
                     ("mz", "EWMA z-score (trivial baseline)")):
        h = sum(r[m]["hit"] for r in results)
        print(f"{label:38s} {h}/{n} = {h/n:.3f}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
