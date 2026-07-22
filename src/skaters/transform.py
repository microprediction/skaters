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
        # Center against the PRIOR mean (centering by the post-update mean would
        # shrink the residual by (1-alpha) — systematic overconfidence). Scale by
        # the updated EWMA std, which avoids a cold-start divide-by-zero. The
        # variance recursion is the standard EWMA var = (1-a) var + a diff^2; the
        # previous (1-a)(var + a diff^2) biased the scale low by sqrt(1-a).
        mu_new = mu + alpha * diff
        var = (1 - alpha) * var + alpha * diff * diff
        sigma = math.sqrt(var) if var > eps * eps else eps
        y_prime = diff / sigma
        return y_prime, {"mu": mu_new, "var": var}

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
        # Residual is the one-step-ahead forecast error (against the PRIOR level),
        # not the post-update smoothing residual. Using the post-update level would
        # shrink the residual by (1-alpha), making the leaf's variance — and hence
        # the predictive interval — too small by that factor (systematic
        # overconfidence). The level update is unchanged, so point forecasts are
        # identical; only the predictive spread is corrected.
        residual = y - state["level"]
        level = state["level"] + alpha * residual
        return residual, {"level": level}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        level = state["level"]
        return [d.shift(level) for d in dists]

    return forward, inverse_k


def ou_transform(kappa: float = 0.1, alpha: float = 0.02):
    """Ornstein-Uhlenbeck mean-reversion as a bijective transform.

    Maintains a running mean ``m`` (EMA, rate ``alpha``) and reverts the current
    value toward it with persistence ``phi = 1 - kappa``:

        forecast_t = m + phi * (y_t - m)        (one-step-ahead)
        residual_t = y_t - forecast_{t-1}

    ``kappa`` in (0, 1] is the reversion speed: ``kappa -> 0`` is a random walk
    (no reversion), ``kappa = 1`` reverts fully to the mean in one step (which is
    :func:`ema_transform`). The intermediate, partial reversion is what neither
    ``ema_transform`` (full reversion, ``phi = 0``) nor ``ar`` (no intercept, so
    reversion is toward zero, not a level) expresses, even composed. Reversion is
    toward a *nonzero running level*, so it is meaningful in a positive coordinate
    (compose under ``yeo_johnson(0.5)`` for the sqrt / CIR-flavoured coupling, or
    ``yeo_johnson(0.0)`` for the log / geometric one).

    The multi-step inverse uses the exact OU predictive moments: the h-step mean
    decays geometrically toward ``m`` as ``phi**h``, and the h-step standard
    deviation grows as ``sqrt((1 - phi**(2h)) / (1 - phi**2))``, saturating at the
    stationary level (and reducing to ``sqrt(h)`` random-walk growth as
    ``phi -> 1``). See ``benchmarks/cir_ablation.py`` for the validation: the edge
    over the random-walk pool is a multi-step phenomenon, growing with horizon.

    Args:
        kappa: reversion speed in (0, 1].
        alpha: EWMA rate for the running mean ``m``.
    """
    assert 0.0 < kappa <= 1.0
    assert 0.0 < alpha < 1.0
    phi = 1.0 - kappa

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None or not math.isfinite(y):
            y0 = y if math.isfinite(y) else 0.0
            return 0.0, {"m": y0, "fc": y0, "y": y0}
        resid = y - state["fc"]
        if not math.isfinite(resid):
            resid = 0.0
        m = state["m"] + alpha * (y - state["m"])
        fc = m + phi * (y - m)
        return resid, {"m": m, "fc": fc, "y": y}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        m, ylast = state["m"], state["y"]
        out = []
        for h, d in enumerate(dists, start=1):
            center = m + (phi ** h) * (ylast - m)
            if phi < 1.0 - 1e-9:
                g = math.sqrt((1.0 - phi ** (2 * h)) / (1.0 - phi * phi))
            else:
                g = math.sqrt(h)               # phi -> 1: random-walk variance growth
            out.append(d.scale(g).shift(center))   # leaf is zero-mean: scale hits spread
        return out

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Theta method (Assimakopoulos & Nikolopoulos, 2000)
# ---------------------------------------------------------------------------

