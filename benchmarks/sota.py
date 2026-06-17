"""Gated SOTA opponents — used only if the libraries are installed.

These are the real conformal-for-time-series methods to beat, judged by
held-out log-likelihood. Each is exposed as a skater-convention forecaster
(y, state) -> ([Dist], state) so the harness scores it identically to ours.

Nothing here is imported by the package; importing this module never fails
(the heavy imports happen lazily inside the factories).
"""

from __future__ import annotations
import math
from skaters.dist import Dist


def available():
    libs = []
    for m in ("crepes", "sklearn", "statsforecast", "numpy"):
        try:
            __import__(m)
            libs.append(m)
        except Exception:
            pass
    return libs


def _smoothed_dist_from_quantiles(qvals):
    """Turn a set of predictive quantile values into a smooth Dist (KDE over
    the quantiles), with a Silverman bandwidth from the quantiles' robust
    spread (IQR/1.349). This is the 'graft a tail to enter the likelihood
    race' step every conformal method needs — its tails are only as fat as
    this bandwidth, which is the weakness we exploit. We pick a *fair*
    bandwidth here so the foil isn't artificially hobbled."""
    n = len(qvals)
    sq = sorted(qvals)
    iqr = sq[int(0.75 * (n - 1))] - sq[int(0.25 * (n - 1))]
    spread = iqr / 1.349 if iqr > 0 else (sq[-1] - sq[0]) or 1.0
    h = max(0.9 * spread * n ** (-0.2), 1e-9)
    return Dist([(1.0 / n, q, h) for q in qvals])


def crepes_cps(window: int = 400, ar: float = 0.0):
    """crepes Conformal Predictive System on a rolling residual window.

    Mean model: AR(1) on the (already-differenced) series with coefficient
    `ar` (0 = naive). Residuals feed crepes' CPS, which yields a predictive
    CDF; we read a percentile grid off it and smooth to a density for logpdf.

    NOTE: written against the crepes ConformalPredictiveSystem API but not
    executable in this offline sandbox — verify the predict() signature
    against your installed crepes version.
    """
    import warnings
    import numpy as np
    from crepes import ConformalPredictiveSystem

    grid = list(range(5, 96, 2))  # avoid extreme percentiles that need huge calibration

    def f(y, state):
        if state is None:
            state = {"buf": [], "prev": None}
        # AR(1) mean for the change series; residual = y - ar*prev.
        mu = ar * state["prev"] if state["prev"] is not None else 0.0
        resid = y - mu
        buf = state["buf"]

        if len(buf) >= 60:
            cps = ConformalPredictiveSystem()
            cps.fit(np.asarray(buf, dtype=float))
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    qs = cps.predict(y_hat=np.zeros(1), higher_percentiles=grid)
                qvals = [float(v) for v in np.ravel(qs) if math.isfinite(float(v))]
            except Exception:
                qvals = list(buf)
            if not qvals:
                qvals = list(buf)
            mu_next = ar * y if ar else 0.0
            out = [_smoothed_dist_from_quantiles([q + mu_next for q in qvals])]
        else:
            sd = (math.sqrt(sum(v * v for v in buf) / len(buf)) if buf else 1.0) or 1.0
            out = [Dist.gaussian(0.0, sd)]

        buf.append(resid)
        if len(buf) > window:
            buf.pop(0)
        state["prev"] = y
        return out, state
    return f


def opponents():
    """Return {name: factory} for whichever SOTA libraries are installed."""
    out = {}
    try:
        import crepes  # noqa: F401
        out["crepes-CPS"] = lambda: crepes_cps(ar=0.0)
        out["crepes-CPS-AR"] = lambda: crepes_cps(ar=0.3)
    except Exception:
        pass
    return out
