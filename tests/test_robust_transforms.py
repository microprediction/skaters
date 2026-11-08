"""Contract tests for the robust MAD transform and the variance-ratio lens.

The lens is a diagnostic. The MAD standardizer is a conjugate transform:
per-stream state, k horizons, and an affine map back to the original units.
"""

import json
import math
import random
import statistics
from fractions import Fraction

from skaters.conjugate import conjugate
from skaters.dist import Dist
from skaters.leaf import leaf
from skaters.residual_variance_lens import _population_var, residual_variance_lens
from skaters.robust_mad_standardize import robust_mad_standardize
from skaters.transform import standardize

_EPS = 1e-12


def _alternating(value: float, n: int) -> list[float]:
    return [value if i % 2 == 0 else -value for i in range(n)]


def _feed(update, values, state=None):
    outputs = []
    for value in values:
        feature, state = update(value, state)
        outputs.append(feature)
    return outputs, state


# --- residual variance lens: diagnostic, frozen reference -------------------

def test_lens_is_silent_until_the_reference_freezes():
    update = residual_variance_lens(burn_in=6, window=4)
    outputs, state = _feed(update, _alternating(1.0, 5))
    assert outputs == [0.0] * 5
    assert state["ref_var"] is None
    feature, state = update(-1.0, state)
    assert feature == 0.0
    assert state["ref_var"] == 1.0 + _EPS


def test_lens_freezes_the_reference_and_reports_the_variance_ratio():
    update = residual_variance_lens(burn_in=20, window=20)
    _, state = _feed(update, _alternating(1.0, 20))
    frozen = state["ref_var"]
    outputs, state = _feed(update, _alternating(3.0, 20), state)
    assert state["ref_var"] == frozen
    assert abs(outputs[-1] - math.log((9.0 + _EPS) / frozen)) < 1e-12


def test_lens_loses_sign():
    update = residual_variance_lens(burn_in=4, window=4)
    series = _alternating(1.0, 4) + [2.0, 3.0, -1.0, 2.5]
    positive, _ = _feed(update, series)
    negative, _ = _feed(update, [-x for x in series])
    assert positive == negative
    assert positive[-1] != 0.0


def test_lens_window_is_the_trailing_residuals_including_burn_in():
    """Peter's example: the last four residuals are [-1, 1, 1, 1], variance 0.75."""
    update = residual_variance_lens(burn_in=4, window=4)
    outputs, state = _feed(update, [-1.0, 1.0, -1.0, 1.0, 1.0, 1.0])
    assert state["recent"] == [-1.0, 1.0, 1.0, 1.0]
    expected = math.log(0.75 + _EPS) - math.log(1.0 + _EPS)
    assert abs(outputs[-1] - expected) < 1e-12
    assert abs(outputs[-1] - (-0.287682)) < 1e-6


def test_lens_is_not_ready_until_the_window_is_full():
    update = residual_variance_lens(burn_in=4, window=8)
    state = None
    for i, value in enumerate(_alternating(1.0, 7)):
        feature, state = update(value, state)
        assert feature == 0.0 and state["ready"] is False, i
    feature, state = update(float("nan"), state)
    assert feature == 0.0 and state["ready"] is False
    feature, state = update(3.0, state)
    assert state["ready"] is True
    expected = math.log(_population_var_of(_alternating(1.0, 7) + [3.0]) + _EPS)
    assert abs(feature - (expected - math.log(1.0 + _EPS))) < 1e-12


def _population_var_of(values):
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def test_lens_streams_keep_separate_state():
    update = residual_variance_lens(burn_in=8, window=4)
    _, quiet = _feed(update, _alternating(1.0, 8))
    _, loud = _feed(update, _alternating(4.0, 8))
    assert quiet["ref_var"] != loud["ref_var"]
    snapshot = json.dumps(quiet)
    update(100.0, quiet)
    assert json.dumps(quiet) == snapshot


def test_lens_state_roundtrips_through_json():
    update = residual_variance_lens(burn_in=10, window=6)
    rng = random.Random(2)
    series = [rng.gauss(0.0, 1.0) for _ in range(40)]
    _, state = _feed(update, series[:20])
    restored = json.loads(json.dumps(state))
    for value in series[20:]:
        a, state = update(value, state)
        b, restored = update(value, restored)
        assert a == b


