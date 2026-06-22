"""A CIR / OU-on-coordinate mean-reverting component — validate, then ablate.

CIR is a sum of squared OU processes (equivalently a space-time-changed squared
Bessel process): dY = a(b - Y)dt + sigma*sqrt(Y) dW. The single-factor reading is
"OU mean-reversion in the square-root coordinate". So instead of CIR's exact
(Bessel-function) Tweedie score, we build the component from existing grammar:

    y --(Yeo-Johnson lambda)--> coordinate --(OU mean-reversion)--> residual --> leaf

with lambda=0.5 giving the sqrt (CIR-flavoured) coupling and lambda=0 the log
(geometric mean-reverting volatility) coupling. This is a real gap in laplace's
pool: the coordinate group composes Yeo-Johnson only over `difference`/`ema`,
never over a mean-reverting inner model. It targets the regime where `doob`'s
martingale prior is wrong (rates, the VIX, spreads).

`ou_transform` is the new primitive the existing `ar` can't express: `ar` is a
no-intercept RLS regression, so on a positive (non-zero-mean) coordinate it learns
phi~1 and degenerates to a random walk. OU reverts toward a *running mean*.

Two experiments:
  1. SYNTHETIC: simulate mean-reverting positive series (exp-OU and CIR-like).
     The component must clearly beat the base pool here — proof it captures the
     regime.
  2. FRED levels: NFL safety + where it wins on real positive series.

    PYTHONPATH=src python benchmarks/cir_ablation.py                 # synthetic + one-step FRED
    MODE=multistep PYTHONPATH=src python benchmarks/cir_ablation.py  # multi-step synthetic
    MODE=fred_multistep H=5 PYTHONPATH=src python benchmarks/cir_ablation.py

FINDINGS (held-out log-likelihood, delta = cir - base).
  * Synthetic, validated: the OU component never loses where reversion is real,
    and the edge is monotone in reversion speed kappa (one-step exp-OU:
    +0.009 at kappa=0.05, +0.071 at kappa=0.40).
  * One-step FRED (positive levels): NFL-safe but negligible, +0.0006 nats
    (90% of series better; signed series +0.0002, i.e. no harm). Realistic
    series revert slowly, so the one-step edge ~ kappa is tiny.
  * Multi-step is the thesis. On slow exp-OU the edge GROWS with horizon:
    +0.009 (h=1) -> +0.036 (h=5) -> +0.066 (h=10); CIR-sqrt similar. This is
    1 - phi^h compounding, and it is invisible to skaters' one-step benchmarks.
  * Multi-step FRED (h=5, positive): aggregate negligible (+0.0005) because the
    universe is mostly random-walk-like prices, BUT the wins concentrate exactly
    on mean-reverting volatility indices -- RVXCLS (+0.023), EVZCLS (+0.012).
  Verdict: a targeted instrument, the mean-reverting sibling of `doob` -- NFL-safe
  to add, pays off multi-step on genuinely reverting positive series (vol, rates).
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import yeo_johnson
from skaters.api import _build_candidates
from skaters.terminal import terminal_leaf_ensemble

MIN_LEN = 800
MAX_WORKERS = min(8, (os.cpu_count() or 4))

# OU mean-reversion in {sqrt, log} coordinate, a couple of reversion speeds.
OU_GRID = [(L, kappa, 0.02) for L in (0.0, 0.5) for kappa in (0.03, 0.1, 0.3)]


def ou_transform(kappa: float = 0.1, alpha: float = 0.02):
    """Ornstein-Uhlenbeck mean-reversion as a bijective transform.

    Maintains a running mean m (EMA, rate alpha) and reverts the current value
    toward it with persistence phi = 1 - kappa:

        forecast_t   = m + phi * (y_t - m)         (one-step-ahead)
        residual_t   = y_t - forecast_{t-1}

    kappa in (0,1] is the reversion speed: kappa->0 is a random walk (no
    reversion), kappa=1 reverts fully to the mean in one step. Unlike `ar`,
    reversion is toward a nonzero running level, so it works in a positive
    coordinate (sqrt/log), which is exactly the OU-on-coordinate view of CIR.
    """
    assert 0.0 < kappa <= 1.0
    phi = 1.0 - kappa

    def forward(y: float, state: dict | None):
        if state is None or not math.isfinite(y):
            y0 = y if math.isfinite(y) else 0.0
            return 0.0, {"m": y0, "fc": y0, "y": y0}
        resid = y - state["fc"]
        m = state["m"] + alpha * (y - state["m"])
        fc = m + phi * (y - m)
        if not math.isfinite(resid):
            resid = 0.0
        return resid, {"m": m, "fc": fc, "y": y}

    def inverse_k(dists: list, state: dict):
        m, ylast = state["m"], state["y"]
        out = []
        for h, d in enumerate(dists, start=1):
            center = m + (phi ** h) * (ylast - m)   # h-step reverted mean
            # OU multi-step predictive sd: sigma * sqrt((1-phi^2h)/(1-phi^2)),
            # which saturates at the stationary sd (phi<1) and -> sqrt(h) as phi->1 (RW).
            if phi < 1.0 - 1e-9:
                g = math.sqrt((1.0 - phi ** (2 * h)) / (1.0 - phi * phi))
            else:
                g = math.sqrt(h)
            out.append(d.scale(g).shift(center))   # leaf is zero-mean, so scale hits sd only
        return out

    return forward, inverse_k


def _cir_candidate(L, kappa, alpha):
    # y -> Yeo-Johnson(L) -> OU(kappa) -> leaf
    return conjugate(conjugate(leaf(k=1), ou_transform(kappa, alpha), k=1),
                     yeo_johnson(L), k=1)


def _base():
    cands, depths, _ = _build_candidates(1)
    return list(cands), list(depths)


def _augmented():
    cands, depths = _base()
    for L, kappa, a in OU_GRID:
        cands.append(_cir_candidate(L, kappa, a))
        depths.append(2)
    return cands, depths


def _ensemble(which):
    cands, depths = _augmented() if which == "cir" else _base()
    return terminal_leaf_ensemble(cands, k=1, learning_rate=0.8,
                                  complexity_penalty=0.005, depths=depths,
                                  max_components=20)


def _logpdf(make, series, burn=300):
    f = make()
    state = None
    pend = None
    lp = 0.0
    n = 0
    for i, y in enumerate(series):
        if pend is not None and i > burn:
            v = pend[0].logpdf(y)
            lp += v if math.isfinite(v) else -20.0
            n += 1
        d, state = f(y, state)
        pend = d
    return lp / n if n else float("nan")


# --------------------------------------------------------------------------
# 1. Synthetic mean-reverting positive series
# --------------------------------------------------------------------------

def _lcg(seed):
    x = seed & 0xFFFFFFFF
    while True:
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        u1 = (x + 1) / 0x80000000
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        u2 = x / 0x80000000
        yield math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def sim_exp_ou(seed, n=1500, kappa=0.05, mu=3.0, sig=0.15):
    """Geometric mean-reverting (log-OU): positive, reverts in log-space."""
    g = _lcg(seed)
    x = mu
    out = []
    for _ in range(n):
        x = x + kappa * (mu - x) + sig * next(g)
        out.append(math.exp(x))
    return out


def sim_cir(seed, n=1500, a=0.03, b=20.0, sig=1.2):
    """CIR (Euler, reflected at 0): positive, sqrt diffusion."""
    g = _lcg(seed)
    y = b
    out = []
    for _ in range(n):
        y = y + a * (b - y) + sig * math.sqrt(max(y, 1e-6)) * next(g)
        y = abs(y)
        out.append(y)
    return out


def synthetic():
    print("=== SYNTHETIC mean-reverting positive series (delta = cir - base) ===")
    for name, gen in [("exp-OU (log mean-revert)", sim_exp_ou), ("CIR (sqrt)", sim_cir)]:
        db, dc = [], []
        for s in range(6):
            ser = gen(1234 + 7919 * s)
            db.append(_logpdf(lambda: _ensemble("base"), ser))
            dc.append(_logpdf(lambda: _ensemble("cir"), ser))
        import statistics as st
        delta = st.mean(c - b for c, b in zip(dc, db))
        print(f"  {name:26s}  base {st.mean(db):+.3f}  cir {st.mean(dc):+.3f}  "
              f"delta {delta:+.4f} nats  ({sum(c>b for c,b in zip(dc,db))}/6 wins)")


# --------------------------------------------------------------------------
# 2. FRED levels ablation
# --------------------------------------------------------------------------

def score(sid):
    levels = fred._load_levels(sid)
    vals = [v for _, v in levels] if levels else []
    if len(vals) < MIN_LEN:
        return None
    positive = all(v > 0 for v in vals)
    base = _logpdf(lambda: _ensemble("base"), vals)
    cir = _logpdf(lambda: _ensemble("cir"), vals)
    if not (math.isfinite(base) and math.isfinite(cir)):
        return None
    return (sid, positive, cir, base)


def fred_ablation():
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        ids = ids[::max(1, len(ids) // cap)][:cap]
    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, s): s for s in ids}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r:
                rows.append(r)
            if done % 50 == 0:
                print(f"  {done}/{len(ids)} scored", flush=True)

    import numpy as np
    print("\n=== FRED levels (delta = cir - base) ===")
    for label, sub in [("positive (target regime)", [r for r in rows if r[1]]),
                       ("signed", [r for r in rows if not r[1]]),
                       ("ALL", rows)]:
        if not sub:
            continue
        diff = np.array([r[2] - r[3] for r in sub])
        win = float(np.mean(diff > 0)) * 100
        print(f"\n{label}: n={len(sub)}")
        print(f"  mean logpdf  +cir {np.mean([r[2] for r in sub]):+.3f}  "
              f"base {np.mean([r[3] for r in sub]):+.3f}  "
              f"delta {diff.mean():+.4f} nats  (median {np.median(diff):+.4f})")
        print(f"  +cir better on {win:.0f}% of series")
    pos = [r for r in rows if r[1]]
    if pos:
        top = sorted(pos, key=lambda r: r[2] - r[3], reverse=True)[:8]
        print("\n  biggest +cir wins (positive series):")
        for sid, _, c, b in top:
            print(f"    {sid:28s} delta {c-b:+.3f}")


# --------------------------------------------------------------------------
# 3. Multi-step: does the OU edge grow with horizon? (the component's thesis)
# --------------------------------------------------------------------------

def _ensemble_k(which, k):
    cands, depths, _ = _build_candidates(k)
    cands, depths = list(cands), list(depths)
    if which == "cir":
        for L, kappa, a in OU_GRID:
            cands.append(conjugate(conjugate(leaf(k=k), ou_transform(kappa, a), k=k),
                                   yeo_johnson(L), k=k))
            depths.append(2)
    return terminal_leaf_ensemble(cands, k=k, learning_rate=0.8,
                                  complexity_penalty=0.005, depths=depths,
                                  max_components=20)


def _logpdf_h(make, series, k, h, burn=300):
    """Held-out log-likelihood of the h-step-ahead Dist (rolling)."""
    f = make()
    state = None
    preds = {}
    lp = 0.0
    n = 0
    for t, y in enumerate(series):
        src = t - h
        if src in preds and t > burn:
            v = preds[src][h - 1].logpdf(y)
            lp += v if math.isfinite(v) else -20.0
            n += 1
        dists, state = f(y, state)
        preds[t] = dists
        preds.pop(t - h - 1, None)
    return lp / n if n else float("nan")


def multistep(ks=(1, 5, 10), seeds=6):
    import statistics as st
    print("=== MULTI-STEP synthetic (delta = cir - base, evaluated at h=k) ===")
    for name, gen in [("exp-OU slow (kappa=0.05)", sim_exp_ou), ("CIR (sqrt)", sim_cir)]:
        for k in ks:
            db, dc = [], []
            for s in range(seeds):
                ser = gen(1234 + 7919 * s)
                db.append(_logpdf_h(lambda: _ensemble_k("base", k), ser, k, k))
                dc.append(_logpdf_h(lambda: _ensemble_k("cir", k), ser, k, k))
            delta = st.mean(c - b for c, b in zip(dc, db))
            print(f"  {name:24s} h={k:2d}  base {st.mean(db):+.3f}  "
                  f"cir {st.mean(dc):+.3f}  delta {delta:+.4f} nats  "
                  f"({sum(c > b for c, b in zip(dc, db))}/{seeds})")


def _score_h(args):
    sid, h = args
    levels = fred._load_levels(sid)
    vals = [v for _, v in levels] if levels else []
    if len(vals) < MIN_LEN or not all(v > 0 for v in vals):   # positive series only
        return None
    base = _logpdf_h(lambda: _ensemble_k("base", h), vals, h, h)
    cir = _logpdf_h(lambda: _ensemble_k("cir", h), vals, h, h)
    if not (math.isfinite(base) and math.isfinite(cir)):
        return None
    return (sid, cir, base)


def fred_multistep(h=5):
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    cap = int(os.environ.get("MAX_SERIES", "120"))
    ids = ids[::max(1, len(ids) // cap)][:cap]
    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(_score_h, (s, h)): s for s in ids}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r:
                rows.append(r)
            if done % 25 == 0:
                print(f"  {done}/{len(ids)} scored", flush=True)
    import numpy as np
    diff = np.array([c - b for _, c, b in rows])
    print(f"\n=== FRED positive levels, h={h} (delta = cir - base), n={len(rows)} ===")
    print(f"  mean logpdf  +cir {np.mean([c for _,c,b in rows]):+.3f}  "
          f"base {np.mean([b for _,c,b in rows]):+.3f}  "
          f"delta {diff.mean():+.4f} nats  (median {np.median(diff):+.4f})")
    print(f"  +cir better on {float(np.mean(diff > 0)) * 100:.0f}% of series")
    for sid, c, b in sorted(rows, key=lambda r: r[1] - r[2], reverse=True)[:8]:
        print(f"    {sid:28s} delta {c-b:+.3f}")


if __name__ == "__main__":
    mode = os.environ.get("MODE", "all")
    if mode == "fred_multistep":
        fred_multistep(int(os.environ.get("H", "5")))
        sys.exit(0)
    if mode in ("synthetic", "all"):
        synthetic()
    if mode in ("multistep", "all"):
        multistep()
    if mode == "all" and os.environ.get("SKIP_FRED") != "1":
        fred_ablation()
