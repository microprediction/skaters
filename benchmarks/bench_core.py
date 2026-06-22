"""Shared benchmark core — ONE scorer for every study.

Every method, ours or a baseline, is turned into the same predictive object and
scored on the same held-out points by the same code (the one rule of a fair
distributional benchmark). Two scoring paths, both here:

  * roll_dist_scores(factory, changes)  — for anything that emits a `Dist` stream
    online (our policies; and baselines whose predictive we rebuild as a Gaussian
    scale-mixture Dist via gauss_dist / student_t_dist / conformal_dist).
  * crepes_pinball(changes, window)     — for a conformal predictive *system* that
    emits only a CDF: CRPS via the pinball decomposition, no log-likelihood (a CDF
    cannot be density-scored — that asymmetry is the point, not a bug).

Both forecast the one-step *change* and score the last steps after a burn-in.
`score_dist` is the single (logpdf, crps) evaluator everyone funnels through.
"""
from __future__ import annotations
import math
import numpy as np
from skaters.dist import Dist

BURN = 300                                   # warm-up steps not scored
GRID = list(range(2, 99, 1))                 # crepes quantile grid (percentiles)
TAUS = [p / 100.0 for p in GRID]
Z90 = 1.6448536269514722                     # 90% two-sided z


# ---- the single scorer ------------------------------------------------------

def score_dist(d, y):
    """(logpdf, crps) of a Dist at realized y; -inf logpdf floored to -20."""
    lp = d.logpdf(y)
    return (lp if math.isfinite(lp) else -20.0), d.crps(y)


def roll_dist_scores(factory, changes, start=BURN):
    """Mean (logpdf, crps, n) of an online Dist-emitting forecaster, scoring every
    step with index >= `start` (the warm-up before `start` is fed but not scored).
    `factory()` returns a skater f(y, state) -> (dists, state)."""
    f = factory(); state = None; pend = None
    lp = cr = 0.0; n = 0
    for i, y in enumerate(changes):
        if pend is not None and i >= start:
            a, b = score_dist(pend[0], y); lp += a; cr += b; n += 1
        pend, state = f(y, state)
    return (lp / n, cr / n, n) if n else (float("nan"), float("nan"), 0)


def crepes_pinball(changes, window=250, start=BURN, mean=0.0):
    """Mean CRPS of a crepes ConformalPredictiveSystem via the pinball
    decomposition of its own predictive CDF — no density conversion, so no logpdf.
    `mean` is the (constant) point forecast the CDF is centered on; 0.0 is the
    naive zero-change mean. Returns (crps, n)."""
    from crepes import ConformalPredictiveSystem
    import warnings
    buf = []; tot = 0.0; n = 0; pend = None
    for i, y in enumerate(changes):
        if pend is not None and i >= start:
            s = sum((y - q) * (tau - (1.0 if y < q else 0.0)) for tau, q in pend)
            tot += 2.0 * s / len(pend); n += 1
        buf.append(y)
        if len(buf) > window:
            buf.pop(0)
        if len(buf) >= 60:
            cps = ConformalPredictiveSystem()
            cps.fit(np.asarray(buf, dtype=float))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                qs = np.ravel(cps.predict(y_hat=np.full(1, mean), higher_percentiles=GRID))
            pend = [(t, float(qs[j])) for j, t in enumerate(TAUS) if math.isfinite(float(qs[j]))]
            if not pend:
                pend = [(0.5, mean)]
        else:
            pend = [(0.5, mean)]
    return (tot / n, n) if n else (float("nan"), 0)


# ---- Dist builders: turn a baseline's predictive into one scorable object ----

def gauss_dist(mu, lo, hi):
    """Gaussian Dist from a mean and a 90% interval (band -> sd)."""
    sd = max((hi - lo) / (2.0 * Z90), 1e-9)
    return Dist.gaussian(mu, sd)


def conformal_dist(point, resid_window, scale=1.0, nq=41):
    """Split-conformal predictive: point + a quantile grid of recent residuals,
    KDE-smoothed (Silverman bandwidth) so it CAN be logpdf-scored. Capped at nq
    quantiles to keep mixture CRPS (O(K^2)) cheap. This is conformal with a fitted
    mean (`point`), as opposed to the bare zero-mean CDF in crepes_pinball."""
    r = np.asarray(resid_window)
    qs = np.quantile(r, np.linspace(0.02, 0.98, nq))
    iqr = np.quantile(r, 0.75) - np.quantile(r, 0.25)
    spread = (iqr / 1.349) if iqr > 0 else (r.max() - r.min()) or 1.0
    h = max(0.9 * spread * scale * len(r) ** (-0.2), 1e-9)
    return Dist([(1.0 / nq, point + scale * q, h) for q in qs])


def student_t_dist(mu, var, nu, K=24):
    """Location-scale Student-t as a Gaussian scale mixture Dist (so it scores
    through the same logpdf/crps). Matches the analytic t logpdf to ~1e-3 at K=24."""
    from scipy.stats import chi2
    nu = max(float(nu), 2.1)
    v = chi2.ppf((np.arange(K) + 0.5) / K, df=nu)
    s2 = var * (nu - 2.0)
    return Dist([(1.0 / K, mu, math.sqrt(max(s2 / vi, 1e-18))) for vi in v])
