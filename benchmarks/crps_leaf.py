"""A scale-mixture leaf whose weights are fit by online CRPS-gradient.

Same Dist, same EWMA scale as scale_mixture_leaf — only the *objective* is
swapped: exponentiated-gradient descent on the simplex minimizing the
closed-form mixture CRPS, instead of likelihood EM. The point is that the
skater machinery is a pluggable proper-scoring-rule optimizer; conformal has
no density and so can only ever target coverage/CRPS.
"""

from __future__ import annotations
import math
from skaters.dist import Dist

_S2 = math.sqrt(2.0)
_INV = 1.0 / math.sqrt(2.0 * math.pi)
_A0 = 2.0 * _INV  # A(0, s) = 2 phi(0) s = _A0 * s


def _Phi(x):
    return 0.5 * (1.0 + math.erf(x / _S2))


def _phi(x):
    return math.exp(-0.5 * x * x) * _INV


def _A(m, s):
    """E|N(m, s^2)| = m(2Φ(m/s)-1) + 2s φ(m/s)."""
    if s <= 0:
        return abs(m)
    z = m / s
    return m * (2.0 * _Phi(z) - 1.0) + 2.0 * s * _phi(z)


FINE = tuple(round(0.4 * 1.28 ** i, 4) for i in range(15))  # log-spaced scale basis


def crps_leaf(k=1, eta=0.5, scale_alpha=0.01, scales=FINE):
    C = list(scales)
    K = len(C)
    # pairwise A(0, sqrt(c_a^2 + c_b^2)) for the CRPS gradient's second term
    B = [[math.sqrt(C[a] * C[a] + C[b] * C[b]) * _A0 for b in range(K)] for a in range(K)]
    one = min(range(K), key=lambda i: abs(C[i] - 1.0))

    def f(y, state):
        if state is None:
            w = [1e-6] * K
            w[one] = 1.0
            state = {"v": 0.0, "w": w, "n": 0}
        state["n"] += 1
        a = scale_alpha if scale_alpha > 1.0 / state["n"] else 1.0 / state["n"]
        state["v"] = (1 - a) * state["v"] + a * y * y
        sig = math.sqrt(state["v"]) if state["v"] > 0 else max(abs(y), 1e-8)
        z = y / sig
        w = state["w"]
        # gradient of CRPS(mixture, z) wrt each weight, in standardized space
        g = [_A(-z, C[c]) - sum(w[j] * B[c][j] for j in range(K)) for c in range(K)]
        gm = sum(g) / K
        nw = [w[c] * math.exp(-eta * (g[c] - gm)) for c in range(K)]
        Z = sum(nw)
        state["w"] = [x / Z for x in nw]
        d = Dist([(state["w"][c], 0.0, C[c] * sig) for c in range(K)])
        return [d] * k, state

    f.skaterName = f"crps_leaf(eta={eta})"
    return f
