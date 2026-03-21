"""Invertible online transforms for conjugation.

A Transform is a pair of online functions:

    y', state = forward(y, state)     # transform one observation
    x = inverse_k(x', state)          # map k predictions back to original space

The forward function runs on every observation. The inverse_k function
takes k-step-ahead predictions in the transformed space and maps them
back to the original space using whatever anchor information the
forward pass has accumulated in state.

Transforms compose: you can chain them. And they conjugate with any
skater: transform the series, predict the simpler series, invert.
"""

from __future__ import annotations
import math


# ---------------------------------------------------------------------------
# Differencing:  y'_t = y_t - y_{t-1}
# ---------------------------------------------------------------------------

def difference():
    """First-order differencing transform.

    Forward:   y'_t = y_t - y_{t-1}
    Inverse:   x_j  = y_t + x'_1 + x'_2 + ... + x'_j   for j = 1..k

    The inner model predicts *changes*; the inverse cumsums them back
    anchored at the last observation.
    """

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"last": y}
        dy = y - state["last"]
        return dy, {"last": y}

    def inverse_k(x_prime: list[float], state: dict) -> list[float]:
        anchor = state["last"]
        result = []
        cumsum = 0.0
        for dx in x_prime:
            cumsum += dx
            result.append(anchor + cumsum)
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

    Args:
        d: differencing order, typically in (0, 0.5). Larger d removes
           more memory. d=1 is ordinary differencing.
        window: truncation length for the filter. Longer = more accurate
                but more memory.

    The transform is stable and invertible for any d. For d in (0, 0.5),
    the transformed series is stationary while preserving long memory.
    """
    w_fwd = _frac_diff_weights(d, window)
    w_inv = _frac_int_weights(d, window)

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {"buffer": []}
        buf = state["buffer"]
        buf.append(y)
        if len(buf) > window:
            buf.pop(0)

        # Apply (1-B)^d: y'_t = sum w_j * y_{t-j}
        n = len(buf)
        y_prime = sum(w_fwd[j] * buf[n - 1 - j] for j in range(n))
        return y_prime, state

    def inverse_k(x_prime: list[float], state: dict) -> list[float]:
        """Apply (1-B)^{-d} to map predictions back to original space.

        We extend the buffer with each predicted transformed value,
        then apply the inverse filter to recover the original-space
        prediction.
        """
        buf = list(state["buffer"])  # copy so we don't mutate
        result = []
        for x_p in x_prime:
            # Append the transformed prediction
            buf.append(0.0)  # placeholder
            n = len(buf)
            # Solve for y_t given y'_t = sum w_fwd[j] * y_{t-j}:
            #   y_t = y'_t - sum_{j=1}^{W-1} w_fwd[j] * y_{t-j}
            #   (since w_fwd[0] = 1)
            y_recovered = x_p
            for j in range(1, min(n, window)):
                y_recovered -= w_fwd[j] * buf[n - 1 - j]
            buf[-1] = y_recovered
            result.append(y_recovered)
            # Trim buffer
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
    Inverse:   x_j  = x'_j * sigma_t + mu_t

    Uses exponential moving averages for mean and variance, so it
    adapts online. The inverse uses the *current* mu and sigma
    (at prediction time), which is the best estimate for the near future.

    Args:
        alpha: EMA smoothing for mean and variance.
        eps: floor for sigma to avoid division by zero.
    """

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"mu": y, "var": 0.0}
        mu = state["mu"]
        var = state["var"]
        # Update mean and variance
        diff = y - mu
        mu = mu + alpha * diff
        var = (1 - alpha) * (var + alpha * diff * diff)
        sigma = math.sqrt(var) if var > eps * eps else eps
        y_prime = (y - mu) / sigma
        return y_prime, {"mu": mu, "var": var}

    def inverse_k(x_prime: list[float], state: dict) -> list[float]:
        mu = state["mu"]
        var = state["var"]
        sigma = math.sqrt(var) if var > 1e-16 else 1e-8
        return [x_p * sigma + mu for x_p in x_prime]

    return forward, inverse_k
