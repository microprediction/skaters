"""Does a Tweedie variance-function coordinate pay, beyond Yeo-Johnson? (NFL ablation, on levels.)

Motivation. `skaters` already learns the *mean coordinate* via the Yeo-Johnson
group (lambda = 1 - p/2: log<->p=2, sqrt<->p=1, identity<->p=0). But Yeo-Johnson
ties the mean coordinate and the variance coordinate to the *same* lambda. The
Tweedie variance function V(mu) = mu^p decouples them: keep an additive
random-walk/EMA mean in level space, but let the predictive *standard deviation*
scale as |level|^(p/2). That is expressiveness Yeo-Johnson cannot reach — an
additive mean with multiplicative (or sqrt, or intermediate) noise.

This is the score-driven / Tweedie reading from papers/tweedie-note.md made into a
transform: `tweedie_scale(p)` standardises each innovation by a power of the
running level, so the leaf sees homoscedastic residuals and the inverse rescales
the predictive spread by |level|^(p/2).

We feed raw LEVELS to two otherwise-identical ensembles:

  base     = laplace's full pool (already includes the Yeo-Johnson group)
  +tweedie = the same pool plus a small grid of tweedie_scale candidates

and compare held-out log-likelihood, split by whether the series is strictly
positive. NFL prediction: +tweedie wins where the mean/variance coordinates
genuinely differ, and is ~neutral elsewhere (a wrong coordinate is down-weighted).

    PYTHONPATH=src python benchmarks/tweedie_ablation.py
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
from skaters.api import _build_candidates
from skaters.terminal import terminal_leaf_ensemble

MIN_LEN = 800
MAX_WORKERS = min(8, (os.cpu_count() or 4))

# Tweedie variance-function grid: p is the Tweedie index, V(mu)=mu^p.
#   p=0   additive / homoscedastic        p=1   sqrt / Poisson-like
#   p=2   multiplicative / GBM-like       (intermediate values interpolate)
# Two EMA rates for the level so the mean tracks at a couple of speeds.
TWEEDIE_GRID = [(p, a) for p in (0.5, 1.0, 1.5, 2.0) for a in (0.05, 0.2)]


def tweedie_scale(p: float = 1.0, alpha: float = 0.1, eps: float = 1e-12):
    """Tweedie variance-function transform: EMA mean, std ~ |level|^(p/2).

    Forward:   level_t = EMA(y);  s_t = |level_t|^(p/2);  y'_t = (y_t - level_t)/s_t
    Inverse:   D -> D.scale(s_t).shift(level_t)   (zero-mean leaf -> N(level, s*sigma))

    The level floor is relative to a running scale (EMA of |y|), so the transform
    is robust to series of very different magnitudes and to levels near zero.
    """
    half = 0.5 * p

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None or not math.isfinite(y):
            y0 = y if math.isfinite(y) else 0.0
            return 0.0, {"level": y0, "scale": abs(y0)}
        level = state["level"] + alpha * (y - state["level"])
        scale = (1 - alpha) * state["scale"] + alpha * abs(y)
        floor = max(1e-3 * scale, eps)
        s = max(abs(level), floor) ** half
        resid = (y - level) / s
        if not math.isfinite(resid):
            resid = 0.0
        return resid, {"level": level, "scale": scale, "s": s}

    def inverse_k(dists: list, state: dict) -> list:
        level = state["level"]
        s = state.get("s", 1.0)
        return [d.scale(s).shift(level) for d in dists]

    return forward, inverse_k


def _base():
    cands, depths, _ = _build_candidates(1)
    return list(cands), list(depths)


def _augmented():
    cands, depths = _base()
    for p, a in TWEEDIE_GRID:
        cands.append(conjugate(leaf(k=1), tweedie_scale(p, a), k=1))
        depths.append(1)
    return cands, depths


def _ensemble(which):
    cands, depths = _augmented() if which == "tweedie" else _base()
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


def score(sid):
    levels = fred._load_levels(sid)
    vals = [v for _, v in levels] if levels else []
    if len(vals) < MIN_LEN:
        return None
    positive = all(v > 0 for v in vals)
    base = _logpdf(lambda: _ensemble("base"), vals)
    twd = _logpdf(lambda: _ensemble("tweedie"), vals)
    if not (math.isfinite(base) and math.isfinite(twd)):
        return None
    return (sid, positive, twd, base)


def main():
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        ids = ids[::max(1, len(ids) // cap)][:cap]  # evenly subsample
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
    for label, sub in [("positive (variance coupling applies)", [r for r in rows if r[1]]),
                       ("signed (should be ~neutral)", [r for r in rows if not r[1]]),
                       ("ALL", rows)]:
        if not sub:
            continue
        diff = np.array([r[2] - r[3] for r in sub])     # tweedie - base
        win = float(np.mean(diff > 0)) * 100
        print(f"\n{label}: n={len(sub)}")
        print(f"  mean logpdf  +tweedie {np.mean([r[2] for r in sub]):+.3f}  "
              f"base {np.mean([r[3] for r in sub]):+.3f}  "
              f"delta {diff.mean():+.4f} nats")
        print(f"  +tweedie better on {win:.0f}% of series")


if __name__ == "__main__":
    main()
