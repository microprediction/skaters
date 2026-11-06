"""Octave standardize: a reliability-gated two-speed scale (benchmark-side, #320).

From the "Schur-damped Satterthwaite Gabor skater" (Theorem 3.1 of an October
2026 technical note extending the Schur stack) and the "octave_standardize"
suggestion. Two exponentially weighted variances run side by side, a fast one
(rate lf) and a medium one (rate lm). Their log-ratio d = |ln(v_fast / v_mid)|
says whether the scale has just moved; a signal-to-noise statistic built from d
gates how much weight the fast estimate gets:

    SNR   = n_fast * max(0, (d - tau) / tau)^2,   n_fast = (2 - lf) / lf
    gamma = SNR / (SNR + 2.5)
    v     = (1 - gamma) v_mid + gamma v_fast
    s     = sqrt(v * (1 + 1 / (2 n_eff))),        n_eff = (1 - gamma) n_mid + gamma n_fast

    forward:  y' = (y - m) / s      (m, v, gamma from y_<t only)
    inverse:  y  = m + s y'         (affine: exact, mixture shape preserved)

So the scale reacts quickly to a volatility jump or collapse and otherwise
stays on the steadier medium estimate. State is plain floats.
"""
from __future__ import annotations

import math


def octave_standardize(lf: float = 0.22, lm: float = 0.08, tau: float = 0.1366,
                       warmup: int = 20):
    n_fast = (2.0 - lf) / lf
    n_mid = (2.0 - lm) / lm

    def scale(state):
        vf, vm = state["vf"], state["vm"]
        if vf <= 0 or vm <= 0:
            return math.sqrt(max(vm, vf, 0.0)) or 0.0
        dd = abs(math.log(vf / vm))
        snr = n_fast * max(0.0, (dd - tau) / tau) ** 2
        g = snr / (snr + 2.5)
        v = (1.0 - g) * vm + g * vf
        n_eff = (1.0 - g) * n_mid + g * n_fast
        return math.sqrt(v * (1.0 + 1.0 / (2.0 * n_eff)))

    def forward(y: float, state: dict | None):
        if state is None:
            state = {"n": 0, "m": 0.0, "vf": 0.0, "vm": 0.0}
        s = scale(state)
        if state["n"] >= warmup and s > 0 and math.isfinite(y):
            yp = (y - state["m"]) / s
        else:
            yp = 0.0 if not math.isfinite(y) else y - state["m"]
        if math.isfinite(y):
            if state["n"] == 0:
                state["m"] = y
            else:
                diff = y - state["m"]
                state["vf"] = (1 - lf) * (state["vf"] + lf * diff * diff)
                state["vm"] = (1 - lm) * (state["vm"] + lm * diff * diff)
                state["m"] = state["m"] + lm * diff
            state["n"] += 1
        return yp, state

    def inverse_k(dists, state):
        s = scale(state)
        if state["n"] < warmup or s <= 0:   # forward scales once n >= warmup
            return [d.shift(state["m"]) for d in dists]
        return [d.affine(s, state["m"]) for d in dists]

    return forward, inverse_k
