"""Section 10's decisive test on real data, following Section 11's exact
block protocol: block 1 fits the static PIT map G, block 2 fits Theta by
penalized conditional MLE, block 3 (strictly held out) evaluates D (mean
conditional log-score gain over the H0: Theta=0 null) and the mode-
autocorrelation checklist item.

D > 0 on held-out data means the projected transition operator found real,
out-of-sample exploitable structure in the base forecaster's calibrated PIT
stream. D <= 0 means shrink Theta to zero and stay with ordinary rank/PIT
calibration -- Section 10's own falsification rule, not a judgment call.

Usage: PYTHONPATH=src python benchmarks/residual-transform/run_pit_transition.py [fred|waveform|price] [n]
"""
from __future__ import annotations
import math
import os
import statistics as st
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import run_study as rs          # noqa: E402
import pit_transition as pt     # noqa: E402
from skaters import laplace, garch_leaf  # noqa: E402

WARMUP = 100


def _garch_leaf_base():
    return laplace(k=1, leaf=garch_leaf, tails="gaussian")


def _raw_pit_stream(ys, base_factory=None):
    """Run the base skater once over the whole series, returning the raw
    PIT u0_t = F0_{t-1}(y_t) for every resolved tick after warmup."""
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    state = None
    prev = None
    u0 = []
    for t, y in enumerate(ys):
        dists, state = base(y, state)
        if prev is not None and t >= WARMUP:
            u0.append(pt._EPS + (1 - 2 * pt._EPS) * np.clip(prev.cdf(y), 0.0, 1.0))
        prev = dists[0]
    return np.array(u0)


def run_series(ys, base_factory=None, ridge=1.0):
    u0 = _raw_pit_stream(ys, base_factory=base_factory)
    n = len(u0)
    if n < 300:
        return None
    b = n // 3
    u0_block1, u0_block2, u0_block3 = u0[:b], u0[b:2 * b], u0[2 * b:]

    G = pt.StaticG(u0_block1)
    u_block2 = np.array([G(x) for x in u0_block2])
    u_block3 = np.array([G(x) for x in u0_block3])

    theta_hat = pt.fit_theta(u_block2, ridge=ridge)
    D = pt.held_out_D(u_block3, theta_hat)
    ac_before = pt.mode_autocorr(u_block3)

    v_block3 = np.array([pt.cdf(u_block3[t], u_block3[t - 1], theta_hat)
                          for t in range(1, len(u_block3))])
    ac_after = pt.mode_autocorr(v_block3)
    return {
        "n_block3": len(u_block3),
        "theta": theta_hat,
        "D": D,
        "ac_before": ac_before,
        "ac_after": ac_after,
    }


DATASETS = {
    "fred": rs.load_local_series,
    "waveform": rs.load_waveform_series,
    "price": rs.load_price_series,
}


def main(dataset_name="fred", n=50):
    series = DATASETS[dataset_name](n=n)
    base_factory = _garch_leaf_base if dataset_name == "price" else None
    print(f"[pit-transition/{dataset_name}] {len(series)} series", flush=True)
    t0 = time.time()
    Ds, theta22s, ac2_before, ac2_after = [], [], [], []
    for i, (sid, ys) in enumerate(series):
        r = run_series(ys, base_factory=base_factory)
        if r is None:
            print(f"  {i+1}/{len(series)} {sid}: too short, skipped", flush=True)
            continue
        Ds.append(r["D"])
        theta22s.append(r["theta"][1, 1])
        ac2_before.append(r["ac_before"][1])
        ac2_after.append(r["ac_after"][1])
        print(f"  {i+1}/{len(series)} {sid}: D={r['D']:+.5f} theta={r['theta'].round(3).tolist()} "
              f"ac2_before={r['ac_before'][1]:+.3f} ac2_after={r['ac_after'][1]:+.3f} n={r['n_block3']}",
              flush=True)

    n_done = len(Ds)
    print(f"\n[pit-transition/{dataset_name}] n={n_done} series, {time.time()-t0:.1f}s")
    print(f"  D: mean={st.mean(Ds):+.5f}  median={st.median(Ds):+.5f}  frac positive={sum(1 for x in Ds if x>0)/n_done:.2f}")
    print(f"  theta22: mean={st.mean(theta22s):+.4f}  median={st.median(theta22s):+.4f}")
    print(f"  mode-2 autocorr: mean before={st.mean(ac2_before):+.3f}  mean after={st.mean(ac2_after):+.3f}")


if __name__ == "__main__":
    dataset_name = sys.argv[1] if len(sys.argv) > 1 else "fred"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    main(dataset_name, n)
