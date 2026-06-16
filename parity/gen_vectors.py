"""Generate parity test vectors from the Python implementation.

Runs a registry of scenarios on a fixed input series and dumps, for every
post-burn-in step and horizon, a small set of distributional probes
(mean, std, logpdf, cdf, two quantiles). The JS checker (check.mjs) rebuilds
the same-named scenarios, runs them on the identical series, and asserts
agreement. The series is embedded in the JSON so both sides use the exact
same floats.

Run:  python parity/gen_vectors.py   (writes parity/vectors.json)
"""

from __future__ import annotations
import json
import math
import os
import random

from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.bayesian import bayesian_ensemble
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform, theta,
    drift, holt_linear, garch, seasonal_difference, power_transform, ar,
    grouped_ar,
)

BURN = 10
PROBE = 0.3
Q_LO = 0.1
Q_HI = 0.9


def make_series(n=150, seed=12345):
    random.seed(seed)
    series = []
    lvl = 0.0
    for t in range(n):
        lvl += random.gauss(0, 0.3)
        val = lvl + 2.0 * math.sin(2 * math.pi * t / 7) + random.gauss(0, 1.0)
        series.append(val)
    return series


def build_scenarios():
    """Return list of (name, k, skater). Names must match scenarios.mjs."""
    s = []
    for k in (1, 3):
        suf = "" if k == 1 else f"_k{k}"
        s.append((f"leaf{suf}", k, leaf(k=k)))
        s.append((f"diff{suf}", k, conjugate(leaf(k=k), difference(), k=k)))
        s.append((f"ema_t{suf}", k, conjugate(leaf(k=k), ema_transform(0.1), k=k)))
        s.append((f"standardize{suf}", k, conjugate(leaf(k=k), standardize(), k=k)))
        s.append((f"theta{suf}", k, conjugate(leaf(k=k), theta(0.1), k=k)))
        s.append((f"drift{suf}", k, conjugate(leaf(k=k), drift(0.05, 0.01), k=k)))
        s.append((f"holt{suf}", k, conjugate(leaf(k=k), holt_linear(0.1, 0.05), k=k)))
        s.append((f"garch{suf}", k, conjugate(leaf(k=k), garch(), k=k)))
        s.append((f"seasonal{suf}", k, conjugate(leaf(k=k), seasonal_difference(7), k=k)))
        s.append((f"power{suf}", k, conjugate(leaf(k=k), power_transform(0.5), k=k)))
        s.append((f"ar1{suf}", k, conjugate(leaf(k=k), ar(1), k=k)))
        s.append((f"ar2{suf}", k, conjugate(leaf(k=k), ar(2, decay=1), k=k)))
        s.append((f"frac{suf}", k, conjugate(leaf(k=k), fractional_difference(0.4, 30), k=k)))
        s.append((f"grouped_ar{suf}", k, conjugate(leaf(k=k), grouped_ar(8), k=k)))
        s.append((f"ema_skater{suf}", k, ema(0.05, k=k)))
        s.append((f"pw_ensemble{suf}", k,
                  precision_weighted_ensemble([ema(0.05, k=k), ema(0.2, k=k)], k=k)))
        s.append((f"bayes_ensemble{suf}", k, bayesian_ensemble(
            [ema(0.05, k=k), conjugate(leaf(k=k), difference(), k=k)],
            k=k, learning_rate=0.5, complexity_penalty=0.02, depths=[1, 1])))
    return s


def clean(x):
    # JS JSON.parse rejects Infinity/NaN; encode them as string sentinels.
    if x != x:
        return "nan"
    if x == float("inf"):
        return "inf"
    if x == float("-inf"):
        return "-inf"
    return x


def probe_dist(d):
    return [clean(v) for v in
            (d.mean, d.std, d.logpdf(PROBE), d.cdf(PROBE),
             d.quantile(Q_LO), d.quantile(Q_HI))]


def run_scenario(skater, series):
    state = None
    out = []
    for i, y in enumerate(series):
        dists, state = skater(y, state)
        if i >= BURN:
            out.append([probe_dist(d) for d in dists])
    return out


def main():
    series = make_series()
    vectors = {"series": series, "burn": BURN, "probe": PROBE,
               "q_lo": Q_LO, "q_hi": Q_HI, "scenarios": {}}
    for name, k, skater in build_scenarios():
        vectors["scenarios"][name] = {"k": k, "out": run_scenario(skater, series)}
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "vectors.json")
    with open(path, "w") as f:
        json.dump(vectors, f, allow_nan=False)
    print(f"wrote {path}: {len(vectors['scenarios'])} scenarios, "
          f"{len(series) - BURN} scored steps each")


if __name__ == "__main__":
    main()
