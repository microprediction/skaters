"""Contract tests for the robust MAD transform and the variance-ratio lens.

The lens is a diagnostic. The MAD standardizer is a conjugate transform:
per-stream state, k horizons, and an affine map back to the original units.
"""

import json
import math
import random

from skaters.conjugate import conjugate
from skaters.dist import Dist
from skaters.leaf import leaf
from skaters.residual_variance_lens import ResidualVarianceLens
from skaters.robust_mad_standardize import robust_mad_standardize
from skaters.transform import standardize


def _alternating(value: float, n: int) -> list[float]:
    return [value if i % 2 == 0 else -value for i in range(n)]


# --- residual variance lens: diagnostic, frozen reference -------------------

def test_lens_is_silent_until_the_reference_freezes():
    lens = ResidualVarianceLens(burn_in=6, window=4)
    for value in _alternating(1.0, 5):
        assert lens.update(value) == 0.0
        assert lens.ref_var is None
    assert lens.update(-1.0) == 0.0
    assert lens.ref_var == 1.0 + lens.eps


def test_lens_freezes_the_reference_and_reports_the_variance_ratio():
    lens = ResidualVarianceLens(burn_in=20, window=20)
    for value in _alternating(1.0, 20):
        lens.update(value)
    frozen = lens.ref_var
    for value in _alternating(3.0, 20):
        feature = lens.update(value)
    assert lens.ref_var == frozen
    assert abs(feature - math.log((9.0 + lens.eps) / frozen)) < 1e-12


def test_lens_loses_sign_and_has_no_inverse():
    positive = ResidualVarianceLens(burn_in=4, window=4)
    negative = ResidualVarianceLens(burn_in=4, window=4)
    for value in _alternating(1.0, 4):
        positive.update(value)
        negative.update(value)
    last_pos = last_neg = None
    for value in _alternating(2.0, 4):
        last_pos = positive.update(value)
        last_neg = negative.update(-value)
    assert last_pos == last_neg
    assert not hasattr(positive, "inverse")


def test_lens_streams_do_not_share_a_reference():
    quiet = ResidualVarianceLens(burn_in=8, window=4)
    loud = ResidualVarianceLens(burn_in=8, window=4)
    for value in _alternating(1.0, 8):
        quiet.update(value)
    for value in _alternating(4.0, 8):
        loud.update(value)
    assert quiet.ref_var != loud.ref_var


def test_lens_log_ratio_stays_finite_for_a_flat_reference():
    """A flat reference makes the variance quotient overflow before log."""
    lens = ResidualVarianceLens(burn_in=2, window=2)
    values = [lens.update(x) for x in (0.0, 0.0, 1e150, -1e150)]
    assert values[:3] == [0.0, 0.0, 0.0]
    assert math.isfinite(values[3])
    assert abs(values[3] - 718.4065490141422) < 1e-9


def test_lens_ignores_non_finite_and_overflowing_residuals():
    lens = ResidualVarianceLens(burn_in=4, window=4)
    for value in _alternating(1.0, 4):
        lens.update(value)
    for value in _alternating(1.0, 4):
        settled = lens.update(value)
    assert lens.update(float("nan")) == settled
    assert lens.update(float("inf")) == settled
    assert lens.update(1e200) == settled
    assert lens.ref_var == 1.0 + lens.eps
    again = None
    for value in _alternating(1.0, 4):
        again = lens.update(value)
    assert math.isfinite(again)
    assert abs(again - settled) < 1e-12


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

    The same pair is registered as leaf+robust-mad and leaf+standardize for
    benchmarks/run_arm.py. This is the stream where the robust arm wins.
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
