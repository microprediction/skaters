"""The missing-observation contract: a non-finite tick carries no information.

Before this rule, a single NaN was unrecoverable. At k=1 laplace returned
mean=nan, std=0.0 and stayed there through any amount of clean data (an EWMA
fed NaN is poisoned permanently, since mu + alpha*(nan - mu) = nan). At k>1 it
tripped a bare ``assert w_total > 0`` deep inside ``Dist``. Which failure you
got depended on the horizon.

The rule: time advanced, information did not. The tree never sees the value,
the base state is not advanced, and the fan is shifted so the forecast ages by
one horizon. The JS twin and the Rust port are held to the same behavior
through the gap scenario in parity/gen_vectors.py.
"""
import math

import pytest

from skaters.api import laplace

NAN = float("nan")
CLEAN = [1.0, 2.0, 1.5, 3.0, 2.0] * 12


def _run(f, ys, state=None):
    dists = None
    for y in ys:
        dists, state = f(y, state)
    return dists, state


@pytest.mark.parametrize("k", [1, 2, 3, 8])
def test_missing_tick_leaves_the_forecast_usable(k):
    f = laplace(k)
    dists, state = _run(f, CLEAN)
    dists, state = f(NAN, state)
    assert len(dists) == k
    for h, d in enumerate(dists, 1):
        assert math.isfinite(d.mean), f"k={k} h={h}: mean not finite after a gap"
        assert d.std > 0.0 and math.isfinite(d.std), f"k={k} h={h}: std={d.std}"
        assert math.isfinite(d.logpdf(2.0))
    assert state["skipped"] == 1


@pytest.mark.parametrize("bad", [NAN, float("inf"), float("-inf")])
def test_state_is_not_poisoned_and_clean_data_still_moves_it(bad):
    """The decisive property: the model must be as good after a gap as before,
    and must keep learning. Previously mean went nan and never came back."""
    f = laplace(1)
    before, state = _run(f, CLEAN)
    after_gap, state = f(bad, state)
    assert after_gap[0].mean == pytest.approx(before[0].mean)
    assert after_gap[0].std == pytest.approx(before[0].std)
    recovered, state = _run(f, [2.0] * 10, state)
    assert math.isfinite(recovered[0].mean)
    assert recovered[0].std > 0.0
    assert state["skipped"] == 1


def test_gap_run_ages_the_fan_then_holds_the_longest_horizon():
    """Each gap shifts horizon h+1 into h. After k gaps the h=k predictive is
    held, so the forecast stops changing rather than degenerating."""
    k = 4
    f = laplace(k)
    pre, state = _run(f, CLEAN)
    pre_fan = [(d.mean, d.std) for d in pre]
    seq = []
    for _ in range(k + 3):
        dists, state = f(NAN, state)
        seq.append((dists[0].mean, dists[0].std))
    # Gap g puts the pre-gap horizon g+1 at h=1, until h=k runs out.
    assert seq[0] == pytest.approx(pre_fan[1]), "first gap: h=1 becomes pre-gap h=2"
    assert seq[1] == pytest.approx(pre_fan[2]), "second gap: h=1 becomes pre-gap h=3"
    assert seq[2] == pytest.approx(pre_fan[3]), "third gap: h=1 becomes pre-gap h=4"
    for later in seq[3:]:
        assert later == pytest.approx(pre_fan[k - 1]), (
            f"past k-1 gaps the longest horizon should be held, got {later}")
    for m, s in seq:
        assert math.isfinite(m) and s > 0.0


def test_leading_gap_is_ignored_and_next_value_initializes_normally():
    """A gap before any observation has no forecast to age and no scale
    information, so it emits a deliberately wide predictive and leaves the tree
    untouched: the first finite value must behave exactly like a first call."""
    fresh, _ = laplace(2)(5.0, None)
    f = laplace(2)
    wide, state = f(NAN, None)
    assert wide[0].mean == 0.0
    assert wide[0].std >= 1e5, "a leading gap must not imply a confident scale"
    assert state["skipped"] == 1
    after, _ = f(5.0, state)
    assert after[0].mean == pytest.approx(fresh[0].mean)
    assert after[0].std == pytest.approx(fresh[0].std)


def test_pit_and_z_report_no_resolution_for_a_missing_tick():
    """The calibration diagnostics must not invent a residual for a value that
    was never observed; anomaly detection reads these."""
    f = laplace(3)
    _, state = _run(f, CLEAN)
    _, state = f(NAN, state)
    assert state["pit"] == [None, None, None]
    assert state["z"] == [None, None, None]


def test_all_missing_stream_never_crashes():
    f = laplace(3)
    state = None
    for _ in range(50):
        dists, state = f(NAN, state)
    assert state["skipped"] == 50
    assert all(d.std > 0.0 for d in dists)
