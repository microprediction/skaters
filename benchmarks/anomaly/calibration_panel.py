"""The calibration panel: re-run the UCR archive for stated-rate accuracy.

Academic TSAD benchmarks score ranking (VUS/AUC, argmax) and are blind to
the operator's question: "if I set the alarm budget to alpha, do I get
alpha?" This harness re-uses their data to measure exactly that, strictly
prequentially:

  FPR panel   On each series' certified anomaly-free prefix (UCR guarantees
              [0, trainLen) is clean), after a burn-in, count alarms at
              nominal alphas {1e-2, 1e-3, 1e-4}. A calibrated method's
              empirical rate matches nominal; an uncalibrated one pages the
              operator at a rate it never promised.
  Delay panel At fixed alpha = 1e-3 on the scored region: false alarms
              before the anomaly, whether the anomaly window [start, end+tol]
              is alarmed at all, and the delay from anomaly start to the
              first alarm inside it.

Methods (all one-pass, no whole-series statistics):
  mah:   p-value of the parade Mahalanobis detector (the method)
  z1:    two-sided normal p of the 1-step parade z (same forecaster; note
         the |z|<=7.03 clamp floors p at ~6e-13, irrelevant for these alphas)
  dspot: DSPOT (frontend_run re-implementation), p = exp(-score); the
         closest rival in spirit — EVT-calibrated alarm rates
  mz:    EWMA z-score with a Gaussian p (the trivial baseline that a naive
         "3-sigma rule" implies)

Usage:
    python benchmarks/anomaly/calibration_panel.py --limit 250 --workers 10
"""

from __future__ import annotations
import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "src"))
from ucr_run import DATA, _NAME, parse_name, load_series  # noqa: E402
from frontend_run import DSpot  # noqa: E402

ALPHAS = (1e-2, 1e-3, 1e-4)
DELAY_ALPHA = 1e-3
# *_z variants are the same heads fed the parade 1-step z instead of raw y:
# the front-end question for job 2 — does the transform make THEIR alarm
# rates match nominal?
METHODS = ("mah", "z1", "dspot", "mz", "dspot_z", "mz_z")


