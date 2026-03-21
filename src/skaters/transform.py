"""Invertible online transforms for conjugation.

A Transform is a pair of online functions:

    y', state = forward(y, state)           # transform one observation
    dists = inverse_k(dists', state)        # map k distributional predictions back

The forward function runs on every observation (scalar in, scalar out).
The inverse_k function takes k Dist objects in the transformed space
and maps them back to the original space.

For linear transforms (diff, standardize, ema), the inverse is exact:
just shift/scale/affine the Dist components. For multi-step predictions,
the cumulative uncertainty is propagated correctly.
"""

from __future__ import annotations
import math
from skaters.dist import Dist


# ---------------------------------------------------------------------------
# Differencing:  y'_t = y_t - y_{t-1}
# ---------------------------------------------------------------------------

def difference():
    """First-order differencing transform.

    Forward:   y'_t = y_t - y_{t-1}
    Inverse:   Shift and accumulate variance across horizons.

    At horizon h, the prediction is:
        y_{t+h} = y_t + Δ_{t+1} + ... + Δ_{t+h}
    where each Δ is a Dist. The mean cumsums, and the variance
    accumulates (assuming independence across horizons).
    """

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"last": y}
        dy = y - state["last"]
        return dy, {"last": y}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        anchor = state["last"]
        result = []
        cumsum_mean = 0.0
        cumsum_var = 0.0
        for d in dists:
            cumsum_mean += d.mean
            cumsum_var += d.var
            std = math.sqrt(cumsum_var) if cumsum_var > 0 else max(d.std, 1e-12)
            result.append(Dist.gaussian(anchor + cumsum_mean, std))
        return result

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Fractional differencing:  (1 - B)^d  with a truncated filter
# ---------------------------------------------------------------------------

def _frac_diff_weights(d: float, window: int) -> list[float]:
    """Compute weights for the truncated (1-B)^d operator.

    w[0] = 1, w[k] = -w[k-1] * (d - k + 1) / k
    """
    w = [1.0]
    for i in range(1, window):
        w.append(-w[-1] * (d - i + 1) / i)
    return w


def _frac_int_weights(d: float, window: int) -> list[float]:
    """Weights for (1-B)^{-d}, the inverse operator."""
    return _frac_diff_weights(-d, window)


def fractional_difference(d: float = 0.4, window: int = 50):
    """Fractional differencing transform of order d.

    Forward:   y'_t = sum_{j=0}^{W-1} w_j * y_{t-j}   where w = (1-B)^d weights
    Inverse:   applies (1-B)^{-d} to the k predictions, anchored at the
               recent history.

    The inverse propagates Dist objects: the mean is recovered exactly,
    and the variance is propagated assuming the inverse is locally linear
    (which it is — it's a weighted sum with known past values).
    """
    w_fwd = _frac_diff_weights(d, window)

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {"buffer": []}
        buf = state["buffer"]
        buf.append(y)
        if len(buf) > window:
            buf.pop(0)

        n = len(buf)
        y_prime = sum(w_fwd[j] * buf[n - 1 - j] for j in range(n))
        return y_prime, state

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        """Apply (1-B)^{-d} to map Dist predictions back to original space.

        For each horizon, the recovered value is:
            y_t = y'_t - sum_{j=1}^{W-1} w_fwd[j] * y_{t-j}
        where y_{t-j} are known (from buffer) for j >= h, and are the
        recovered means for j < h (previous horizons).

        The shift is deterministic (known past), so it just shifts the Dist.
        The variance passes through unchanged (linear operation with unit
        coefficient on y'_t).
        """
        buf = list(state["buffer"])
        result = []
        for d_in in dists:
            buf.append(0.0)  # placeholder for recovered mean
            n = len(buf)
            # The deterministic shift from known/recovered past values
            shift = 0.0
            for j in range(1, min(n, window)):
                shift -= w_fwd[j] * buf[n - 1 - j]
            # Recovered mean: x_prime_mean + shift (since w_fwd[0] = 1)
            recovered_mean = d_in.mean + shift
            buf[-1] = recovered_mean
            # Variance passes through (linear op with unit coeff on x')
            result.append(Dist.gaussian(recovered_mean, d_in.std))
            if len(buf) > window:
                buf.pop(0)
        return result

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Running standardization: predict in z-score space
# ---------------------------------------------------------------------------

def standardize(alpha: float = 0.05, eps: float = 1e-8):
    """Running standardization transform.

    Forward:   y'_t = (y_t - mu_t) / sigma_t
    Inverse:   Apply affine x -> sigma * x + mu to each Dist.
    """

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"mu": y, "var": 0.0}
        mu = state["mu"]
        var = state["var"]
        diff = y - mu
        mu = mu + alpha * diff
        var = (1 - alpha) * (var + alpha * diff * diff)
        sigma = math.sqrt(var) if var > eps * eps else eps
        y_prime = (y - mu) / sigma
        return y_prime, {"mu": mu, "var": var}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        mu = state["mu"]
        var = state["var"]
        sigma = math.sqrt(var) if var > 1e-16 else 1e-8
        return [d.affine(sigma, mu) for d in dists]

    return forward, inverse_k


# ---------------------------------------------------------------------------
# EMA as a transform: subtract the running level
# ---------------------------------------------------------------------------

def ema_transform(alpha: float = 0.05):
    """Exponential moving average as a bijective transform.

    Forward:   y'_t = y_t - level_t   (residual from EMA)
    Inverse:   Shift each Dist by the current level.

    This reframes EMA as a change of reference frame: the inner model
    predicts centered residuals, and the inverse adds back the level.
    """
    assert 0 < alpha < 1

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"level": y}
        level = state["level"] + alpha * (y - state["level"])
        residual = y - level
        return residual, {"level": level}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        level = state["level"]
        return [d.shift(level) for d in dists]

    return forward, inverse_k
