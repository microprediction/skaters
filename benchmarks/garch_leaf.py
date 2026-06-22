"""Prototype GARCH(1,1)-t terminal leaf (issue #25), scored as a benchmark leaf.

The "conform last" terminal leaf in `scale_mixture_leaf` / `crps_leaf` tracks its
scale with an EWMA of squared residuals: v_t = (1-a) v_{t-1} + a r_t^2. That is
RiskMetrics / **IGARCH** — the omega=0, alpha+beta=1 special case with *no
variance mean-reversion*. It is to a real GARCH leaf what `doob` (committed
martingale) is to `mean_revert`: the random-walk-variance prior. On price/return
series, where volatility clusters but *reverts*, GARCH-t (fitted omega/alpha/beta
+ Student-t) beats `laplace` ~90% (issue #25).

`garch_leaf` is the drop-in generalization for the terminal-leaf slot:

  * conditional variance h_t = omega + alpha r_{t-1}^2 + beta h_{t-1}, with
    (alpha, beta) refit periodically by **variance-targeted** Gaussian QMLE
    (omega = (1 - alpha - beta) * S^2), a coarse grid -- dependency-free, robust;
  * Student-t tails via the same fixed Gaussian scale mixture as the existing leaf
    (a Gaussian scale mixture *is* a Student-t), weights fit online by EM.

EWMA is the alpha+beta=1, omega=0 corner, so this strictly generalizes today's leaf.

    PYTHONPATH=src python benchmarks/garch_leaf.py        # synthetic validation
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist

_SCALE_BASIS = (0.7, 1.0, 1.6, 3.0, 6.0)
# (alpha, beta) candidates for the variance-targeted refit; alpha+beta < 1 always.
_AB_GRID = [(a, b) for a in (0.02, 0.05, 0.08, 0.12, 0.18)
            for b in (0.70, 0.80, 0.88, 0.93, 0.97) if a + b < 0.999]


def _garch_nll(resid, alpha, beta, s2):
    """Gaussian QMLE neg-log-lik of a variance-targeted GARCH(1,1) over `resid`."""
    omega = (1.0 - alpha - beta) * s2
    h = s2
    nll = 0.0
    for r in resid:
        h = omega + alpha * (r * r) + beta * h
        if h <= 1e-300:
            h = 1e-300
        nll += math.log(h) + (r * r) / h
    return 0.5 * nll


def garch_leaf(k: int = 1, gamma: float = 0.02, refit_every: int = 40,
               min_obs: int = 80, window: int = 400, scales: tuple = _SCALE_BASIS):
    """GARCH(1,1) conditional variance + Gaussian-scale-mixture (Student-t) tails.

    Same interface as ``scale_mixture_leaf`` — a drop-in ``leaf_fn`` for
    ``terminal_leaf_ensemble`` (the conform-last stage of ``laplace``).
    """
    C = tuple(scales)
    K = len(C)
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))

    def _leaf(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            w = [1e-6] * K
            w[one_idx] = 1.0
            state = {
                "h": 0.0, "s2": 0.0, "n": 0,
                "omega": 0.0, "alpha": 0.05, "beta": 0.90,
                "buf": deque(maxlen=window), "w": w, "last_r2": 0.0,
            }
        s = state
        s["n"] += 1
        # Running unconditional variance (bootstrap then EWMA-ish), for targeting.
        a0 = 0.02 if 0.02 > 1.0 / s["n"] else 1.0 / s["n"]
        s["s2"] = (1 - a0) * s["s2"] + a0 * y * y
        if s["s2"] <= 0:
            s["s2"] = max(y * y, 1e-12)

        # GARCH(1,1) one-step-ahead conditional variance (uses last residual).
        if s["n"] == 1:
            h = s["s2"]
        else:
            h = s["omega"] + s["alpha"] * s["last_r2"] + s["beta"] * s["h"]
        if h <= 1e-300:
            h = s["s2"]
        s["h"] = h
        s["last_r2"] = y * y
        s["buf"].append(y)

        # Periodic variance-targeted refit of (alpha, beta) by Gaussian QMLE.
        if s["n"] >= min_obs and s["n"] % refit_every == 0 and len(s["buf"]) >= min_obs:
            resid = list(s["buf"])
            s2 = sum(r * r for r in resid) / len(resid)
            if s2 > 0:
                best = min(_AB_GRID, key=lambda ab: _garch_nll(resid, ab[0], ab[1], s2))
                s["alpha"], s["beta"] = best
                s["omega"] = (1.0 - best[0] - best[1]) * s2

        sigma = math.sqrt(h) if (math.isfinite(h) and h > 0) else max(abs(y), 1e-8)

        # Scale-mixture tail weights, fit online by recency-weighted EM on z = r/sigma.
        z = y / sigma
        w = s["w"]
        dens = [w[i] * math.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        total = sum(dens)
        if total > 0:
            g = gamma if gamma > 1.0 / s["n"] else 1.0 / s["n"]
            s["w"] = [(1 - g) * w[i] + g * dens[i] / total for i in range(K)]

        d = Dist([(s["w"][i], 0.0, C[i] * sigma) for i in range(K)])
        return [d] * k, s

    _leaf.__name__ = f"garch_leaf(k={k})"
    return _leaf


# ---------------------------------------------------------------------------
# Synthetic validation: does the GARCH recursion beat the EWMA/IGARCH leaf on
# vol-clustering-WITH-reversion data (where the variance mean-reverts)?
# ---------------------------------------------------------------------------

def _sim_garch_t(seed, n=3000, omega=0.05, alpha=0.08, beta=0.90, nu=6.0):
    """GARCH(1,1)-t returns: clustered, fat-tailed, mean-reverting variance."""
    import random
    rng = random.Random(seed)
    h = omega / max(1e-6, 1 - alpha - beta)
    out = []
    for _ in range(n):
        # Student-t innovation, standardized to unit variance.
        g = rng.gauss(0, 1)
        chi = sum(rng.gauss(0, 1) ** 2 for _ in range(int(nu)))
        t = g / math.sqrt(chi / nu) if chi > 0 else g
        t *= math.sqrt((nu - 2) / nu)
        r = math.sqrt(h) * t
        out.append(r)
        h = omega + alpha * (r * r) + beta * h
    return out


def _score(make_leaf, series, burn=300):
    f = make_leaf()
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


def main():
    from skaters.leaf import scale_mixture_leaf
    import statistics as st
    print("=== synthetic GARCH(1,1)-t returns: garch_leaf vs EWMA scale_mixture_leaf ===")
    print("(delta = garch_leaf - ewma, held-out one-step log-likelihood)")
    for pers, ab in [("clustering + strong reversion", (0.10, 0.80)),
                     ("clustering + mild reversion", (0.08, 0.90)),
                     ("near-IGARCH (little reversion)", (0.05, 0.945))]:
        de, dg = [], []
        for s in range(6):
            ser = _sim_garch_t(11 + 7 * s, alpha=ab[0], beta=ab[1])
            de.append(_score(lambda: scale_mixture_leaf(k=1), ser))
            dg.append(_score(lambda: garch_leaf(k=1), ser))
        delta = st.mean(g - e for g, e in zip(dg, de))
        print(f"  {pers:32s} a+b={sum(ab):.3f}  ewma {st.mean(de):+.3f}  "
              f"garch {st.mean(dg):+.3f}  delta {delta:+.4f}  "
              f"({sum(g > e for g, e in zip(dg, de))}/6)")


if __name__ == "__main__":
    main()
