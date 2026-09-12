"""Compose the homogenization cell model (benchmarks/homogenization/cell_model.py)
onto a real base forecaster, the same way laplace_on_scale.py composes the
Kalman-grid and garch-grid designs. cell_model.py's phase-1 synthetic gate
already passed (see benchmarks/homogenization/RESULTS.md, verdict "go") but
it was explicitly never tested on real data -- that integration was staged
as a deliberately later phase. This is that phase.

cell_model.cell_step(z, state, candidates) already returns a pooled, exact
Gaussian scale-mixture correction {"weights": [...], "scales": [...]} for
the next z -- a genuine density in z-space, same shape of object as
laplace_on_scale.ZSpaceCorrectedDist wraps, just represented as a plain
dict/logg() pair instead of a Dist-like object with methods. ScaleMixtureDist
below adapts it to the same cdf/logpdf/quantile interface.

Usage: PYTHONPATH=src python benchmarks/residual-transform/cell_model_on_laplace.py
"""
from __future__ import annotations
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_HOMOG = os.path.join(os.path.dirname(_HERE), "homogenization")
sys.path.insert(0, _HERE)
sys.path.insert(0, _HOMOG)
import laplace_on_scale as los  # noqa: E402
import cell_model as cm         # noqa: E402
from skaters import laplace    # noqa: E402


class ScaleMixtureDist:
    """A Gaussian scale mixture in z-space, {"weights": [...], "scales":
    [...]}, given the cdf/logpdf/quantile interface cell_model_on_laplace's
    ZSpaceCorrectedDist-style composition needs."""

    __slots__ = ("correction",)

    def __init__(self, correction: dict):
        self.correction = correction

    def logpdf(self, z: float) -> float:
        return cm.logg(z, self.correction)

    def cdf(self, z: float) -> float:
        total = 0.0
        for w, s in zip(self.correction["weights"], self.correction["scales"]):
            total += w * los._STD_NORMAL.cdf(z / s)
        return los._clamp01(total)

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        lo, hi = -40.0, 40.0
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            if self.cdf(mid) < p:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)


def laplace_scale_cell_model(base_factory=None, candidates=None):
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    candidates = candidates if candidates is not None else cm.make_candidates()

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "cell_state": None, "raw": None, "correction": None}
        s = state
        if s["raw"] is not None:
            u = los._clamp01(s["raw"].cdf(y))
            z = los._phi_inv(u)
            s["correction"], s["cell_state"] = cm.cell_step(z, s["cell_state"], candidates)

        base_dists, s["base_state"] = base(y, s["base_state"])
        f_t = base_dists[0]
        s["raw"] = f_t

        corrected = f_t if s["correction"] is None else los.ZSpaceCorrectedDist(
            f_t, ScaleMixtureDist(s["correction"]))
        return [corrected], s

    return _skater


def _smoke_test():
    print("--- synthetic sanity check ---")
    for name, gen in (("iid_gaussian_null", los.gen_iid_gaussian), ("periodic_vol_period24", los.gen_periodic_vol)):
        ys = gen(3000, seed=1)
        f = laplace_scale_cell_model()
        state = None
        z_corr = []
        for t, y in enumerate(ys):
            dists, state = f(y, state)
            if t >= 300 and t + 1 < len(ys):
                u = los._clamp01(dists[0].cdf(ys[t + 1]))
                z_corr.append(los._phi_inv(u))
        m = los._moments(z_corr)
        print(f"  {name}: var={m['var']:.4f} kurt={m['kurtosis']:.4f}")


if __name__ == "__main__":
    _smoke_test()
