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


# ---------------------------------------------------------------------------
# GARCH(1,1) volatility scaling
# ---------------------------------------------------------------------------

def garch(omega: float = 0.01, alpha: float = 0.1, beta: float = 0.85, eps: float = 1e-8):
    """GARCH(1,1) volatility transform.

    Divides by the conditional standard deviation, producing
    approximately unit-variance residuals when the series has
    volatility clustering.

    Forward:   y'_t = y_t / sigma_t
               sigma_t^2 = omega + alpha * y_{t-1}^2 + beta * sigma_{t-1}^2
    Inverse:   D -> sigma_t * D

    Args:
        omega: baseline variance (intercept).
        alpha: weight on lagged squared observation (ARCH term).
        beta:  weight on lagged conditional variance (GARCH term).
        eps:   floor for sigma to avoid division by zero.

    Stationarity requires alpha + beta < 1. The unconditional variance
    is omega / (1 - alpha - beta).
    """
    assert omega > 0
    assert alpha >= 0
    assert beta >= 0

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            # Initialize conditional variance at the unconditional level
            # (or a sensible default if not stationary)
            persist = alpha + beta
            var0 = omega / (1 - persist) if persist < 1 else omega / eps
            return y / max(math.sqrt(var0), eps), {"var": var0, "last_y": y}

        var = omega + alpha * state["last_y"] ** 2 + beta * state["var"]
        sigma = math.sqrt(var) if var > eps * eps else eps
        y_prime = y / sigma
        return y_prime, {"var": var, "last_y": y}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        sigma = math.sqrt(state["var"]) if state["var"] > 1e-16 else 1e-8
        return [d.scale(sigma) for d in dists]

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Seasonal differencing:  y'_t = y_t - y_{t-s}
# ---------------------------------------------------------------------------

def seasonal_difference(period: int = 12):
    """Seasonal differencing transform.

    Forward:   y'_t = y_t - y_{t-s}   (difference with lag s)
    Inverse:   Shift each horizon's Dist by the appropriate
               lagged value from the buffer.

    Args:
        period: seasonal period s (e.g. 12 for monthly, 7 for daily-weekly).
    """
    assert period >= 1

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"buffer": [y]}
        buf = state["buffer"]
        if len(buf) >= period:
            y_prime = y - buf[-period]
        else:
            y_prime = 0.0
        buf.append(y)
        # Keep buffer bounded: need at most period + max_k values
        # but we don't know k here; keep 2*period to be safe
        if len(buf) > 2 * period:
            buf.pop(0)
        return y_prime, state

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        buf = list(state["buffer"])
        result = []
        for h, d in enumerate(dists):
            # The anchor for horizon h is y_{t-s+h+1}
            # which is buf[-(period - h - 1)] if available
            idx = len(buf) - period + h + 1
            if 0 <= idx < len(buf):
                anchor = buf[idx]
            elif idx >= len(buf) and result:
                # Use a previously recovered mean
                anchor = result[idx - len(buf)].mean
            else:
                anchor = 0.0
            result.append(d.shift(anchor))
        return result

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Signed power transform (works on any real value)
# ---------------------------------------------------------------------------

def power_transform(p: float = 0.5):
    """Signed power transform: compresses large values, handles negatives.

    Forward:   y'_t = sign(y_t) * |y_t|^p
    Inverse:   y_t  = sign(y') * |y'|^(1/p)

    For 0 < p < 1, this compresses the tails (like log) but works on
    all reals — no explosion on negatives.

    The inverse is nonlinear, so we linearize around the Dist mean
    for each component: if y' ~ N(mu, sigma^2) in transformed space,
    the inverse is approximately:
        mean_orig = sign(mu) * |mu|^(1/p)
        std_orig  = sigma * (1/p) * |mu|^(1/p - 1)   (delta method)

    Args:
        p: power in (0, 1). Smaller = more compression.
           p=0.5 is the signed square root.
    """
    assert 0 < p < 1
    inv_p = 1.0 / p

    def _fwd(y: float) -> float:
        return math.copysign(abs(y) ** p, y)

    def _inv(y_prime: float) -> float:
        return math.copysign(abs(y_prime) ** inv_p, y_prime)

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        return _fwd(y), state or {}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        result = []
        for d in dists:
            components = []
            for w, mu, sigma in d.components:
                orig_mean = _inv(mu)
                # Delta method: d/dy'[inv(y')] = (1/p) * |y'|^(1/p - 1)
                abs_mu = abs(mu)
                if abs_mu > 1e-12:
                    deriv = inv_p * abs_mu ** (inv_p - 1)
                else:
                    deriv = inv_p  # near zero, |y|^(1/p-1) ≈ 1 for p<1
                orig_std = max(sigma * deriv, 1e-12)
                components.append((w, orig_mean, orig_std))
            result.append(Dist(components))
        return result

    return forward, inverse_k
