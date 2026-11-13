"""Example: forecasting a series you know is positive.

``laplace`` forecasts in the series' own coordinates, so on a positive series
that drifts toward zero it can put probability below zero. If you know the
series is positive (a rate, a price, a volume, a volatility), say so with a
transform: forecast log(y), then map the predictive back through exp.

``conjugate(skater, transform)`` does the bookkeeping. The transform is a
(forward, inverse_k) pair. Here the inverse uses the exact change of
variables (:class:`skaters.pushforward.PushforwardDist`), so the predictive
in y keeps the right skew and its logpdf includes the Jacobian. Every
quantile it reports is positive.

The library's ``yeo_johnson(0, exact=True)`` is the packaged version of the
same idea (it uses log1p, so it bounds the predictive below by -1 rather than
0, and also accepts negative values).

Usage:
    PYTHONPATH=src python examples/positive_series.py
"""

import math
import random

from skaters import laplace
from skaters.conjugate import conjugate
from skaters.pushforward import PushforwardDist, table_from_map


def log_transform():
    """forward: y -> log(y); inverse: exact pushforward through exp."""

    def forward(y, state):
        return math.log(y), state or {}

    def inverse_k(dists, state):
        out = []
        exp = lambda z: math.exp(min(z, 700.0))
        for d in dists:
            # table range: well past the predictive's own extreme quantiles
            lo, hi = d.quantile(1e-6), d.quantile(1 - 1e-6)
            pad = hi - lo
            ys, zs = table_from_map(exp, lo - pad, hi + pad)
            out.append(PushforwardDist(d, ys, zs, inv_fn=exp))
        return out

    return forward, inverse_k


def positive_series(n=600, seed=7):
    """A mean-reverting rate on the log scale: positive, often close to zero,
    with noise proportional to its level. The series is built on the log scale,
    so the comparison below favours the log transform by construction. It
    demonstrates the mechanics; benchmark numbers live in benchmarks/."""
    rng = random.Random(seed)
    x, out = math.log(0.5), []
    for t in range(n):
        target = math.log(0.05) if 250 <= t < 400 else math.log(0.5)
        x += 0.05 * (target - x) + 0.15 * rng.gauss(0.0, 1.0)
        out.append(math.exp(x))
    return out


def run(name, f, series, burn=100):
    state, prev = None, None
    lps, below_zero, covered = [], [], []
    for t, y in enumerate(series):
        if prev is not None and t > burn:
            lps.append(prev.logpdf(y))
            below_zero.append(prev.cdf(0.0))
            covered.append(prev.quantile(0.1) <= y <= prev.quantile(0.9))
        dists, state = f(y, state)
        prev = dists[0]
    n = len(lps)
    print(f"  {name:<22} mean logpdf {sum(lps)/n:7.3f}"
          f"   80% coverage {sum(covered)/n:6.1%}"
          f"   max P(Y<0) {max(below_zero):.3f}"
          f"   next q10 {prev.quantile(0.1):.4f}")


if __name__ == "__main__":
    ys = positive_series()
    print(f"\n  {len(ys)} positive observations, min {min(ys):.4f}, max {max(ys):.4f}\n")
    run("laplace (levels)", laplace(), ys)
    run("laplace on log(y)", conjugate(laplace(), log_transform(), k=1), ys)
    print()
