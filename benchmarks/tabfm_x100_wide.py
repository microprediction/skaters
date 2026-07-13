"""TabFM clfx100 at full scale: pre-registered single-arm study.

Statement: benchmarks/preregistrations/2026-07-13-tabfm-x100-wide.md,
committed before this ran. Per series: laplace baseline, clfx100 raw,
clfx100 sandwiched, all under the wide study's scoring (TEST=150,
identical -20 floors).

Usage:
    TB_DEVICE=mps PYTHONPATH=src python benchmarks/tabfm_x100_wide.py
"""
import csv
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

from tabfm_wide_study import (  # noqa: E402
    _load_ch, clf_arm_dists, decile_edges, score_steps, laplace_scores,
    _mps_shim, TEST, WEIGHTS, DEVICE, X100,
)
from tabfm_sandwich_study import _lap_pass, _phi_inv, _EPS, _LOG_SQRT2PI  # noqa: E402

UNIVERSE = os.path.join(_HERE, "preregistrations", "tabfm_x100_universe.txt")
OUT = os.path.join(_HERE, "results_tabfm_x100_wide.csv")
FLOOR = -20.0


def run_one(sid, stratum, model, Clf):
    ch = _load_ch(sid)
    n = len(ch)
    y = ch[n - TEST:]

    lap_lp, lap_crps = laplace_scores(ch)

    # raw clfx100: clf8 on 100x the series, exact affine back
    sch = [X100 * v for v in ch]
    dists = clf_arm_dists(sch, 8, [decile_edges], model, Clf)
    aa, _bb = score_steps(dists, [X100 * v for v in y])
    raw = aa + math.log(X100)

    # sandwich: same machinery on 100x the parade z, affine + Jacobian
    lp = _lap_pass(ch)
    zs, jac = [0.0], [0.0]
    for t in range(1, n):
        d = lp[t]
        u = min(max(d.cdf(ch[t]), _EPS), 1.0 - _EPS)
        z = _phi_inv(u)
        zs.append(z)
        jac.append(d.logpdf(ch[t]) - (-0.5 * z * z - _LOG_SQRT2PI))
    szs = [X100 * v for v in zs]
    zdists = clf_arm_dists(szs, 8, [decile_edges], model, Clf)
    tot = 0
    acc = 0.0
    for i in range(TEST):
        t = n - TEST + i
        lz = zdists[i].logpdf(szs[t]) + math.log(X100)   # z-space, affine back
        acc += max(lz + jac[t], FLOOR)
        tot += 1
    sand = acc / tot
    return lap_lp, raw, sand


def main():
    from tabfm import TabFMClassifier as Clf, tabfm_v1_0_0_pytorch as V
    model = V.load(model_type="classification", checkpoint_path=WEIGHTS,
                   device=None if DEVICE == "cpu" else DEVICE)
    _mps_shim()

    uni = [tuple(l.strip().split(",")) for l in open(UNIVERSE)]
    done = set()
    if os.path.exists(OUT):
        done = {r["series"] for r in csv.DictReader(open(OUT))}
    new = not os.path.exists(OUT)
    fh = open(OUT, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(["series", "ll_laplace", "ll_x100_raw", "ll_x100_sandwich",
                    "n", "stratum"])
        fh.flush()
    todo = [(s, st) for s, st, _f in uni if s not in done]
    for k, (sid, stratum) in enumerate(todo):
        t0 = time.time()
        try:
            lap, raw, sand = run_one(sid, stratum, model, Clf)
        except Exception as e:
            print(f"  FAIL {sid}: {e!r}", flush=True)
            continue
        w.writerow([sid, lap, raw, sand, TEST, stratum])
        fh.flush()
        os.fsync(fh.fileno())
        print(f"  x1 {k + 1}/{len(todo)} {sid} lap={lap:+.3f} raw={raw:+.3f} "
              f"sand={sand:+.3f} ({time.time() - t0:.0f}s)", flush=True)
    fh.close()

    rows = list(csv.DictReader(open(OUT)))
    n = len(rows)
    med = lambda v: sorted(v)[len(v) // 2]  # noqa: E731
    for col in ("ll_x100_raw", "ll_x100_sandwich"):
        d = [float(r[col]) - float(r["ll_laplace"]) for r in rows]
        print(f"{col} vs laplace: median {med(d):+.4f}, "
              f"wins {sum(1 for x in d if x > 0)}/{n}")


if __name__ == "__main__":
    main()