def run_one(args):
    fname, k, scale_alpha, det_alpha = args
    sid, name, train_len, a_start, a_end = parse_name(fname)
    ys = load_series(os.path.join(DATA, fname))
    n = len(ys)
    burn = min(2000, train_len // 2)
    tol = max(100, a_end - a_start)
    win_lo, win_hi = a_start, a_end + tol
    t0 = time.time()

    from skaters import laplace
    from skaters.anomaly import mahalanobis

    f = mahalanobis(laplace(k, scale_alpha=scale_alpha), k=k, alpha=det_alpha)
    state = None
    d = DSpot(list(ys[:burn])) if burn >= 10 else None
    d_z, zcal = None, []                 # fronted DSPOT, calibrated on burn z
    mz_m, mz_v, mz_n = 0.0, 0.0, 0
    mzz_m, mzz_v, mzz_n = 0.0, 0.0, 0    # fronted trivial head
    MZ_ALPHA = 0.02

    clean = {m: {a: 0 for a in ALPHAS} for m in METHODS}
    clean_ticks = 0
    fa_before = {m: 0 for m in METHODS}          # scored region, pre-anomaly
    first_hit = {m: None for m in METHODS}       # first alarm inside window

    for t, y in enumerate(ys):
        ps = {}
        # trivial baseline: score BEFORE update
        mz_n += 1
        a = max(MZ_ALPHA, 1.0 / mz_n)
        sd = math.sqrt(mz_v) if mz_v > 0 else 1e-8
        ps["mz"] = math.erfc((abs(y - mz_m) / sd) / math.sqrt(2.0)) \
            if mz_n > 3 else 1.0
        dd = y - mz_m
        mz_m += a * dd
        mz_v = (1 - a) * mz_v + a * dd * (y - mz_m)

        if d is not None and t >= burn:
            ps["dspot"] = math.exp(-min(d.score(y), 700.0))

        _, state = f(y, state)
        p = state["pvalue"]
        ps["mah"] = p if p is not None else 1.0
        zvec = state["base"]["z"] if isinstance(state["base"], dict) else None
        z = zvec[0] if zvec else None
        ps["z1"] = math.erfc(abs(z) / math.sqrt(2.0)) if z is not None else 1.0

        # fronted heads: same detectors, parade z as the input stream
        zv = z if z is not None else 0.0
        if t < burn:
            zcal.append(zv)
        else:
            if d_z is None and len(zcal) >= 10:
                d_z = DSpot(zcal)
            if d_z is not None:
                ps["dspot_z"] = math.exp(-min(d_z.score(zv), 700.0))
        mzz_n += 1
        a = max(MZ_ALPHA, 1.0 / mzz_n)
        sd = math.sqrt(mzz_v) if mzz_v > 0 else 1e-8
        ps["mz_z"] = math.erfc((abs(zv - mzz_m) / sd) / math.sqrt(2.0)) \
            if mzz_n > 3 else 1.0
        dz = zv - mzz_m
        mzz_m += a * dz
        mzz_v = (1 - a) * mzz_v + a * dz * (zv - mzz_m)

        if burn <= t < train_len:                # certified-clean prefix
            clean_ticks += 1
            for m in METHODS:
                if m in ps:
                    for al in ALPHAS:
                        if ps[m] < al:
                            clean[m][al] += 1
        elif t >= train_len:                     # scored region
            for m in METHODS:
                if m not in ps or ps[m] >= DELAY_ALPHA:
                    continue
                if t < win_lo:
                    fa_before[m] += 1
                elif t <= win_hi and first_hit[m] is None:
                    first_hit[m] = t

    res = {"sid": sid, "name": name, "n": n, "train_len": train_len,
           "anom": [a_start, a_end], "clean_ticks": clean_ticks,
           "seconds": round(time.time() - t0, 1)}
    for m in METHODS:
        res[m] = {"clean_alarms": {f"{al:g}": clean[m][al] for al in ALPHAS},
                  "fa_before": fa_before[m],
                  "delay": (first_hit[m] - a_start)
                  if first_hit[m] is not None else None}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--scale-alpha", type=float, default=0.01)
    ap.add_argument("--det-alpha", type=float, default=0.005)
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(DATA) if _NAME.match(f))
    files.sort(key=lambda f: os.path.getsize(os.path.join(DATA, f)))
    if args.limit:
        files = files[:args.limit]

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"calibration_panel_fronted_sa{args.scale_alpha}_da{args.det_alpha}"
        f"_n{len(files)}.jsonl")

    # Crash safety + resume: append/fsync per series, skip finished sids.
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
        for res in pool.imap_unordered(
                run_one,
                [(f, args.k, args.scale_alpha, args.det_alpha)
                 for f in files]):
            results.append(res)
            ofh.write(json.dumps(res) + "\n")
            ofh.flush()
            os.fsync(ofh.fileno())
            ticks = sum(r["clean_ticks"] for r in results)
            line = " ".join(
                f"{m}:{sum(r[m]['clean_alarms']['0.001'] for r in results)}"
                for m in METHODS)
            print(f"[{len(results)}/{total}] {res['sid']:03d} "
                  f"{res['name'][:26]:26s} {res['seconds']:6.1f}s  "
                  f"clean-alarms@1e-3 per {ticks} ticks: {line}", flush=True)
    ofh.close()

    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        for r in sorted(results, key=lambda r: r["sid"]):
            fh.write(json.dumps(r) + "\n")
    os.replace(tmp, out)

    ticks = sum(r["clean_ticks"] for r in results)
    print(f"\n=== FPR panel: certified-clean prefixes, {ticks} ticks ===")
    print(f"{'method':8s}" + "".join(f"  emp@{al:g} (nominal {al:g})"
                                     for al in ALPHAS))
    for m in METHODS:
        row = f"{m:8s}"
        for al in ALPHAS:
            alarms = sum(r[m]["clean_alarms"][f"{al:g}"] for r in results)
            row += f"  {alarms / ticks:.2e} ({alarms})".ljust(22)
        print(row)
    print(f"\n=== Delay panel @ alpha={DELAY_ALPHA:g} ===")
    for m in METHODS:
        hits = [r[m]["delay"] for r in results if r[m]["delay"] is not None]
        fas = sum(r[m]["fa_before"] for r in results)
        med = sorted(hits)[len(hits) // 2] if hits else None
        print(f"{m:8s} window-alarmed {len(hits)}/{len(results)}, "
              f"median delay {med}, false alarms pre-anomaly {fas}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
