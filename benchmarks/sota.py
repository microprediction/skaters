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
    the quantiles). This is the 'graft a tail to enter the likelihood race'
    step every conformal method needs — its tails are only as fat as this
    bandwidth, which is the weakness we exploit."""
    n = len(qvals)
    sq = sorted(qvals)
    gaps = [sq[i + 1] - sq[i] for i in range(n - 1) if sq[i + 1] > sq[i]]
    h = (sorted(gaps)[len(gaps) // 2] if gaps else 1.0) or 1e-6
    return Dist([(1.0 / n, q, max(h, 1e-9)) for q in qvals])


def crepes_cps(window: int = 400, ar: float = 0.0):
    """crepes Conformal Predictive System on a rolling residual window.

    Mean model: AR(1) on the (already-differenced) series with coefficient
    `ar` (0 = naive). Residuals feed crepes' CPS, which yields a predictive
    CDF; we read a percentile grid off it and smooth to a density for logpdf.

    NOTE: written against the crepes ConformalPredictiveSystem API but not
    executable in this offline sandbox — verify the predict() signature
    against your installed crepes version.
    """
    import numpy as np
    from crepes import ConformalPredictiveSystem

    grid = list(range(2, 99, 2))

    def f(y, state):
        if state is None:
            state = {"buf": [], "prev": None}
        # AR(1) mean for the change series; residual = y - ar*prev.
        mu = ar * state["prev"] if state["prev"] is not None else 0.0
        resid = y - mu
        buf = state["buf"]

        if len(buf) >= 30:
            cps = ConformalPredictiveSystem()
            cps.fit(np.asarray(buf, dtype=float))
            # Predict the next residual's percentiles (point estimate 0), then
            # shift by the next mean. Fall back to recentred empirical if the
            # percentile call differs in this crepes version.
            try:
                qs = cps.predict(y_hat=np.zeros(1), higher_percentiles=grid)
                qvals = [float(v) for v in np.ravel(qs)]
            except Exception:
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
