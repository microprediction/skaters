"""Front-end experiment, matrix-profile head: does the laplace z front-end
help or hurt a DAMP-style left-discord detector?

DAMP (Lu et al., KDD 2022) scores each arriving subsequence by its distance
to the nearest *earlier* subsequence (streaming left matrix profile); the
anomaly is the left-discord argmax. We use stumpy.stumpi (incremental,
z-normalized) and read its left profile — algorithmically DAMP without the
pruning speedups, so identical scores, slower. Matrix profile z-normalizes
every subsequence internally, i.e. it carries its own local normalizer and
feeds on periodic template structure. Hypothesis (RESULTS.md section 1):
the laplace front-end lifts distributional heads (DSPOT) but should NOT
lift a structural head — z destroys the repeated templates the profile
compares against.

Protocol: identical to frontend_run.py (UCR argmax, tolerance max(100, L),
scored region t >= trainLen, prefix tail fed for warm-up only). Subsequence
window m=100 (the tolerance floor; DAMP's auto-window would tune per series
— we hold it fixed for both conditions, which is the comparison that
matters). Discord location reported at the subsequence center.

Usage:
    NUMBA_NUM_THREADS=2 python benchmarks/anomaly/frontend_damp.py \
        --limit 150 --workers 10
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "src"))
from ucr_run import DATA, _NAME, parse_name, load_series  # noqa: E402
from frontend_run import z_series, WARMUP_TAIL  # noqa: E402

M = 100  # subsequence length; also the hit-tolerance floor


def left_discord(xs, train_len, start):
    """Streaming left matrix profile over xs[start:]; return (loc, score) of
    the left-discord argmax among subsequences fully inside the scored
    region [train_len, len(xs))."""
    import numpy as np
    import stumpy
    T = np.asarray(xs[start:], dtype=np.float64)
    seed_len = max(train_len - start, M + 1)
    stream = stumpy.stumpi(T[:seed_len], m=M, egress=False)
    for x in T[seed_len:]:
        stream.update(x)
    lp = stream.left_P_
    best, loc = -1.0, -1
    for i in range(len(lp)):
        t = start + i           # subsequence start index in the full series
        if t < train_len:       # warm-up region: never scored
            continue
        s = lp[i]
        if np.isfinite(s) and s > best:
            best, loc = float(s), t + M // 2
    return loc, best


def run_one(args):
    fname, = args
    sid, name, train_len, a_start, a_end = parse_name(fname)
    ys = load_series(os.path.join(DATA, fname))
    n = len(ys)
    start = max(0, train_len - WARMUP_TAIL)
    t0 = time.time()

    zs = z_series(ys, start)
    tol = max(100, a_end - a_start)
    lo, hi = a_start - tol, a_end + tol
    res = {"sid": sid, "name": name, "n": n}
    for cond, xs in (("raw", ys), ("z", zs)):
        loc, score = left_discord(xs, train_len, start)
        res[f"damp_{cond}"] = {"loc": loc, "score": round(score, 3),
                               "hit": bool(lo <= loc <= hi)}
    res["seconds"] = round(time.time() - t0, 1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(DATA) if _NAME.match(f))
    files.sort(key=lambda f: os.path.getsize(os.path.join(DATA, f)))
    if args.limit:
        files = files[:args.limit]

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       f"frontend_damp_m{M}_n{len(files)}.jsonl")

    # Crash safety + resume: append/fsync per series, skip finished sids.
    keys = ["damp_raw", "damp_z"]
    results = []
    if os.path.exists(out):
        with open(out) as fh:
            results = [json.loads(line) for line in fh if line.strip()]
        done = {r["sid"] for r in results}
        files = [f for f in files if parse_name(f)[0] not in done]
        print(f"resuming {out}: {len(results)} done, {len(files)} to go",
              flush=True)
    total = len(results) + len(files)

    ofh = open(out, "a")
    with Pool(args.workers) as pool:
        for res in pool.imap_unordered(run_one, [(f,) for f in files]):
            results.append(res)
            ofh.write(json.dumps(res) + "\n")
            ofh.flush()
            os.fsync(ofh.fileno())
            hits = {m: sum(r[m]["hit"] for r in results) for m in keys}
            print(f"[{len(results)}/{total}] {res['sid']:03d} "
                  f"{res['name'][:26]:26s} {res['seconds']:6.1f}s  "
                  + "  ".join(f"{m}={'HIT' if res[m]['hit'] else '.'}"
                              for m in keys)
                  + "   running: " + " ".join(f"{m}:{hits[m]}" for m in keys),
                  flush=True)
    ofh.close()

    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        for r in sorted(results, key=lambda r: r["sid"]):
            fh.write(json.dumps(r) + "\n")
    os.replace(tmp, out)

    n = len(results)
    print("\n=== UCR accuracy: DAMP-style left discord, raw vs z ===")
    for m in keys:
        h = sum(r[m]["hit"] for r in results)
        print(f"{m:12s} {h}/{n} = {h/n:.3f}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
