"""Benchmark harness — NOT part of the deployed package.

Compares skaters policies (and conformal recalibration) against classical
baselines and split-conformal prediction, on point accuracy (MASE) *and*
distributional quality (CRPS, interval coverage, log-likelihood).

It is deliberately self-contained and offline: the baselines and the
conformal comparison are implemented here in pure Python, so the harness
runs with only `skaters` installed and never adds a package dependency.
External packages (statsforecast, statsmodels, river, ...) are optional and
loaded behind try/except — used only if already installed.

Run:  python benchmarks/bench.py
"""

from __future__ import annotations
import math
import random

from skaters import laplace, kahneman, dantzig, conformal, ema, Dist


# ---------------------------------------------------------------------------
# Reference baselines (pure Python), skater convention: (y, state) -> ([Dist], state)
# Each emits a Gaussian predictive from a rolling residual scale, except the
# conformal baseline which uses split-conformal quantiles.
# ---------------------------------------------------------------------------

def _gaussian_baseline(point_fn):
    """Build a baseline from a point-forecaster, with a rolling residual std."""
    def f(y, state):
        if state is None:
            state = {"pt": None, "last_pred": None, "n": 0, "m2": 0.0, "mean": 0.0}
        if state["last_pred"] is not None:           # update residual variance (Welford)
            e = y - state["last_pred"]
            state["n"] += 1
            d = e - state["mean"]; state["mean"] += d / state["n"]
            state["m2"] += d * (e - state["mean"])
        pred, state["pt"] = point_fn(y, state["pt"])
        state["last_pred"] = pred
        var = state["m2"] / (state["n"] - 1) if state["n"] >= 2 else 1.0
        return [Dist.gaussian(pred, math.sqrt(max(var, 1e-12)))], state
    return f


def _naive_pt(y, st):
    return y, y                                       # predict last value


def _drift_pt(y, st):
    if st is None:
        return y, {"last": y, "mu": 0.0, "n": 0}
    n = st["n"] + 1
    mu = st["mu"] + ((y - st["last"]) - st["mu"]) / n
    return y + mu, {"last": y, "mu": mu, "n": n}


def _ewma_pt(alpha):
    def pt(y, st):
        level = y if st is None else st + alpha * (y - st)
        return level, level
    return pt


def conformal_naive(window=250):
    """Split-conformal prediction on a naive forecaster (no parametric shape).

    The predictive distribution is the empirical distribution of recent
    naive residuals, recentred on the last value. This is the 'plain'
    conformal baseline to compare the package's conformal() against.
    """
    return conformal(_gaussian_baseline(_naive_pt), k=1, window=window)


FORECASTERS = {
    "naive":            lambda: _gaussian_baseline(_naive_pt),
    "drift":            lambda: _gaussian_baseline(_drift_pt),
    "ewma(.1)":         lambda: _gaussian_baseline(_ewma_pt(0.1)),
    "conformal-naive":  lambda: conformal(_gaussian_baseline(_naive_pt), k=1),
    "laplace":          lambda: laplace(1),
    "kahneman":         lambda: kahneman(1),
    "dantzig":          lambda: dantzig(1),
    "conformal-laplace": lambda: conformal(laplace(1), k=1),
}


# ---------------------------------------------------------------------------
# Synthetic regimes
# ---------------------------------------------------------------------------

def _t(nu, r):
    z = r.gauss(0, 1); chi = sum(r.gauss(0, 1) ** 2 for _ in range(nu))
    return z / math.sqrt(chi / nu)


def regimes(n=2000, seed=0):
    r = random.Random(seed)
    out = {"trend": [], "seasonal": [], "rwalk": [], "heavy-t3": [], "hetero": []}
    lvl = 0.0
    for t in range(n):
        out["trend"].append(0.03 * t + 2 * r.gauss(0, 1))
        out["seasonal"].append(5 * math.sin(2 * math.pi * t / 12) + r.gauss(0, 1))
        lvl += r.gauss(0, 1); out["rwalk"].append(lvl)
        out["heavy-t3"].append(_t(3, r))
        sig = math.exp(math.log(.3) + (math.log(3) - math.log(.3)) * (.5 + .5 * math.sin(2 * math.pi * t / 250)))
        out["hetero"].append(r.gauss(0, sig))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score(make, series, burn=300):
    f = make(); state = None; pending = None
    ae = 0.0; crps = 0.0; lp = 0.0; c90 = c95 = n = 0
    scale_num = 0.0; scale_den = 0; prev = None     # MASE scale = mean |Δy|
    for i, y in enumerate(series):
        if prev is not None:
            scale_num += abs(y - prev); scale_den += 1
        prev = y
        if pending is not None and i > burn:
            d = pending[0]
            ae += abs(d.mean - y)
            crps += d.crps(y)
            v = d.logpdf(y); lp += v if math.isfinite(v) else -20.0
            if d.quantile(0.05) <= y <= d.quantile(0.95): c90 += 1
            if d.quantile(0.025) <= y <= d.quantile(0.975): c95 += 1
            n += 1
        dists, state = f(y, state); pending = dists
    scale = scale_num / scale_den if scale_den else 1.0
    return {"MASE": (ae / n) / scale, "CRPS": crps / n, "cov90": c90 / n,
            "cov95": c95 / n, "logpdf": lp / n}


def try_external():
    """Report which optional external packages are available (none required)."""
    avail = []
    for mod in ("statsforecast", "statsmodels", "river", "mapie", "crepes"):
        try:
            __import__(mod); avail.append(mod)
        except Exception:
            pass
    return avail


def main():
    data = regimes()
    ext = try_external()
    print(f"optional external packages available: {ext or 'none (offline baselines only)'}\n")
    for name, series in data.items():
        print(f"=== {name} ===")
        print(f"  {'forecaster':18s}{'MASE':>7}{'CRPS':>8}{'cov90':>8}{'cov95':>8}{'logpdf':>9}")
        rows = [(nm, score(mk, series)) for nm, mk in FORECASTERS.items()]
        best = min(r["CRPS"] for _, r in rows)
        for nm, r in rows:
            star = "  <- best CRPS" if r["CRPS"] == best else ""
            print(f"  {nm:18s}{r['MASE']:>7.3f}{r['CRPS']:>8.3f}"
                  f"{r['cov90']*100:>7.1f}%{r['cov95']*100:>7.1f}%{r['logpdf']:>9.3f}{star}")
        print()


if __name__ == "__main__":
    main()
