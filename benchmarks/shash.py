"""Sinh-arcsinh (SHASH) coordinate transform (benchmark-side prototype, #320).

Yeo-Johnson reshapes one-sidedly with one parameter. Sinh-arcsinh has two:
delta sets tail weight (delta < 1 compresses heavy tails toward Gaussian,
delta > 1 expands light ones) and epsilon sets skew. It is defined on all
reals, so it needs a scale: the series is first standardized causally by an
exponentially weighted mean and standard deviation (updated after the value
is transformed, so z_t uses only y_<t), then

    forward:  z = (y - m) / s ;   y' = sinh(delta * asinh(z) - epsilon)
    inverse:  z = sinh((asinh(y') + epsilon) / delta) ;   y = m + s z

Each mixture component of the downstream predictive is mapped exactly at its
mean and by the delta method on its standard deviation, as Yeo-Johnson's
default inverse does. (epsilon, delta) = (0, 1) is the identity after
standardization. State is plain floats (json and deepcopy safe).

    from shash import shash
    conjugate(leaf(k=1), shash(epsilon=0.0, delta=0.7), k=1)
"""
from __future__ import annotations

import math

from skaters.dist import Dist


def shash(epsilon: float = 0.0, delta: float = 1.0, alpha: float = 0.02, warmup: int = 20):
    assert delta > 0
    e, d = float(epsilon), float(delta)

    def _f(z):
        return math.sinh(d * math.asinh(z) - e)

    def _finv(zp):
        return math.sinh((math.asinh(zp) + e) / d)

    def _dfinv(zp):
        # d finv / d z'  =  cosh((asinh z' + e)/d) / (d * sqrt(1 + z'^2))
        return math.cosh((math.asinh(zp) + e) / d) / (d * math.sqrt(1.0 + zp * zp))

    def forward(y: float, state: dict | None):
        if state is None:
            state = {"n": 0, "m": 0.0, "v": 0.0}
        m, v, n = state["m"], state["v"], state["n"]
        s = math.sqrt(v) if v > 0 else 0.0
        if n >= warmup and s > 0 and math.isfinite(y):
            z = (y - m) / s
            yp = _f(max(-1e6, min(1e6, z)))
        else:
            yp = 0.0 if not math.isfinite(y) else (y - m)
        if math.isfinite(y):
            if n == 0:
                state["m"], state["v"] = y, 0.0
            else:
                diff = y - m
                state["m"] = m + alpha * diff
                state["v"] = (1.0 - alpha) * (v + alpha * diff * diff)
            state["n"] = n + 1
        return yp, state

    def inverse_k(dists, state):
        m, v, n = state["m"], state["v"], state["n"]
        s = math.sqrt(v) if v > 0 else 0.0
        if n < warmup or s <= 0:   # forward transforms once n >= warmup
            return [dd.shift(m) for dd in dists]
        out = []
        for dd in dists:
            comps = []
            for w, mu, sg in dd.components:
                mu_c = max(-1e6, min(1e6, mu))
                comps.append((w, m + s * _finv(mu_c), max(sg * s * _dfinv(mu_c), 1e-12)))
            out.append(Dist(comps))
        return out

    return forward, inverse_k


# the grid the pool carries: identity-after-standardization is left to the
# existing standardize candidates; these four add tail weight and skew
SHASH_GRID = [(0.0, 0.7), (0.0, 1.4), (0.3, 1.0), (-0.3, 1.0)]