def theta(alpha: float = 0.1):
    """Theta method as a transform: SES + half the OLS slope.

    The Theta method decomposes the series into two "theta lines" and
    combines their forecasts. The standard version (theta=2) is
    equivalent to SES with a drift correction of half the OLS slope.

    Forward:   y'_t = y_t - (ses_t + b_t/2)   (residual from theta forecast)
    Inverse:   y_{t+h} = ses_t + h * b_t/2 + residual

    The OLS slope is estimated online via running regression of y on t.

    This was the best simple method in M3 and near-best in M4.

    Args:
        alpha: SES smoothing factor in (0, 1).
    """
    assert 0 < alpha < 1

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {
                "ses": y,
                "t": 1,
                "sum_t": 1.0,
                "sum_t2": 1.0,
                "sum_y": y,
                "sum_ty": y,
            }

        s = state
        s["t"] += 1
        t = s["t"]

        # One-step-ahead theta forecast from the PRIOR state (SES + half the OLS
        # slope), then update. Forecasting after folding y into ses/slope would
        # leak y into its own residual and shrink the predictive interval.
        forecast = s["ses"] + s.get("slope", 0.0) / 2
        residual = y - forecast

        # Update SES
        s["ses"] = alpha * y + (1 - alpha) * s["ses"]

        # Update running OLS: y = a + b*t
        s["sum_t"] += t
        s["sum_t2"] += t * t
        s["sum_y"] += y
        s["sum_ty"] += t * y

        n = t
        denom = n * s["sum_t2"] - s["sum_t"] ** 2
        if abs(denom) > 1e-12:
            slope = (n * s["sum_ty"] - s["sum_t"] * s["sum_y"]) / denom
        else:
            slope = 0.0

        s["slope"] = slope
        return residual, s

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        ses = state["ses"]
        slope = state.get("slope", 0.0)
        result = []
        cumsum_var = 0.0
        for h, d in enumerate(dists):
            cumsum_var += d.var
            forecast = ses + (h + 1) * slope / 2 + d.mean
            std = math.sqrt(cumsum_var) if cumsum_var > 0 else max(d.std, 1e-12)
            result.append(Dist.gaussian(forecast, std))
        return result

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Random walk with drift: careful long-memory drift estimation
# ---------------------------------------------------------------------------

def drift(alpha: float = 0.002, shrinkage: float = 0.001):
    """Random walk with adaptive drift removal.

    Differences the series AND subtracts an estimated drift, leaving
    centered residuals. The drift is estimated as a heavily smoothed
    mean of increments, with shrinkage toward zero.

    Forward:   dy_t = y_t - y_{t-1}
               mu_t = (1 - alpha - shrinkage) * mu_{t-1} + alpha * dy_t
               y'_t = dy_t - mu_t

    Inverse:   y_{t+h} = y_t + h * mu_t + sum(residuals_1..h)

    The drift estimator has two forces:
    - alpha pulls toward the latest increment (adaptation)
    - shrinkage pulls toward zero (regularization / Bachelier prior)

    With the defaults (alpha=0.002, shrinkage=0.001), the effective
    half-life is ~230 observations, and the drift decays to zero in
    ~1000 observations without reinforcement.

    Args:
        alpha: learning rate for drift estimate. Smaller = longer memory.
        shrinkage: per-step pull toward zero. Encodes the prior that
            drift is unlikely / temporary. Set to 0 for no shrinkage.
    """
    assert 0 < alpha < 1
    assert 0 <= shrinkage < 1
    decay = 1 - alpha - shrinkage

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"last": y, "mu": 0.0}
        dy = y - state["last"]
        # Residual is the increment minus the PRIOR drift estimate (the one-step
        # forecast error); subtracting the post-update drift would leak dy into its
        # own residual and shrink the predictive interval. Drift update unchanged.
        residual = dy - state["mu"]
        mu = decay * state["mu"] + alpha * dy
        return residual, {"last": y, "mu": mu}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        """Multi-step inverse: y_{t+h} = y_t + h * mu + cumulative residuals.

        The drift contributes a deterministic shift of h * mu per horizon.
        The residual uncertainty accumulates as with difference().
        """
        anchor = state["last"]
        mu = state["mu"]
        result = []
        cumsum_mean = 0.0
        cumsum_var = 0.0
        for h, d in enumerate(dists):
            cumsum_mean += d.mean
            cumsum_var += d.var
            # Total prediction: anchor + (h+1)*drift + cumulative residual
            total_mean = anchor + (h + 1) * mu + cumsum_mean
            total_std = math.sqrt(cumsum_var) if cumsum_var > 0 else max(d.std, 1e-12)
            result.append(Dist.gaussian(total_mean, total_std))
        return result

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Holt linear: coupled level + trend (Holt 1957)
# ---------------------------------------------------------------------------

