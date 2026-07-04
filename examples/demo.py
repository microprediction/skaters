"""Demo: the ``laplace`` forecaster on synthetic series.

Runs ``laplace`` online over a few synthetic regimes (random walk with
drift, mean reversion, level shift) and prints per-step forecast
summaries: point forecast (dist.mean), an 80% quantile interval, and the
logpdf of the realized value. Ends with a multi-step ``laplace(k=3)``
example (k=3), scored per horizon.

Usage:
    PYTHONPATH=src python examples/demo.py
"""

import math
import random

from skaters import laplace


def run_online(name, f, series, burn=50, print_every=100):
    """Run a skater online, printing periodic per-step summaries and totals.

    Convention: f(y, state) -> (dists, state), where dists[0] is the
    predictive distribution for the NEXT observation. So each incoming y
    is scored against the prediction issued one step earlier.
    """
    state = None
    prev = None                       # last one-step-ahead predictive Dist
    abs_errors, logpdfs, covered = [], [], []

    print(f"\n{'='*70}")
    print(f"  {name}  ({len(series)} observations, burn-in={burn})")
    print(f"{'='*70}")
    print(f"  {'t':>5} {'y':>9} {'mean':>9} {'q10':>9} {'q90':>9} {'logpdf':>8}")

    for t, y in enumerate(series):
        if prev is not None and t > burn:
            abs_errors.append(abs(prev.mean - y))
            lp = prev.logpdf(y)
            if math.isfinite(lp):
                logpdfs.append(lp)
            lo, hi = prev.quantile(0.1), prev.quantile(0.9)
            covered.append(1 if lo <= y <= hi else 0)
            if t % print_every == 0:
                print(f"  {t:>5} {y:9.3f} {prev.mean:9.3f} {lo:9.3f} {hi:9.3f} {lp:8.3f}")

        dists, state = f(y, state)
        prev = dists[0]

    print(f"  {'-'*58}")
    print(f"  MAE {sum(abs_errors)/len(abs_errors):.4f}"
          f"   mean logpdf {sum(logpdfs)/len(logpdfs):.4f}"
          f"   80% coverage {sum(covered)/len(covered):.1%}")


def run_multistep(name, f, series, k, burn=50):
    """Run a multi-step skater online, scoring each horizon separately.

    A prediction issued at time t for horizon h is scored against
    series[t + h], so forecasts are buffered until their target arrives.
    """
    state = None
    pending = {}                      # target time -> list of (h, Dist)
    abs_errors = {h: [] for h in range(1, k + 1)}
    logpdfs = {h: [] for h in range(1, k + 1)}
    covered = {h: [] for h in range(1, k + 1)}

    for t, y in enumerate(series):
        for h, d in pending.pop(t, []):
            if t > burn:
                abs_errors[h].append(abs(d.mean - y))
                lp = d.logpdf(y)
                if math.isfinite(lp):
                    logpdfs[h].append(lp)
                covered[h].append(1 if d.quantile(0.1) <= y <= d.quantile(0.9) else 0)
        dists, state = f(y, state)
        for h, d in enumerate(dists, start=1):
            pending[t + h] = pending.get(t + h, []) + [(h, d)]

    print(f"\n{'='*70}")
    print(f"  {name}  ({len(series)} observations, k={k}, burn-in={burn})")
    print(f"{'='*70}")
    print(f"  {'horizon':>8} {'MAE':>9} {'mean logpdf':>12} {'80% coverage':>13}")
    for h in range(1, k + 1):
        mae = sum(abs_errors[h]) / len(abs_errors[h])
        mlp = sum(logpdfs[h]) / len(logpdfs[h])
        cov = sum(covered[h]) / len(covered[h])
        print(f"  {h:>8} {mae:9.4f} {mlp:12.4f} {cov:12.1%}")


def main():
    random.seed(42)

    # --- Regime 1: random walk with drift ---
    rw = [0.0]
    for _ in range(699):
        rw.append(rw[-1] + 0.3 + random.gauss(0, 1))
    run_online("laplace on random walk + drift", laplace(k=1), rw)

    # --- Regime 2: mean-reverting (Ornstein-Uhlenbeck) ---
    ou = [0.0]
    for _ in range(699):
        ou.append(ou[-1] * 0.95 + random.gauss(0, 1))
    run_online("laplace on mean-reverting (OU)", laplace(k=1), ou)

    # --- Regime 3: level shift halfway through ---
    shift = [10.0 + random.gauss(0, 2) if t < 350 else 50.0 + random.gauss(0, 2)
             for t in range(700)]
    run_online("laplace on level shift at t=350", laplace(k=1), shift)

    # --- Multi-step: laplace(k>1) is multi-scale by default ---
    run_multistep("laplace(k=3) on random walk + drift", laplace(k=3), rw, k=3)


if __name__ == "__main__":
    main()
