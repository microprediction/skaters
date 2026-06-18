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

from skaters.leaf import leaf, scale_mixture_leaf, crps_leaf
from skaters.conjugate import conjugate
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.bayesian import bayesian_ensemble
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform, theta,
    drift, holt_linear, garch, seasonal_difference, power_transform, ar,
    grouped_ar, yeo_johnson,
)
from skaters.api import laplace, doob
from skaters.sticky import sticky
from skaters.search import search as adaptive_search
from skaters import spec as S
from skaters.periodicity import period_detector
from skaters.cov import running_cov, ema_cov, ledoit_wolf_cov

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
        s.append((f"yeojohnson_log{suf}", k, conjugate(leaf(k=k), yeo_johnson(0.0), k=k)))
        s.append((f"yeojohnson_half{suf}", k, conjugate(leaf(k=k), yeo_johnson(0.5), k=k)))
        s.append((f"ema_skater{suf}", k, ema(0.05, k=k)))
        s.append((f"pw_ensemble{suf}", k,
                  precision_weighted_ensemble([ema(0.05, k=k), ema(0.2, k=k)], k=k)))
        s.append((f"bayes_ensemble{suf}", k, bayesian_ensemble(
            [ema(0.05, k=k), conjugate(leaf(k=k), difference(), k=k)],
            k=k, learning_rate=0.5, complexity_penalty=0.02, depths=[1, 1])))

    # Named policies (the full shared-pool ensembles)
    for nm, fac in [("laplace", laplace), ("doob", doob)]:
        s.append((f"pol_{nm}", 1, fac(k=1)))

    # Adaptive-search engine (still public via skaters.search)
    s.append(("search_default", 1, adaptive_search(k=1, expand_interval=50)))

    # Spec-built skaters (exercise the spec/build path)
    spec_conj = S.conjugate_spec(
        S.ensemble_spec(S.ema_spec(0.01, 1), S.ema_spec(0.1, 1), k=1), S.diff_spec())
    s.append(("spec_diff_ensemble", 1, S.build(spec_conj)))
    s.append(("spec_ema", 1, S.build(S.ema_spec(0.05, 1))))

    # Scale-mixture leaf (the discrepancy-from-N(0,1) residual model)
    s.append(("scale_mixture_leaf", 1, scale_mixture_leaf(k=1)))
    s.append(("crps_leaf", 1, crps_leaf(k=1)))
    s.append(("scalemix_ema", 1,
              conjugate(scale_mixture_leaf(k=1), ema_transform(0.1), k=1)))
    return s


def make_vec_series(n=120, seed=7):
    random.seed(seed)
    out = []
    for _ in range(n):
        a = random.gauss(0, 1)
        b = 0.5 * a + random.gauss(0, 1)
        c = random.gauss(0, 1) + 0.2 * b
        out.append([a, b, c])
    return out


def make_repeat_series(n=150, seed=99):
    # Exact repeats (sticky) plus 0.25-grid jumps (all exactly float-representable,
    # so y == last matches bit-for-bit in Python and JS).
    random.seed(seed)
    out = []
    v = 1.0
    for _ in range(n):
        if random.random() >= 0.7:
            v += random.choice([-0.25, 0.25, 0.5])
        out.append(v)
    return out


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
             d.quantile(Q_LO), d.quantile(Q_HI), d.crps(PROBE))]


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

    # Periodicity detector: dump the ranked (lag, acf) scores per step.
    pd = period_detector()
    pd_state = None
    pd_out = []
    for i, y in enumerate(series):
        scores, pd_state = pd(y, pd_state)
        if i >= BURN:
            pd_out.append([[L, clean(acf)] for L, acf in scores])
    vectors["periodicity"] = pd_out

    # Covariance estimators on a fixed multivariate series.
    vec_series = make_vec_series()
    vectors["vec_series"] = vec_series
    cov = {}
    for nm, fn in [("running", lambda y, st: running_cov(y, st)),
                   ("ema", lambda y, st: ema_cov(y, st)),
                   ("ledoit", lambda y, st: ledoit_wolf_cov(y, st))]:
        st = None
        out = []
        for i, y in enumerate(vec_series):
            mean, cmat, st = fn(y, st)
            if i >= BURN:
                out.append([[clean(v) for v in mean], [clean(v) for v in cmat]])
        cov[nm] = out
    vectors["cov"] = cov

    # Sticky/dirac: a repeat-heavy series (exact repeats + grid jumps) so the
    # near-Dirac spike path is exercised, not just pass-through.
    rep = make_repeat_series()
    vectors["repeat_series"] = rep
    rep_scen = {
        "sticky_ema": (1, sticky(conjugate(leaf(k=1), ema_transform(0.1), k=1), k=1)),
    }
    vectors["repeat_scenarios"] = {
        name: {"k": k, "out": run_scenario(sk, rep)} for name, (k, sk) in rep_scen.items()
    }

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "vectors.json")
    with open(path, "w") as f:
        json.dump(vectors, f, allow_nan=False)
    print(f"wrote {path}: {len(vectors['scenarios'])} scenarios, "
          f"{len(series) - BURN} scored steps each")


if __name__ == "__main__":
    main()