def test_lens_log_ratio_stays_finite_for_a_flat_reference():
    """A flat reference makes the variance quotient overflow before log."""
    update = residual_variance_lens(burn_in=2, window=2)
    outputs, _ = _feed(update, (0.0, 0.0, 1e150, -1e150))
    assert outputs[:2] == [0.0, 0.0]
    assert all(math.isfinite(x) for x in outputs)
    assert abs(outputs[3] - 718.4065490141422) < 1e-9


def test_lens_constant_large_stream_has_no_variance():
    """sum/n of a constant 1e12 rounds off the value; that must not read as variance."""
    update = residual_variance_lens(burn_in=60, window=4)
    outputs, state = _feed(update, [1_000_000_000_000.04] * 64)
    assert outputs == [0.0] * 64
    assert state["ref_var"] == _EPS


def test_lens_variance_is_exact_when_the_first_sample_is_an_outlier():
    """The variance is centred on values[0]; an outlier there must not cost precision."""
    rng = random.Random(3)
    for _ in range(300):
        base = rng.choice([0.0, 1e6, 1e12])
        values = [base + rng.gauss(0.0, 1.0) for _ in range(rng.choice([4, 60, 250]))]
        values[0] = base + rng.choice([-1.0, 1.0]) * 10 ** rng.uniform(2.0, 8.0)
        exact = float(statistics.pvariance([Fraction(v) for v in values]))
        assert abs(_population_var(values) - exact) <= 1e-12 * exact


def test_lens_ignores_non_finite_and_overflowing_residuals():
    update = residual_variance_lens(burn_in=4, window=4)
    outputs, state = _feed(update, _alternating(1.0, 8))
    settled = outputs[-1]
    for bad in (float("nan"), float("inf"), 1e200):
        feature, state = update(bad, state)
        assert feature == settled
    assert state["ref_var"] == 1.0 + _EPS
    outputs, _ = _feed(update, _alternating(1.0, 4), state)
    assert math.isfinite(outputs[-1])
    assert abs(outputs[-1] - settled) < 1e-12


# --- robust MAD: conjugate transform ----------------------------------------

def test_conjugate_matches_the_affine_inverse_at_k1_and_k3():
    series = [0.2 * i + ((-1) ** i) * 0.5 for i in range(40)]
    for k in (1, 3):
        forward, inverse = robust_mad_standardize(window=15, min_periods=5)
        manual = leaf(k=k)
        wrapped = conjugate(leaf(k=k), robust_mad_standardize(window=15, min_periods=5), k=k)
        t_state = s_state = c_state = None
        for y in series:
            y_prime, t_state = forward(y, t_state)
            dists_prime, s_state = manual(y_prime, s_state)
            by_hand = inverse(dists_prime, t_state)
            via_conjugate, c_state = wrapped(y, c_state)
            assert len(via_conjugate) == k
            unit = inverse([Dist.gaussian(0.0, 1.0)], t_state)[0]
            for horizon, inner, outer in zip(by_hand, dists_prime, via_conjugate):
                assert abs(outer.mean - horizon.mean) < 1e-9
                assert abs(outer.std - horizon.std) < 1e-9
                assert abs(outer.mean - (unit.mean + inner.mean * unit.std)) < 1e-9
                assert abs(outer.std - inner.std * unit.std) < 1e-9


def test_inverse_scales_each_horizon():
    forward, inverse = robust_mad_standardize(window=11, min_periods=5)
    state = None
    for y in range(11):
        _, state = forward(float(y), state)
    out = inverse([Dist.gaussian(0.0, 1.0), Dist.gaussian(1.0, 2.0)], state)
    assert len(out) == 2
    assert abs(out[1].mean - (out[0].mean + out[0].std)) < 1e-9
    assert abs(out[1].std - 2.0 * out[0].std) < 1e-9


def test_streams_keep_separate_windows():
    forward, _ = robust_mad_standardize(window=10, min_periods=4)
    flat = varied = None
    for i in range(12):
        _, flat = forward(0.0, flat)
        _, varied = forward(float(i), varied)
    assert flat["buf"][-1] == 0.0
    assert varied["buf"][-1] == 11.0
    snapshot = list(flat["buf"])
    forward(5.0, flat)
    assert flat["buf"] == snapshot


