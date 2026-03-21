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
        """Inverse: y_{t+h} = Delta_{t+h} + y_{t+h-s}.

        For h < s, the anchor y_{t+h-s} is in the buffer.
        For h >= s, the anchor is a previously recovered value.
        """
        buf = list(state["buffer"])
        recovered_means = []
        result = []
        for h in range(len(dists)):
            lag_idx = h - period  # relative to "future" start
            if lag_idx < 0:
                # Anchor is in the buffer: y_{t+h+1-s} = buf[len(buf) - s + h + 1 - 1]
                buf_idx = len(buf) - period + h
                if 0 <= buf_idx < len(buf):
                    anchor = buf[buf_idx]
                else:
                    anchor = 0.0
            else:
                # Anchor is a previously recovered value
                anchor = recovered_means[lag_idx]
            recovered_mean = dists[h].mean + anchor
            recovered_means.append(recovered_mean)
            result.append(dists[h].shift(anchor))
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


# ---------------------------------------------------------------------------
# AR(p) transform with online recursive least squares
# ---------------------------------------------------------------------------

def ar(order: int = 2, lam: float = 0.99, ridge: float = 1.0):
    """Autoregressive transform with online coefficient estimation.

    Subtracts the AR(p) prediction from each observation, leaving
    residuals. Coefficients are estimated via recursive least squares
    (RLS) with exponential forgetting.

    Forward:   y'_t = y_t - (phi_1 * y_{t-1} + ... + phi_p * y_{t-p})
    Inverse:   y_{t+h} = eps_{t+h} + phi_1 * y_{t+h-1} + ... + phi_p * y_{t+h-p}
               where past y values come from the buffer (known) or
               from previously recovered predictions (uncertain).

    Combined with other transforms:
        diff|ar(2)|leaf  ≈  ARIMA(2,1,0)
        frac(0.4)|ar(3)|leaf  ≈  ARFIMA(3,0.4,0)
        seas(12)|ar(2)|leaf  =  seasonal AR(2)

    Args:
        order: number of AR lags (p).
        lam: RLS forgetting factor in (0, 1]. 1.0 = no forgetting
             (OLS limit). 0.99 = slowly forgets old data.
        ridge: initial diagonal of the P matrix (regularization).
               Larger = more regularized initial estimates.
    """
    assert order >= 1
    assert 0 < lam <= 1
    p = order

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {
                "buffer": [],
                "phi": [0.0] * p,
                # P matrix stored as flat list (p x p), row-major
                "P": _eye(p, ridge),
                "n": 0,
            }

        buf = state["buffer"]
        phi = state["phi"]
        state["n"] += 1

        if len(buf) >= p:
            # Regressor: [y_{t-1}, y_{t-2}, ..., y_{t-p}]
            x = [buf[-(i + 1)] for i in range(p)]
            prediction = sum(phi[i] * x[i] for i in range(p))
            residual = y - prediction

            # RLS update
            P = state["P"]
            Px = _mat_vec(P, x, p)
            denom = lam + _dot(x, Px, p)
            if abs(denom) > 1e-15:
                K = [px / denom for px in Px]
                # Update phi
                for i in range(p):
                    phi[i] += K[i] * residual
                # Update P: P = (P - K * x' * P) / lam
                for i in range(p):
                    for j in range(p):
                        P[i * p + j] = (P[i * p + j] - K[i] * Px[j]) / lam
        else:
            residual = y

        buf.append(y)
        # Keep buffer bounded
        if len(buf) > 2 * p + 10:
            buf.pop(0)

        return residual, state

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        """Recover original-space predictions from residual predictions.

        At horizon h:
            y_{t+h} = eps_{t+h} + sum_{j=1}^{p} phi_j * y_{t+h-j}

        For j > h, y_{t+h-j} is known from the buffer.
        For j <= h, y_{t+h-j} is a previously recovered prediction.
        Variance propagates: ar_var += phi_j^2 * var of uncertain lags.
        """
        buf = list(state["buffer"])
        phi = state["phi"]
        recovered_means = []
        recovered_vars = []
        result = []

        for h in range(len(dists)):
            ar_mean = 0.0
            ar_var = 0.0
            for j in range(p):
                lag_h = h - j - 1  # which previous horizon provides this lag
                if lag_h < 0:
                    # Known value from buffer
                    buf_idx = len(buf) + lag_h
                    if 0 <= buf_idx < len(buf):
                        ar_mean += phi[j] * buf[buf_idx]
                else:
                    # Previously recovered prediction
                    if lag_h < len(recovered_means):
                        ar_mean += phi[j] * recovered_means[lag_h]
                        ar_var += phi[j] ** 2 * recovered_vars[lag_h]

            total_mean = dists[h].mean + ar_mean
            total_var = dists[h].var + ar_var
            total_std = math.sqrt(total_var) if total_var > 0 else max(dists[h].std, 1e-12)

            recovered_means.append(total_mean)
            recovered_vars.append(total_var)
            result.append(Dist.gaussian(total_mean, total_std))

        return result

    return forward, inverse_k


# --- Small matrix helpers for RLS (pure Python, no numpy) ---

def _eye(n: int, scale: float = 1.0) -> list[float]:
    """n x n identity matrix as flat list, scaled."""
    m = [0.0] * (n * n)
    for i in range(n):
        m[i * n + i] = scale
    return m


def _mat_vec(M: list[float], v: list[float], n: int) -> list[float]:
    """Matrix-vector product for n x n flat matrix."""
    result = [0.0] * n
    for i in range(n):
        s = 0.0
        for j in range(n):
            s += M[i * n + j] * v[j]
        result[i] = s
    return result


def _dot(a: list[float], b: list[float], n: int) -> float:
    """Dot product."""
    return sum(a[i] * b[i] for i in range(n))
