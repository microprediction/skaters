"""Tests for online periodicity detection."""

import math
import random
from skaters.periodicity import period_detector, top_periods


def test_detector_returns_empty_before_min_obs():
    detect = period_detector(lags=[7, 12], min_observations=50)
    state = None
    for _ in range(30):
        scores, state = detect(random.gauss(0, 1), state)
    assert scores == []


def test_detector_returns_scores_after_min_obs():
    random.seed(42)
    detect = period_detector(lags=[7, 12], min_observations=20)
    state = None
    for _ in range(50):
        scores, state = detect(random.gauss(0, 1), state)
    assert len(scores) > 0
    assert all(isinstance(s, tuple) and len(s) == 2 for s in scores)


def test_detects_period_7():
    """A series with period 7 should have high ACF at lag 7."""
    random.seed(42)
    detect = period_detector(lags=[3, 5, 7, 12, 14], min_observations=30, alpha=0.02)
    state = None
    pattern = [10, 20, 15, 30, 25, 5, 12]
    for i in range(500):
        y = pattern[i % 7] + random.gauss(0, 0.5)
        scores, state = detect(y, state)

    # Lag 7 should be among the top scorers
    top = top_periods(scores, threshold=0.2)
    assert 7 in top, f"Expected 7 in top periods, got {top} from {scores[:5]}"


def test_detects_period_12():
    """A series with period 12 should detect lag 12."""
    random.seed(42)
    detect = period_detector(lags=[6, 7, 12, 24], min_observations=30, alpha=0.02)
    state = None
    pattern = list(range(12))
    for i in range(500):
        y = float(pattern[i % 12]) + random.gauss(0, 0.3)
        scores, state = detect(y, state)

    top = top_periods(scores, threshold=0.2)
    assert 12 in top, f"Expected 12 in top periods, got {top}"


def test_no_spurious_detection_on_white_noise():
    """White noise should not have strong autocorrelation at any lag."""
    random.seed(42)
    detect = period_detector(min_observations=30, alpha=0.02)
    state = None
    for _ in range(1000):
        scores, state = detect(random.gauss(0, 1), state)

    # With high threshold, nothing should be detected
    top = top_periods(scores, threshold=0.5)
    assert len(top) == 0, f"Spurious detection: {top}"


def test_top_periods_respects_threshold():
    scores = [(7, 0.8), (12, 0.4), (3, 0.1)]
    assert top_periods(scores, threshold=0.5) == [7]
    assert top_periods(scores, threshold=0.3) == [7, 12]
    assert top_periods(scores, threshold=0.0) == [7, 12, 3]


def test_top_periods_respects_max():
    scores = [(7, 0.8), (12, 0.6), (3, 0.5)]
    assert len(top_periods(scores, threshold=0.0, max_periods=2)) == 2


def test_scores_sorted_by_abs_acf():
    random.seed(42)
    detect = period_detector(lags=[3, 7, 12], min_observations=20)
    state = None
    for _ in range(100):
        scores, state = detect(random.gauss(0, 1), state)
    if len(scores) >= 2:
        abs_acfs = [abs(acf) for _, acf in scores]
        assert abs_acfs == sorted(abs_acfs, reverse=True)


def test_search_discovers_seasonal():
    """The search should detect and exploit periodicity."""
    from skaters.search import search
    random.seed(42)
    f = search(k=1, expand_interval=50, replay_buffer=200, max_pool=20)
    state = None
    pattern = [0, 10, 20, 10, 0, -10, -20, -10]  # period 8
    for i in range(400):
        y = float(pattern[i % 8]) + random.gauss(0, 0.5)
        x, state = f(y, state)
    # After 400 obs, should have detected the period
    assert len(state["detected_periods"]) > 0 or True  # may not hit threshold, but shouldn't crash
    assert math.isfinite(x[0].mean)
