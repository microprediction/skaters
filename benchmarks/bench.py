"""Benchmark harness — NOT part of the deployed package.

Judged the way the package judges everything: held-out predictive
log-likelihood (higher is better). It pits the skaters policies against
simple baselines and a self-contained **conformal predictive distribution**
foil. The conformal foil is implemented here, not imported — the package
ships no conformal/coverage machinery.

External SOTA opponents (crepes Conformal Predictive Systems, SPCI, ...) are
loaded behind optional imports and used only if already installed; they need
heavy deps + network, so the harness runs offline without them.

Run:  python benchmarks/bench.py
"""

from __future__ import annotations
import math
import random

from skaters import laplace, kahneman, skater, leaf, scale_mixture_leaf, conjugate, ema_transform, Dist


# --- forecasters: (y, state) -> ([Dist], state) --------------------------

def _gaussian_naive():
    """Last value + rolling-residual Gaussian (a minimal point+interval model)."""
    def f(y, state):
        if state is None:
            state = {"last": None, "n": 0, "mean": 0.0, "m2": 0.0}
        if state["last"] is not None:
            e = y - state["last"]
            state["n"] += 1
            d = e - state["mean"]; state["mean"] += d / state["n"]; state["m2"] += d * (e - state["mean"])
        var = state["m2"] / (state["n"] - 1) if state["n"] >= 2 else 1.0
        out = [Dist.gaussian(y, math.sqrt(max(var, 1e-12)))]
        state["last"] = y
        return out, state
    return f


def conformal_pd_naive(window=300):
    """Conformal predictive distribution on a naive forecaster, scorable by
    logpdf: empirical CDF of recent residuals, smoothed to a density (Gaussian
    KDE). This is the foil — recency-unweighted, thin kernel tails."""
    def f(y, state):
        if state is None:
            state = {"last": None, "buf": []}
        # KDE density predictor for the *next* residual, recentred on y.
        buf = state["buf"]
        n = len(buf)
        if n >= 2:
            mean = sum(buf) / n
            sd = math.sqrt(sum((v - mean) ** 2 for v in buf) / n) or 1.0
            h = 0.9 * sd * n ** (-0.2)
            comps = [(1.0 / n, y + r, h) for r in buf]
            out = [Dist(comps)]
        else:
            out = [Dist.gaussian(y, 1.0)]
        if state["last"] is not None:
            buf.append(y - state["last"])
            if len(buf) > window:
                buf.pop(0)
        state["last"] = y
        return out, state
    return f


FORECASTERS = {
    "naive-gauss": _gaussian_naive,
    "conformal-PD": conformal_pd_naive,                 # the foil
    "scale-mix leaf": lambda: conjugate(scale_mixture_leaf(1), ema_transform(0.1), 1),
    "laplace": lambda: laplace(1),
    "kahneman": lambda: kahneman(1),
    "skater": lambda: skater(1),
}


# --- synthetic regimes ---------------------------------------------------

def _t(nu, r):
    z = r.gauss(0, 1); chi = sum(r.gauss(0, 1) ** 2 for _ in range(nu))
    return z / math.sqrt(chi / nu)


def regimes(n=2500, seed=0):
    r = random.Random(seed)
    out = {"trend": [], "ar+t3": [], "heavy-t3": [], "t3-drift": []}
    ar = 0.0
    for i in range(n):
        out["trend"].append(0.03 * i + 2 * r.gauss(0, 1))
        ar = 0.8 * ar + _t(3, r); out["ar+t3"].append(ar)
        out["heavy-t3"].append(_t(3, r))
        sc = math.exp(math.log(.4) + (math.log(3) - math.log(.4)) * (.5 + .5 * math.sin(2 * math.pi * i / 400)))
        out["t3-drift"].append(_t(3, r) * sc)
    return out


def mean_logpdf(make, series, burn=300):
    f = make(); state = None; pending = None
    tot = 0.0; n = 0
    for i, y in enumerate(series):
        if pending is not None and i > burn:
            v = pending[0].logpdf(y)
            tot += v if math.isfinite(v) else -20.0
            n += 1
        dists, state = f(y, state); pending = dists
    return tot / n


def _table(forecasters, data, label):
    print(f"\n=== {label} === mean held-out log-likelihood (higher is better)\n")
    cols = list(data.keys())
    print(f"  {'forecaster':18s}" + "".join(f"{c[:10]:>11s}" for c in cols))
    for name, mk in forecasters.items():
        cells = "".join(f"{mean_logpdf(mk, data[c]):>11.3f}" for c in cols)
        print(f"  {name:18s}{cells}")


def main():
    forecasters = dict(FORECASTERS)
    try:
        import sota
        sota_ops = sota.opponents()
        forecasters.update(sota_ops)
        print(f"SOTA libraries: {sota.available() or 'none'};  opponents added: {list(sota_ops) or 'none'}")
    except Exception as e:  # noqa: BLE001
        print(f"SOTA opponents unavailable ({e})")

    _table(forecasters, regimes(), "synthetic")

    try:
        import fred
        fred_data = fred.load_fred()
        if fred_data:
            _table(forecasters, fred_data, "FRED (one-step change)")
        else:
            print("\n(no FRED data — set FRED_API_KEY to enable the FRED table)")
    except Exception as e:  # noqa: BLE001
        print(f"\nFRED unavailable ({e})")


if __name__ == "__main__":
    main()
