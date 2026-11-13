"""Example: forecasting a series you know is positive.

``laplace`` forecasts in the series' own coordinates, so on a positive series
that drifts toward zero it can put probability below zero. If you know the
series is positive (a rate, a price, a volume, a volatility), say so:
``gibrat`` forecasts log(y) with ``laplace`` and maps the predictive back
through exp exactly, so every quantile it reports is positive and its logpdf
includes the Jacobian.

``gibrat(lower=b)`` moves the bound to b, and ``gibrat(upper=b)`` makes it a
ceiling. The same thing by hand is
``conjugate(laplace(), log_transform(lower=0.0))``.

The built-in ``yeo_johnson(0, exact=True)`` uses log1p, so it bounds the
predictive at -1 rather than 0. On a series near 0.05, log1p is nearly the
identity and the bound does little; the last row below shows it.

Usage:
    PYTHONPATH=src python examples/positive_series.py
"""

import math
import random

from skaters import gibrat, laplace
from skaters.conjugate import conjugate
from skaters.transform import yeo_johnson


def positive_series(n=600, seed=7):
    """A mean-reverting rate on the log scale: positive, often close to zero,
    with noise proportional to its level. The series is built on the log scale,
    so the comparison below favours gibrat by construction. It demonstrates
    the mechanics; benchmark numbers live in benchmarks/."""
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
    run("laplace()", laplace(), ys)
    run("gibrat()", gibrat(), ys)
    run("laplace on log1p(y)", conjugate(laplace(), yeo_johnson(0.0, exact=True), k=1), ys)
    print()