def test_flat_stretch_then_level_shift_enters_within_one_window():
    window = 11
    forward, inverse = robust_mad_standardize(window=window, min_periods=5)
    state = None
    for _ in range(40):
        _, state = forward(0.0, state)
    for _ in range(window):
        _, state = forward(1000.0, state)
    assert state["buf"] == [1000.0] * window
    located = inverse([Dist.gaussian(0.0, 1.0)], state)[0]
    assert located.mean == 1000.0
    y_prime, state = forward(1000.0, state)
    assert y_prime == 0.0


def test_wrapped_forecast_recovers_after_a_flat_stretch():
    """The leaf must not keep a residual created by dividing by the floor.

    The window median does recover on its own. This checks the forecast the
    conjugated skater actually returns once that window has moved.
    """
    series = [0.0] * 40 + [1000.0] * 11 + [998.0, 999.0, 1000.0, 1001.0, 1002.0] * 40
    f = conjugate(leaf(), robust_mad_standardize(window=11, min_periods=5))
    state = None
    dists = None
    for y in series:
        dists, state = f(y, state)
    assert abs(dists[0].mean - 1000.0) < 1.0
    assert 0.05 < dists[0].std < 20.0


def test_warmup_forecast_scale_tracks_the_observed_spread():
    series = [0.0, 10.0, -10.0, 10.0, -10.0, 10.0, -10.0]
    f = conjugate(leaf(), robust_mad_standardize())
    state = None
    dists = None
    for y in series:
        dists, state = f(y, state)
    assert dists[0].std > 0.1


def test_gaussian_mad_scale_is_within_a_few_percent():
    """After burn-in, the stored MAD scale tracks a known Gaussian sigma."""
    sigma = 3.0
    window = 120
    forward, _ = robust_mad_standardize(window=window, min_periods=30)
    rng = random.Random(0)
    state = None
    late = []
    for i in range(2500):
        _, state = forward(rng.gauss(0.0, sigma), state)
        if i >= 1700:
            late.append(state["scale"])
    estimate = sum(late) / len(late)
    assert abs(estimate - sigma) / sigma < 0.05


def test_conjugate_state_roundtrips_through_json():
    rng = random.Random(1)
    series = [rng.gauss(0.0, 1.0) for _ in range(80)]
    f = conjugate(leaf(), robust_mad_standardize(window=30, min_periods=8))
    state = None
    for y in series[:50]:
        _, state = f(y, state)
    restored = json.loads(json.dumps(state))
    for y in series[50:]:
        original, state = f(y, state)
        copy, restored = f(y, restored)
        assert original[0].mean == copy[0].mean
        assert original[0].std == copy[0].std
        assert json.dumps(state) == json.dumps(restored)


def _mean_log_score(maker, series, burn):
    f = maker()
    state = None
    pending = None
    total = 0.0
    count = 0
    for i, y in enumerate(series):
        if pending is not None and i >= burn:
            total += pending.logpdf(y)
            count += 1
        dists, state = f(y, state)
        pending = dists[0]
    return total / count


def test_robust_mad_beats_standardize_on_a_heavy_tailed_stream():
    """5% of the points are N(0, 30); the rest are N(0, 1).

    A synthetic stream. On the FRED daily and M4 hourly corpora the robust
    arm does not beat standardize at the median series; see
    benchmarks/canonical_summary_vs_laplace_pr307_vs_leaf+standardize.csv.
    """
    rng = random.Random(7)
    series = [rng.gauss(0.0, 30.0) if rng.random() < 0.05 else rng.gauss(0.0, 1.0)
              for _ in range(2000)]
    robust = _mean_log_score(
        lambda: conjugate(leaf(), robust_mad_standardize(window=60, min_periods=20)),
        series, 400)
    plain = _mean_log_score(
        lambda: conjugate(leaf(), standardize(0.05)),
        series, 400)
    assert robust > plain


def test_non_finite_observation_does_not_poison_the_window():
    forward, inverse = robust_mad_standardize(window=10, min_periods=4)
    state = None
    for y in (1.0, 2.0, 3.0, 4.0):
        _, state = forward(y, state)
    _, after = forward(float("nan"), state)
    assert after["buf"] == [1.0, 2.0, 3.0, 4.0]
    _, after = forward(float("inf"), after)
    mapped = inverse([Dist.gaussian(0.0, 1.0)], after)[0]
    assert math.isfinite(mapped.mean) and math.isfinite(mapped.std)
