"""Performance release gate: a massive slowdown must fail the suite.

Origin: a well-intentioned one-line change (the extreme-input gate reading
``.mean``/``.std`` off the 1-step predictive each tick) silently made
``laplace`` 20x slower, because those properties on a tail-spliced
predictive were numeric quantile grids. Nothing failed; the suite just took
an hour. These tests convert that class of regression into a red X.

Budgets are ceilings with roughly 10x headroom over healthy timings on a
slow CI runner, so they stay quiet under load and only trip on
order-of-magnitude regressions.
"""
import random
import time

from skaters import laplace
from skaters.dist import Dist
from skaters.tails import SplicedDist


def test_laplace_tick_budget():
    """2,500 ticks of laplace(1), splice active for the back 2,000: under
    10 ms/tick even on a slow machine. Healthy is ~0.3 ms/tick."""
    rng = random.Random(7)
    f = laplace(1)
    state = None
    t0 = time.perf_counter()
    for _ in range(2500):
        _, state = f(rng.gauss(0, 1), state)
    dt = time.perf_counter() - t0
    assert dt < 25.0, f"laplace(1) took {dt:.1f}s for 2500 ticks " \
                      f"({1e3 * dt / 2500:.1f} ms/tick; budget 10 ms/tick)"


def test_spliced_moments_are_amortized():
    """mean/var/std/crps on one SplicedDist share one quantile grid: the
    second read must be near-free, so a per-tick consumer of moments costs
    one grid, not four."""
    d = SplicedDist(Dist.gaussian(0.0, 1.0), -2.054, 2.054,
                    0.02, 0.02, 0.1, 0.6, 0.2, 0.7)
    t0 = time.perf_counter()
    _ = (d.mean, d.var, d.std, d.crps(0.3))
    first = time.perf_counter() - t0
    t0 = time.perf_counter()
    _ = (d.mean, d.var, d.std, d.crps(0.3))
    second = time.perf_counter() - t0
    assert second < first / 5 or second < 1e-3


def test_gate_does_not_pay_for_spliced_moments():
    """The parade's extreme-input gate must read closed-form body moments,
    not the spliced numeric grid: 300 warm ticks in well under a second of
    marginal cost. Guards the exact regression that motivated this file."""
    rng = random.Random(9)
    f = laplace(1)
    state = None
    for _ in range(700):                      # splice active from ~500
        _, state = f(rng.gauss(0, 1), state)
    t0 = time.perf_counter()
    for _ in range(300):
        _, state = f(rng.gauss(0, 1), state)
    dt = time.perf_counter() - t0
    assert dt < 3.0, f"300 warm ticks took {dt:.2f}s (budget 3s)"
