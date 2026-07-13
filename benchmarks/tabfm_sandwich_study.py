"""TabFM sandwich and body: exploratory follow-up to the wide study.

Statement: benchmarks/preregistrations/2026-07-13-tabfm-sandwich-body.md
(committed before this ran). Three log-likelihoods per series, identical
flooring, strictly causal throughout:

    laplace   plain laplace(1), the wide study's opponent
    sandwich  TabFM regressor on lagged parade z; its z-space residual
              density mapped back exactly:
              log f_y(y) = log f_z(z) + log f_lap(y) - log phi(z)
    body      TabFM regressor points p_t on raw lags; laplace consumes
              the residual stream y_t - p_t; predictive = residual
              density shifted by p_t (logpdf equals the residual
              density's logpdf at the residual)

Usage:
    TB_DEVICE=mps PYTHONPATH=src python benchmarks/tabfm_sandwich_study.py
"""
import csv
import math
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

from tabfm_wide_study import (  # noqa: E402
    load_universe, _load_ch, reg_arm, _mps_shim, TEST, WEIGHTS, DEVICE,
)
from skaters import laplace  # noqa: E402

OUT = os.path.join(_HERE, "results_tabfm_sandwich.csv")
FLOOR = -20.0
WARM_BODY = 150            # one extra truncated pass = 150 pre-test points
_EPS = 1e-12
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)


def _phi_inv(u):
    # coarse bisection is fine here; z only feeds TabFM features/Jacobian
    from skaters.tails import _phi_inv as f
    return f(u)


def _lap_pass(series):
    """One laplace(1) pass: per-step 1-step-ahead predictive for each y_t
    (None for t=0) aligned with series indices."""
    f = laplace(1)
    st = None
    pend = None
    dists = []
    for y in series:
        dists.append(pend)
        d, st = f(y, st)
        pend = d[0]
    return dists


def run_one(sid, stratum, model, Reg):
    ch = _load_ch(sid)
    n = len(ch)
    y = np.array(ch[n - TEST:])

    # ---- laplace pass on raw y: baseline LL, z stream, Jacobian pieces ----
    lp = _lap_pass(ch)
    ll_lap, lap_logf, zs = [], [], [0.0]
    for t in range(1, n):
        d = lp[t]
        u = min(max(d.cdf(ch[t]), _EPS), 1.0 - _EPS)
        zs.append(_phi_inv(u))
        if t >= n - TEST:
            v = max(d.logpdf(ch[t]), FLOOR)
            ll_lap.append(v)
            lap_logf.append(d.logpdf(ch[t]))
    zs = np.array(zs)

    # ---- sandwich: TabFM regressor in z-space, exact Jacobian back ----
    zdists, _ = reg_arm(list(zs), 8, model, Reg)
    ll_sand = []
    for i in range(TEST):
        t = n - TEST + i
        z = zs[t]
        lfz = zdists[i].logpdf(z)
        lphi = -0.5 * z * z - _LOG_SQRT2PI
        ll_sand.append(max(lfz + lap_logf[i] - lphi, FLOOR))

    # ---- body: TabFM points on raw lags, laplace on the residuals ----
    _, pts_pre = reg_arm(ch[: n - TEST], 8, model, Reg)   # covers pre-test 150
    _, pts_test = reg_arm(ch, 8, model, Reg)              # covers test 150
    pts = np.array(list(pts_pre) + list(pts_test))
    resid = np.array(ch[n - TEST - WARM_BODY:]) - pts
    rdists = _lap_pass(list(resid))
    ll_body = []
    for i in range(TEST):
        d = rdists[WARM_BODY + i]
        ll_body.append(max(d.logpdf(resid[WARM_BODY + i]), FLOOR))

    return (float(np.mean(ll_lap)), float(np.mean(ll_sand)),
            float(np.mean(ll_body)))


def main():
    from tabfm import TabFMRegressor as Reg, tabfm_v1_0_0_pytorch as V
    model = V.load(model_type="regression", checkpoint_path=WEIGHTS,
                   device=None if DEVICE == "cpu" else DEVICE)
    _mps_shim()

    universe = load_universe()
    done = set()
    if os.path.exists(OUT):
        done = {r["series"] for r in csv.DictReader(open(OUT))}
    new = not os.path.exists(OUT)
    fh = open(OUT, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(["series", "ll_laplace", "ll_sandwich", "ll_body",
                    "n", "stratum"])
        fh.flush()

    for j, (sid, stratum) in enumerate(universe):
        if sid in done:
            continue
        t0 = time.time()
        try:
            lap, sand, body = run_one(sid, stratum, model, Reg)
        except Exception as e:                     # log and continue
            print(f"  FAIL {sid}: {e!r}", flush=True)
            continue
        w.writerow([sid, lap, sand, body, TEST, stratum])
        fh.flush()
        os.fsync(fh.fileno())
        print(f"  sb {j + 1}/{len(universe)} {sid} lap={lap:+.3f} "
              f"sand={sand:+.3f} body={body:+.3f} ({time.time() - t0:.0f}s)",
              flush=True)
    fh.close()

    rows = list(csv.DictReader(open(OUT)))
    n = len(rows)
    for arm in ("ll_sandwich", "ll_body"):
        d = sorted(float(r[arm]) - float(r["ll_laplace"]) for r in rows)
        wins = sum(1 for x in d if x > 0)
        print(f"{arm} vs laplace: median {d[n // 2]:+.4f}, wins {wins}/{n}")


if __name__ == "__main__":
    main()