def holt_linear(alpha: float = 0.1, beta: float = 0.05):
    """Holt's linear exponential smoothing as a transform.

    Maintains coupled level and trend estimates:
        l_t = alpha * y_t + (1 - alpha) * (l_{t-1} + b_{t-1})
        b_t = beta * (l_t - l_{t-1}) + (1 - beta) * b_{t-1}

    Forward:   y'_t = y_t - (l_t + b_t)   (one-step-ahead residual)
    Inverse:   y_{t+h} = l_t + h * b_t + residual

    This is the classic Holt (1957) method. Unlike our drift() transform
    which estimates drift from differences, Holt's method couples the
    level and trend updates, which is better at tracking accelerating or
    decelerating trends.

    Args:
        alpha: level smoothing in (0, 1). Higher = more reactive level.
        beta:  trend smoothing in (0, 1). Higher = more reactive trend.
    """
    assert 0 < alpha < 1
    assert 0 < beta < 1

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"level": y, "trend": 0.0}
        l_prev = state["level"]
        b_prev = state["trend"]
        l_new = alpha * y + (1 - alpha) * (l_prev + b_prev)
        b_new = beta * (l_new - l_prev) + (1 - beta) * b_prev
        # One-step-ahead prediction was l_prev + b_prev
        residual = y - (l_prev + b_prev)
        return residual, {"level": l_new, "trend": b_new}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        """Inverse: forecast is level + h * trend + residual.

        Variance accumulates across horizons (independent residuals).
        """
        level = state["level"]
        trend = state["trend"]
        result = []
        cumsum_var = 0.0
        for h, d in enumerate(dists):
            cumsum_var += d.var
            forecast = level + (h + 1) * trend + d.mean
            std = math.sqrt(cumsum_var) if cumsum_var > 0 else max(d.std, 1e-12)
            result.append(Dist.gaussian(forecast, std))
        return result

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

        For h < s, the anchor y_{t+h-s} is an *observed* value in the buffer, so
        it is deterministic and only shifts the location. For h >= s the anchor is
        a value we recovered earlier in this same call, which carries its own
        predictive variance; that variance must be added, exactly as the ordinary
        ``difference`` inverse accumulates ``cumsum_var`` along the integration
        chain and ``grouped_ar`` accumulates ``recovered_vars``. Dropping it would
        understate uncertainty at every horizon h >= s.

        Adding an independent Gaussian anchor variance to a mixture is a
        convolution: shift each component mean and inflate each component
        variance by ``anchor_var`` (mixture variance then grows by exactly
        ``anchor_var``). When ``anchor_var == 0`` this is the plain shift, which
        preserves the leaf's mixture shape.
        """
        buf = list(state["buffer"])
        recovered_means = []
        recovered_vars = []
        result = []
        for h in range(len(dists)):
            lag_idx = h - period  # relative to "future" start
            if lag_idx < 0:
                # Anchor is in the buffer: y_{t+h+1-s} = buf[len(buf) - s + h + 1 - 1]
                buf_idx = len(buf) - period + h
                anchor_mean = buf[buf_idx] if 0 <= buf_idx < len(buf) else 0.0
                anchor_var = 0.0
            else:
                # Anchor is a value recovered earlier in this call: it is uncertain.
                anchor_mean = recovered_means[lag_idx]
                anchor_var = recovered_vars[lag_idx]
            recovered_means.append(dists[h].mean + anchor_mean)
            recovered_vars.append(dists[h].var + anchor_var)
            if anchor_var > 0.0:
                result.append(Dist([(w, m + anchor_mean, math.sqrt(s * s + anchor_var))
                                    for w, m, s in dists[h].components]))
            else:
                result.append(dists[h].shift(anchor_mean))
        return result

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Seasonal anchor: hedged seasonal location (phase-EMA blended with naive)
# ---------------------------------------------------------------------------

def seasonal_anchor(period: int, alpha: float = 0.2, weight: float = 0.5):
    """Residual from a hedged seasonal anchor.

    Forward:   y'_t = y_t - a_t,  a_t = weight * phaseEMA_{p(t)} + (1-weight) * y_{t-s}
    Inverse:   shift each horizon's Dist by its anchor; for h >= s the naive
               component is a value recovered earlier in the same call and its
               variance is convolved in (as in ``seasonal_difference``).

    The phase-EMA is a recency-weighted mean of same-phase values (memory
    ~1/alpha cycles); the seasonal-naive is the single value one period ago.
    The naive alone adapts instantly but is one noisy draw; the phase-EMA
    averages the noise but lags level shifts. The blend beats either alone on
    seasonal series. ``weight=0`` recovers ``seasonal_difference``.

    Forecasting from same-phase component series follows Viole's NNS package
    (``NNS.ARMA``, CRAN, since 2017).
    """
    assert period >= 1
    assert 0 < alpha < 1
    assert 0.0 <= weight <= 1.0

    def _anchor(ema, snaive):
        return (weight * ema + (1.0 - weight) * snaive) if ema is not None else snaive

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"ema": [None] * period, "buffer": [y], "n": 1}
        buf = state["buffer"]
        p = state["n"] % period
        snaive = buf[-period] if len(buf) >= period else buf[-1]
        y_prime = y - _anchor(state["ema"][p], snaive)
        e = state["ema"][p]
        state["ema"][p] = y if e is None else e + alpha * (y - e)
        buf.append(y)
        if len(buf) > 2 * period:
            buf.pop(0)
        state["n"] += 1
        return y_prime, state

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        buf = state["buffer"]
        recovered_means: list[float] = []
        recovered_vars: list[float] = []
        out = []
        for h in range(len(dists)):
            p = (state["n"] + h) % period
            lag_idx = h - period
            if lag_idx < 0:
                buf_idx = len(buf) - period + h
                snaive = buf[buf_idx] if 0 <= buf_idx < len(buf) else buf[-1]
                snaive_var = 0.0
            else:
                snaive = recovered_means[lag_idx]
                snaive_var = recovered_vars[lag_idx]
            a_mean = _anchor(state["ema"][p], snaive)
            a_var = ((1.0 - weight) ** 2) * snaive_var
            recovered_means.append(dists[h].mean + a_mean)
            recovered_vars.append(dists[h].var + a_var)
            if a_var > 0.0:
                out.append(Dist([(w, m + a_mean, math.sqrt(s * s + a_var))
                                 for w, m, s in dists[h].components]))
            else:
                out.append(dists[h].shift(a_mean))
        return out

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Seasonal scale: phase-indexed running standardization
# ---------------------------------------------------------------------------

def seasonal_scale(period: int, alpha: float = 0.05, center: bool = False,
                   eps: float = 1e-8):
    """Phase-indexed running standardization (seasonal heteroskedasticity).

    Forward:   y'_t = (y_t - mu_{p(t)}) / sigma_{p(t)},   p(t) = t mod period
    Inverse:   affine by the stats of the phase being *forecast*: dists[h] is
               the (h+1)-step-ahead predictive, so its phase is
               (n + h) mod period where n counts observations seen.

    Each phase keeps its own EWMA mean and variance, so predictive width (and
    with ``center=True`` location) is conditioned on the phase of the cycle —
    the seasonal volatility that ``seasonal_difference`` alone cannot express
    (its residual scale is phase-averaged). ``center=False`` divides by the
    phase sigma without subtracting the phase mean; use it composed OVER
    ``seasonal_difference(period)``, where location is already handled.

    A phase's variance is shrunk toward the global EWMA variance by visit
    count, w = visits / (visits + 3), so thin phases (few observed cycles)
    degrade gracefully to plain ``standardize`` instead of trusting a noisy
    per-phase estimate. ``alpha`` is the per-phase EWMA rate — memory is
    ~1/alpha *visits*, i.e. cycles; the global stats use ``alpha / period``
    so both remember the same span of raw observations.
    """
    assert period >= 1
    assert 0 < alpha < 1
    a_g = alpha / period
    K0 = 3.0                                     # shrinkage prior strength (visits)

    def _vg(state):
        """Bias-corrected global variance: the EWMA runs at the slow rate
        a_g = alpha/period, so from a zero start it is badly low for the first
        ~1/a_g observations; dividing by 1-(1-a_g)^updates removes that bias
        exactly (after one update it equals the one-sample estimate)."""
        updates = state["n"] - 1
        if updates <= 0:
            return 0.0
        return state["var_g"] / (1.0 - (1.0 - a_g) ** updates)

    def _phase_stats(state, p):
        """Shrunk (mu, sigma) for phase p under the current state.

        Variance shrinks toward the global in LOG space (geometric blend):
        additive blending would let the global variance dominate quiet phases
        whenever the phase spread is large — at a 50x scale ratio, 0.3 %
        additive weight on the global still doubles the quiet phase's sigma.
        """
        w = state["vis"][p] / (state["vis"][p] + K0)
        vp = max(state["var"][p], eps * eps)
        vg = max(_vg(state), eps * eps)
        var_eff = math.exp(w * math.log(vp) + (1.0 - w) * math.log(vg))
        mu_eff = (w * state["mu"][p] + (1.0 - w) * state["mu_g"]) if center else 0.0
        return mu_eff, math.sqrt(var_eff)

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            return 0.0, {"mu_g": y, "var_g": 0.0,
                         "mu": [0.0] * period, "var": [0.0] * period,
                         "vis": [0] * period, "n": 1}
        p = state["n"] % period
        # Center against the PRIOR mean but scale by the UPDATED variance,
        # exactly as standardize does (prior-mean centering avoids systematic
        # overconfidence; updated variance avoids the cold-start divide-by-zero).
        mu_eff, _ = _phase_stats(state, p)
        dg = y - state["mu_g"]
        state["mu_g"] += a_g * dg
        state["var_g"] = (1 - a_g) * state["var_g"] + a_g * dg * dg
        if state["vis"][p] == 0:            # first visit seeds from global stats
            state["mu"][p] = y
            state["var"][p] = _vg(state)
        else:
            dp = y - state["mu"][p]
            state["mu"][p] += alpha * dp
            state["var"][p] = (1 - alpha) * state["var"][p] + alpha * dp * dp
        state["vis"][p] += 1
        state["n"] += 1
        _, sigma = _phase_stats(state, p)
        y_prime = (y - mu_eff) / sigma
        return y_prime, state

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        out = []
        for h in range(len(dists)):
            mu_eff, sigma = _phase_stats(state, (state["n"] + h) % period)
            out.append(dists[h].affine(sigma, mu_eff))
        return out

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Signed power transform (works on any real value)
# ---------------------------------------------------------------------------

def _exact_inverse_k(inv_fn):
    """Build an inverse_k that emits the exact pushforward.

    The table window adapts to each predictive: [m - 10s, m + 10s] over the
    mixture. A fixed window fails in level coordinates (positive levels live
    at z ~ 2 sqrt(y) under lambda = 0.5, far from any static range) and
    everything beyond a table extrapolates with the wrong curvature.
    """
    from skaters.pushforward import PushforwardDist, table_from_map

    def inverse_k(dists: list, state: dict) -> list:
        out = []
        for d in dists:
            lo = min(m - 10.0 * s for _, m, s in d.components)
            hi = max(m + 10.0 * s for _, m, s in d.components)
            ys, zs = table_from_map(inv_fn, lo, hi)
            out.append(PushforwardDist(d, ys, zs, inv_fn=inv_fn))
        return out

    return inverse_k


def power_transform(p: float = 0.5, exact: bool = False):
    """Signed power transform: compresses large values, handles negatives.

    Forward:   y'_t = sign(y_t) * |y_t|^p
    Inverse:   y_t  = sign(y') * |y'|^(1/p)

    For 0 < p < 1, this compresses the tails (like log) but works on
    all reals — no explosion on negatives.

    By default the inverse linearizes around each component's mean
    (delta method):
        mean_orig = sign(mu) * |mu|^(1/p)
        std_orig  = sigma * (1/p) * |mu|^(1/p - 1)

    ``exact=True`` emits the exact pushforward instead (see
    :mod:`skaters.pushforward` and :func:`yeo_johnson` for when the delta
    method's missing skew becomes material).

    Args:
        p: power in (0, 1). Smaller = more compression.
           p=0.5 is the signed square root.
        exact: emit :class:`PushforwardDist` (exact change of variables)
            instead of delta-method component mapping.
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

    return forward, (_exact_inverse_k(_inv) if exact else inverse_k)


def yeo_johnson(lmbda: float = 0.0, exact: bool = False):
    """Yeo-Johnson coordinate transform — the signed Box-Cox family.

    A one-parameter family that picks the *coordinate in which the series is
    simple*. It subsumes log (lmbda=0, on the shifted level), identity
    (lmbda=1), and reciprocal-ish (lmbda<0) shapes, but unlike Box-Cox it is
    defined for all reals (no positivity requirement) — so the same primitive
    expresses a non-negativity prior (lmbda~0 makes the inverse predictive
    non-negative for non-negative data) and a generic re-scaling prior.

    Forward:
        y >= 0:  ((y+1)**L - 1) / L            (L != 0);   log(y+1)      (L == 0)
        y <  0:  -(((-y+1)**(2-L) - 1)/(2-L))  (L != 2);  -log(-y+1)     (L == 2)

    By default each Dist component is mapped by the exact inverse on the mean
    and the delta method on the std (deriv = d inv / dy'). The delta method
    cannot carry the skew of the coordinate change (the mapped mixture is
    location-symmetric about the mapped median) and its error grows with the
    predictive spread, hence with horizon. ``exact=True`` emits the exact
    pushforward (:class:`skaters.pushforward.PushforwardDist`) instead: on
    120 strictly positive FRED level series under the standalone composition
    from the README (leaf under OU under Yeo-Johnson, k=10), exact beats
    delta by a median +0.018 nats at h=10 (72% of series) at lmbda=0, and
    +0.015 (78%) at lmbda=0.5, with h=1 a wash. Inside the candidate pool the
    trunk consumes means, one-step likelihoods and warm-up mixtures, all at
    small spreads where the two agree, so the pool keeps the default.

    Fit the *family* the NFL-safe way: put a coarse grid of lmbda in the
    candidate pool (see :func:`skaters.api._build_candidates`) and let the
    ensemble weight the coordinate online, rather than MLE-ing a single value.

    Args:
        lmbda: the transform parameter. 0 = log1p (multiplicative / non-negative),
            1 = identity, 0.5 = signed-sqrt-ish compression.
        exact: emit :class:`PushforwardDist` (exact change of variables)
            instead of delta-method component mapping. Prefer it for
            standalone conjugation at multi-step horizons.
    """
    L = float(lmbda)

    def _fwd(y: float) -> float:
        if y >= 0.0:
            return math.log1p(y) if L == 0.0 else ((y + 1.0) ** L - 1.0) / L
        if L == 2.0:
            return -math.log1p(-y)
        return -(((-y + 1.0) ** (2.0 - L) - 1.0) / (2.0 - L))

    def _inv(yp: float) -> float:
        # clamp exp arguments to avoid OverflowError on pathological inputs
        # (exp(350) ~ 1e152 keeps var (its square) finite); the value is huge-but-finite, not NaN.
        if yp >= 0.0:                       # forward is monotone, sign-preserving
            if L == 0.0:
                return math.expm1(min(yp, 350.0))
            base = max(L * yp + 1.0, 1e-12)
            return base ** (1.0 / L) - 1.0
        if L == 2.0:
            return 1.0 - math.exp(min(-yp, 350.0))
        base = max(-(2.0 - L) * yp + 1.0, 1e-12)
        return 1.0 - base ** (1.0 / (2.0 - L))

    def _dinv(yp: float) -> float:
        """d inv / dy' at yp (for the delta-method std)."""
        if yp >= 0.0:
            if L == 0.0:
                return math.exp(min(yp, 350.0))
            base = max(L * yp + 1.0, 1e-12)
            return base ** (1.0 / L - 1.0)
        if L == 2.0:
            return math.exp(min(-yp, 350.0))
        base = max(-(2.0 - L) * yp + 1.0, 1e-12)
        return base ** (1.0 / (2.0 - L) - 1.0)

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        return _fwd(y), state or {}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        result = []
        for d in dists:
            comps = []
            for w, mu, sigma in d.components:
                comps.append((w, _inv(mu), max(sigma * _dinv(mu), 1e-12)))
            result.append(Dist(comps))
        return result

    return forward, (_exact_inverse_k(_inv) if exact else inverse_k)


# ---------------------------------------------------------------------------
# AR(p) transform with online recursive least squares
# ---------------------------------------------------------------------------

def ar(order: int = 2, lam: float = 0.99, ridge: float = 1.0,
       decay: float = 0.0):
    """Autoregressive transform with online coefficient estimation.

    Subtracts the AR(p) prediction from each observation, leaving
    residuals. Coefficients are estimated via recursive least squares
    (RLS) with exponential forgetting.

    Forward:   y'_t = y_t - (phi_1 * y_{t-1} + ... + phi_p * y_{t-p})
    Inverse:   y_{t+h} = eps_{t+h} + phi_1 * y_{t+h-1} + ... + phi_p * y_{t+h-p}

    Combined with other transforms:
        diff|ar(2)|leaf  ≈  ARIMA(2,1,0)
        frac(0.4)|ar(3)|leaf  ≈  ARFIMA(3,0.4,0)
        seas(12)|ar(2)|leaf  =  seasonal AR(2)

    Args:
        order: number of AR lags (p).
        lam: RLS forgetting factor in (0, 1]. 1.0 = no forgetting.
        ridge: baseline diagonal of the P matrix (regularization).
        decay: Minnesota prior strength. If > 0, the initial prior
               variance for lag j is ridge / (j+1)^decay. This shrinks
               distant lags more aggressively toward zero (Litterman 1986).
               decay=0 is uniform prior (standard ridge).
               decay=1 is the standard Minnesota prior.
               decay=2 is aggressive shrinkage.
    """
    assert order >= 1
    assert 0 < lam <= 1
    assert decay >= 0
    p = order

    def _init_P() -> list[float]:
        """Build initial P matrix with optional Minnesota-style decay."""
        P = [0.0] * (p * p)
        for j in range(p):
            P[j * p + j] = ridge / ((j + 1) ** decay) if decay > 0 else ridge
        return P

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {
                "buffer": [],
                "phi": [0.0] * p,
                "P": _init_P(),
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
                # Guard against RLS covariance windup: under low-excitation input
                # P inflates by 1/lam each step and eventually overflows to inf,
                # yielding nan coefficients. Reset the covariance (keeping phi) if
                # it grows implausibly large or turns non-finite. It never triggers
                # on well-excited data, so results there are unchanged.
                if not all(math.isfinite(v) for v in P) or max(abs(v) for v in P) > 1e10:
                    P[:] = _init_P()
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


def grouped_ar(max_lag: int = 16, lam: float = 0.99, ridge: float = 1.0):
    """AR transform with geometrically grouped coefficients.

    Instead of estimating one coefficient per lag (p parameters),
    lags are grouped into geometrically growing bins:
        group 0: lag 1       (1 lag)
        group 1: lags 2-3    (2 lags, shared coefficient)
        group 2: lags 4-7    (4 lags, shared coefficient)
        group 3: lags 8-15   (8 lags, shared coefficient)
        ...

    This gives O(log2(max_lag)) parameters for max_lag lags.
    Motivated by the MDL principle: the number of effective
    parameters should grow logarithmically with the model order.

    The RLS estimates the group-level coefficients. At prediction
    time, each lag uses its group's coefficient.

    Args:
        max_lag: maximum lag to include.
        lam: RLS forgetting factor in (0, 1]. 1.0 = no forgetting.
        ridge: initial regularization (> 0).
    """
    assert max_lag >= 1
    assert 0 < lam <= 1      # divides by lam in the RLS update; 0 would crash
    assert ridge > 0

    # Build the grouping: which group does each lag belong to?
    groups = _build_groups(max_lag)
    n_groups = max(groups) + 1

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {
                "buffer": [],
                "theta": [0.0] * n_groups,  # group-level coefficients
                "P": _eye(n_groups, ridge),
                "n": 0,
            }

        buf = state["buffer"]
        theta = state["theta"]
        state["n"] += 1

        if len(buf) >= max_lag:
            # Build group-aggregated regressor
            x = _group_regressor(buf, groups, n_groups, max_lag)
            prediction = sum(theta[g] * x[g] for g in range(n_groups))
            residual = y - prediction

            # RLS update on group-level coefficients
            P = state["P"]
            Px = _mat_vec(P, x, n_groups)
            denom = lam + _dot(x, Px, n_groups)
            if abs(denom) > 1e-15:
                K = [px / denom for px in Px]
                for g in range(n_groups):
                    theta[g] += K[g] * residual
                for i in range(n_groups):
                    for j in range(n_groups):
                        P[i * n_groups + j] = (
                            P[i * n_groups + j] - K[i] * Px[j]
                        ) / lam
                # RLS covariance windup guard (see ar()): reset P if it inflates
                # implausibly or turns non-finite; keeps theta. No effect on
                # well-excited data.
                if not all(math.isfinite(v) for v in P) or max(abs(v) for v in P) > 1e10:
                    P[:] = _eye(n_groups, ridge)
        else:
            residual = y

        buf.append(y)
        if len(buf) > max_lag + 10:
            buf.pop(0)

        return residual, state

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        buf = list(state["buffer"])
        theta = state["theta"]
        # Expand group coefficients to per-lag coefficients
        phi = [theta[groups[j]] for j in range(max_lag)]

        recovered_means = []
        recovered_vars = []
        result = []

        for h in range(len(dists)):
            ar_mean = 0.0
            ar_var = 0.0
            for j in range(max_lag):
                lag_h = h - j - 1
                if lag_h < 0:
                    buf_idx = len(buf) + lag_h
                    if 0 <= buf_idx < len(buf):
                        ar_mean += phi[j] * buf[buf_idx]
                else:
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


def _build_groups(max_lag: int) -> list[int]:
    """Assign each lag index to a geometric group.

    Lag 0 → group 0 (size 1)
    Lags 1-2 → group 1 (size 2)
    Lags 3-6 → group 2 (size 4)
    Lags 7-14 → group 3 (size 8)
    ...
    """
    groups = []
    g = 0
    size = 1
    assigned = 0
    while assigned < max_lag:
        for _ in range(size):
            if assigned >= max_lag:
                break
            groups.append(g)
            assigned += 1
        g += 1
        size *= 2
    return groups


def _group_regressor(buf: list[float], groups: list[int],
                     n_groups: int, max_lag: int) -> list[float]:
    """Aggregate lagged values by group (sum within each group)."""
    x = [0.0] * n_groups
    for j in range(max_lag):
        x[groups[j]] += buf[-(j + 1)]
    return x


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
