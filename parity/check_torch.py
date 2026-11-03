"""Parity check for the torch port against parity/vectors.json, the twin of
check.mjs: every scenario is rebuilt from skaters.torch, run over the fixed
series, probed (mean, std, logpdf, cdf, two quantiles, crps) at every
post-burn-in step and horizon, and compared at ATOL = RTOL = 1e-6, the
gate every other port passes. The repeat-series (sticky), gap-series
(missing observations), periodicity and pool-structure sections are checked
too. The restore-and-continue leg uses a deep copy of the state at the
burn-in step, the torch analogue of the JSON/pickle round trip.

    PYTHONPATH=src .venv-kumo/bin/python parity/check_torch.py [--only name,...]

Exits non-zero on any mismatch. Scenarios whose torch module is not yet
ported are reported as MISSING, not silently skipped.
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys

import torch

ATOL = RTOL = 1e-6
HERE = os.path.dirname(os.path.abspath(__file__))


def decode(x):
    return {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}.get(x, x) if isinstance(x, str) else x


def close(actual, expected_raw):
    e = decode(expected_raw)
    if isinstance(actual, torch.Tensor):
        actual = float(actual)
    if math.isnan(actual) and math.isnan(e):
        return True
    if not (math.isfinite(actual) and math.isfinite(e)):
        return actual == e
    return abs(actual - e) <= ATOL + RTOL * abs(e)


def probe_dist(d, probe, q_lo, q_hi):
    return [d.mean, d.std, d.logpdf(probe), d.cdf(probe), d.quantile(q_lo), d.quantile(q_hi), d.crps(probe)]


def run_scenario(skater, series, burn, probe, q_lo, q_hi, restore_at=-1):
    state = None
    out = []
    with torch.no_grad():
        for i, y in enumerate(series):
            y = decode(y)
            dists, state = skater(y, state)
            if i == restore_at:
                state = copy.deepcopy(state)
            if i >= burn:
                out.append([probe_dist(d, probe, q_lo, q_hi) for d in dists])
    return out


def _mods():
    """Lazy module handles: a scenario whose module is not yet ported reports
    MISSING instead of breaking every other scenario."""
    import importlib
    class L:
        def __getattr__(self, name):
            mod, attr = {
                "T": ("skaters.torch", "from_reference"), "conj": ("skaters.torch.conjugate", "conjugate"),
                "leaf": ("skaters.torch.leaf", "leaf"), "scale_mixture_leaf": ("skaters.torch.leaf", "scale_mixture_leaf"),
                "crps_leaf": ("skaters.torch.leaf", "crps_leaf"), "garch_leaf": ("skaters.torch.leaf", "garch_leaf"),
                "ema": ("skaters.torch.ema", "ema"),
                "precision_weighted_ensemble": ("skaters.torch.ensemble", "precision_weighted_ensemble"),
                "bayesian_ensemble": ("skaters.torch.bayesian", "bayesian_ensemble"),
                "multiscale": ("skaters.torch.multiscale", "multiscale"), "gpdtails": ("skaters.torch.tails", "gpdtails"),
                "adaptive_search": ("skaters.torch.search", "search"), "S": ("skaters.torch", "spec"),
                "laplace": ("skaters.torch.api", "laplace"), "sticky": ("skaters.torch.sticky", "sticky"),
            }[name]
            m = importlib.import_module(mod)
            return getattr(m, attr) if attr != "spec" else importlib.import_module("skaters.torch.spec")
    return L()


def build_scenarios():
    """{name: (k, builder)} for every entry of gen_vectors.build_scenarios; a
    builder constructs the torch skater on demand."""
    M = _mods()
    s = {}
    for k in (1, 3):
        suf = "" if k == 1 else f"_k{k}"
        def tx(name, kk=k, **kw):
            return lambda: M.conj(M.leaf(k=kk), M.T(name, **kw), k=kk)
        s[f"leaf{suf}"] = (k, lambda kk=k: M.leaf(k=kk))
        s[f"diff{suf}"] = (k, tx("difference"))
        s[f"ema_t{suf}"] = (k, tx("ema_transform", alpha=0.1))
        s[f"standardize{suf}"] = (k, tx("standardize"))
        s[f"theta{suf}"] = (k, tx("theta", alpha=0.1))
        s[f"drift{suf}"] = (k, tx("drift", alpha=0.05, shrinkage=0.01))
        s[f"holt{suf}"] = (k, tx("holt_linear", alpha=0.1, beta=0.05))
        s[f"garch{suf}"] = (k, tx("garch"))
        s[f"seasonal{suf}"] = (k, tx("seasonal_difference", period=7))
        s[f"power{suf}"] = (k, tx("power_transform", p=0.5))
        s[f"ar1{suf}"] = (k, tx("ar", order=1))
        s[f"ar2{suf}"] = (k, tx("ar", order=2, decay=1))
        s[f"frac{suf}"] = (k, tx("fractional_difference", d=0.4, window=30))
        s[f"grouped_ar{suf}"] = (k, tx("grouped_ar", max_lag=8))
        s[f"yeojohnson_log{suf}"] = (k, tx("yeo_johnson", lmbda=0.0))
        s[f"yeojohnson_half{suf}"] = (k, tx("yeo_johnson", lmbda=0.5))
        s[f"ou{suf}"] = (k, tx("ou_transform", kappa=0.1))
        s[f"ou_sqrt{suf}"] = (k, lambda kk=k: M.conj(M.conj(M.leaf(k=kk), M.T("ou_transform", kappa=0.1), k=kk),
                                                     M.T("yeo_johnson", lmbda=0.5), k=kk))
        s[f"ema_skater{suf}"] = (k, lambda kk=k: M.ema(0.05, k=kk))
        s[f"pw_ensemble{suf}"] = (k, lambda kk=k: M.precision_weighted_ensemble([M.ema(0.05, k=kk), M.ema(0.2, k=kk)], k=kk))
        s[f"multiscale{suf}"] = (k, lambda kk=k: M.multiscale(
            lambda k2: M.conj(M.leaf(k=k2), M.T("ema_transform", alpha=0.1), k=k2), kk))
        s[f"bayes_ensemble{suf}"] = (k, lambda kk=k: M.bayesian_ensemble(
            [M.ema(0.05, k=kk), M.conj(M.leaf(k=kk), M.T("difference"), k=kk)],
            k=kk, learning_rate=0.5, complexity_penalty=0.02, depths=[1, 1]))
    s["pol_laplace"] = (1, lambda: M.laplace(k=1))
    s["pol_laplace_k3"] = (3, lambda: M.laplace(k=3))
    s["search_default"] = (1, lambda: M.adaptive_search(k=1, expand_interval=50))
    s["spec_diff_ensemble"] = (1, lambda: M.S.build(M.S.conjugate_spec(
        M.S.ensemble_spec(M.S.ema_spec(0.01, 1), M.S.ema_spec(0.1, 1), k=1), M.S.diff_spec())))
    s["spec_ema"] = (1, lambda: M.S.build(M.S.ema_spec(0.05, 1)))
    s["gpd_tails"] = (1, lambda: M.gpdtails(M.conj(M.leaf(k=1), M.T("ema_transform", alpha=0.1), k=1),
                                            k=1, level=0.9, nexc=50, warmup=100))
    s["scale_mixture_leaf"] = (1, lambda: M.scale_mixture_leaf(k=1))
    s["crps_leaf"] = (1, lambda: M.crps_leaf(k=1))
    s["garch_leaf"] = (1, lambda: M.garch_leaf(k=1))
    s["scalemix_ema"] = (1, lambda: M.conj(M.scale_mixture_leaf(k=1), M.T("ema_transform", alpha=0.1), k=1))
    return s


def build_repeat_scenarios():
    M = _mods()
    return {"sticky_ema": (1, lambda: M.sticky(M.conj(M.leaf(k=1), M.T("ema_transform", alpha=0.1), k=1), k=1))}


def build_gap_scenarios():
    M = _mods()
    return {"pol_laplace": (1, lambda: M.laplace(k=1)), "pol_laplace_k3": (3, lambda: M.laplace(k=3))}


def compare(label, expected, actual, fails, verbose):
    n = 0
    if len(expected) != len(actual):
        print(f"FAIL {label}: {len(expected)} expected steps vs {len(actual)}")
        return 1
    for i, (erow, arow) in enumerate(zip(expected, actual)):
        if len(erow) != len(arow):
            print(f"FAIL {label}: step {i} horizon count {len(erow)} vs {len(arow)}")
            return 1
        for h, (ep, ap) in enumerate(zip(erow, arow)):
            for j, (e, a) in enumerate(zip(ep, ap)):
                if not close(a, e):
                    n += 1
                    if n <= 3:
                        print(f"  {label} step {i} h {h} probe {j}: torch {float(a)!r} expected {e!r}")
    if n:
        print(f"FAIL {label}: {n} mismatches")
    elif verbose:
        print(f"ok   {label}")
    return n


def main(argv):
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    verbose = "-q" not in argv
    vectors = json.load(open(os.path.join(HERE, "vectors.json")))
    series, burn, probe = vectors["series"], vectors["burn"], vectors["probe"]
    q_lo, q_hi = vectors["q_lo"], vectors["q_hi"]
    failures = checked = missing = 0

    scenarios = build_scenarios()
    for name, expected in vectors["scenarios"].items():
        if only and name not in only:
            continue
        if name not in scenarios:
            print(f"MISSING {name} (no builder)"); missing += 1; continue
        k, build = scenarios[name]
        try:
            sk = build()
        except Exception as e:  # noqa: BLE001
            print(f"MISSING {name}: {type(e).__name__}: {str(e)[:90]}"); missing += 1; continue
        for leg, restore in (("", -1), ("+restore", burn - 1)):
            out = run_scenario(sk, series, burn, probe, q_lo, q_hi, restore)
            failures += compare(name + leg, expected["out"], out, failures, verbose)
            checked += sum(len(r) * 7 for r in out)

    if vectors.get("repeat_scenarios") and not only:
        rep = vectors["repeat_series"]
        for name, (k, build) in build_repeat_scenarios().items():
            try:
                sk = build()
            except Exception as e:  # noqa: BLE001
                print(f"MISSING repeat:{name}: {type(e).__name__}: {str(e)[:90]}"); missing += 1; continue
            out = run_scenario(sk, rep, burn, probe, q_lo, q_hi)
            failures += compare("repeat:" + name, vectors["repeat_scenarios"][name]["out"], out, failures, verbose)
            checked += sum(len(r) * 7 for r in out)
    if vectors.get("gap_scenarios") and not only:
        gaps = vectors["gap_series"]
        for name, (k, build) in build_gap_scenarios().items():
            try:
                sk = build()
            except Exception as e:  # noqa: BLE001
                print(f"MISSING gap:{name}: {type(e).__name__}: {str(e)[:90]}"); missing += 1; continue
            out = run_scenario(sk, gaps, burn, probe, q_lo, q_hi)
            failures += compare("gap:" + name, vectors["gap_scenarios"][name]["out"], out, failures, verbose)
            checked += sum(len(r) * 7 for r in out)
    if vectors.get("periodicity") and not only:
        from skaters.torch.periodicity import period_detector
        pd = period_detector(); st = None; out = []
        with torch.no_grad():
            for i, y in enumerate(series):
                scores, st = pd(y, st)
                if i >= burn:
                    out.append([[int(L), float(acf)] for L, acf in scores])
        n = 0
        for i, (erow, arow) in enumerate(zip(vectors["periodicity"], out)):
            if len(erow) != len(arow) or any(int(e[0]) != a[0] or not close(a[1], e[1]) for e, a in zip(erow, arow)):
                n += 1
        if n:
            print(f"FAIL periodicity: {n} steps differ"); failures += n
        elif verbose:
            print("ok   periodicity")
    if vectors.get("structure") and not only:
        from skaters.torch.pool import pool_spec
        for kk, exp in vectors["structure"].items():
            spec = pool_spec(int(kk))
            if len(spec) != exp["n_candidates"] or [d for _, d in spec] != exp["depths"]:
                print(f"FAIL structure k={kk}: {len(spec)} candidates vs {exp['n_candidates']}"); failures += 1
            elif verbose:
                print(f"ok   structure k={kk}")

    print(f"\n{checked} values checked across {len(vectors['scenarios'])} scenarios"
          + (f"; {missing} MISSING" if missing else ""))
    print("PARITY OK" if failures == 0 and missing == 0 else f"PARITY FAILED ({failures} mismatches, {missing} missing)")
    return 0 if failures == 0 and missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
