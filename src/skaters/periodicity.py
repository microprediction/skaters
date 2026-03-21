"""Online periodicity detection via running autocorrelation.

Maintains exponentially weighted estimates of autocorrelation at
a set of candidate lags. The top-scoring lags are the detected
periods, which can be used to dynamically add seasonal_difference
transforms during search expansion.

All O(n_lags) per observation. No batch computation.
"""

from __future__ import annotations
import math


# Common periods to scan
DEFAULT_LAGS = [2, 3, 4, 5, 6, 7, 12, 14, 24, 28, 30, 52, 60, 90, 168, 365]


def period_detector(
    lags: list[int] | None = None,
    alpha: float = 0.01,
    min_observations: int = 50,
):
    """Create an online period detector.

    Args:
        lags: candidate periods to test. Defaults to common periods.
        alpha: EMA smoothing for the running autocorrelation estimates.
        min_observations: don't report periods until this many obs seen.

    Returns:
        A callable: (y, state) -> (top_periods, state)
        where top_periods is a list of (lag, acf_score) tuples sorted
        by |acf| descending.
    """
    if lags is None:
        lags = list(DEFAULT_LAGS)

    max_lag = max(lags)

    def _detect(y: float, state: dict | None) -> tuple[list[tuple[int, float]], dict]:
        if state is None:
            state = {
                "buffer": [],
                "n": 0,
                "mean": 0.0,
                "var": 0.0,
                # Per-lag: running EMA of (y_t - mu) * (y_{t-L} - mu)
                "cross": {L: 0.0 for L in lags},
            }

        buf = state["buffer"]
        buf.append(y)
        state["n"] += 1

        # Update running mean and variance
        diff = y - state["mean"]
        state["mean"] += alpha * diff
        state["var"] = (1 - alpha) * (state["var"] + alpha * diff * diff)

        mu = state["mean"]
        var = state["var"]

        # Update cross-correlation for each lag
        for L in lags:
            if len(buf) > L:
                y_lagged = buf[-(L + 1)]
                cross = (y - mu) * (y_lagged - mu)
                state["cross"][L] = (1 - alpha) * state["cross"][L] + alpha * cross

        # Trim buffer
        if len(buf) > max_lag + 1:
            buf.pop(0)

        # Compute ACF scores
        if state["n"] < min_observations or var < 1e-12:
            return [], state

        scores = []
        for L in lags:
            if state["n"] > L:
                acf = state["cross"][L] / var if var > 0 else 0.0
                scores.append((L, acf))

        # Sort by |acf| descending
        scores.sort(key=lambda x: abs(x[1]), reverse=True)
        return scores, state

    return _detect


def top_periods(scores: list[tuple[int, float]], threshold: float = 0.3, max_periods: int = 3) -> list[int]:
    """Extract the best periods from detector scores.

    Args:
        scores: output from period_detector
        threshold: minimum |acf| to consider significant
        max_periods: maximum number of periods to return

    Returns:
        List of detected periods (lags), sorted by strength.
    """
    return [lag for lag, acf in scores[:max_periods] if abs(acf) >= threshold]
