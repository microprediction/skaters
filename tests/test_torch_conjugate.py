"""End-to-end parity of torch conjugation chains against the reference:
the same leaf under the same stacked transforms, compared per step and per
horizon at 1e-9, and gradients through two stacked learnable transforms."""
import math

import pytest

torch = pytest.importorskip("torch")

import skaters.transform as rt                                  # noqa: E402
from skaters.conjugate import conjugate as ref_conjugate        # noqa: E402
from skaters.leaf import leaf                                   # noqa: E402
from skaters.torch import from_reference                        # noqa: E402
from skaters.torch.conjugate import conjugate, reference_skater  # noqa: E402
from skaters.torch.parity import random_series                  # noqa: E402

TOL = 1e-9


def _run_pair(ref_f, tor_f, series, k):
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for y in series:
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            assert len(d1) == len(d2) == k
            for a, b in zip(d1, d2):
                bc = b.to_reference().components
                assert len(a.components) == len(bc)
                for (w1, m1, v1), (w2, m2, v2) in zip(a.components, bc):
                    worst = max(worst, abs(w1 - w2), abs(m1 - m2), abs(v1 - v2))
    return worst


@pytest.mark.parametrize("k", [1, 3])
def test_difference_over_ema_over_leaf(k):
    """laplace's depth-2 candidate: conjugate(conjugate(leaf, ema(0.1)), difference())."""
    series = random_series(250, seed=3)
    ref_f = ref_conjugate(ref_conjugate(leaf(k=k), rt.ema_transform(0.1), k=k), rt.difference(), k=k)
    tor_f = conjugate(conjugate(reference_skater(leaf(k=k)), from_reference("ema_transform", alpha=0.1), k=k),
                      from_reference("difference"), k=k)
    assert _run_pair(ref_f, tor_f, series, k) < TOL


@pytest.mark.parametrize("k", [1, 3])
def test_standardize_over_ema_over_leaf(k):
    series = random_series(250, seed=4)
    ref_f = ref_conjugate(ref_conjugate(leaf(k=k), rt.ema_transform(0.05), k=k), rt.standardize(), k=k)
    tor_f = conjugate(conjugate(reference_skater(leaf(k=k)), from_reference("ema_transform", alpha=0.05), k=k),
                      from_reference("standardize"), k=k)
    assert _run_pair(ref_f, tor_f, series, k) < TOL


@pytest.mark.parametrize("k", [1, 3])
def test_frac_over_ema_over_leaf(k):
    """laplace's depth-2 candidate: fractional_difference(0.4, 30) over ema(0.1)."""
    series = random_series(250, seed=6)
    ref_f = ref_conjugate(ref_conjugate(leaf(k=k), rt.ema_transform(0.1), k=k),
                          rt.fractional_difference(d=0.4, window=30), k=k)
    tor_f = conjugate(conjugate(reference_skater(leaf(k=k)), from_reference("ema_transform", alpha=0.1), k=k),
                      from_reference("fractional_difference", d=0.4, window=30), k=k)
    assert _run_pair(ref_f, tor_f, series, k) < TOL


@pytest.mark.parametrize("k", [1, 3])
def test_power_over_ema_over_leaf(k):
    """laplace's depth-2 candidate: power_transform(0.5) over ema(0.1), positive series."""
    series = random_series(250, seed=7, kind="positive")
    ref_f = ref_conjugate(ref_conjugate(leaf(k=k), rt.ema_transform(0.1), k=k), rt.power_transform(0.5), k=k)
    tor_f = conjugate(conjugate(reference_skater(leaf(k=k)), from_reference("ema_transform", alpha=0.1), k=k),
                      from_reference("power_transform", p=0.5), k=k)
    assert _run_pair(ref_f, tor_f, series, k) < TOL


def test_gradients_through_two_stacked_transforms():
    k = 2
    series = random_series(120, seed=5)
    ema = from_reference("ema_transform", alpha=0.1)
    std = from_reference("standardize", alpha=0.05)
    f = conjugate(conjugate(reference_skater(leaf(k=k)), ema, k=k), std, k=k)
    state = None
    loss = torch.zeros((), dtype=torch.float64)
    for t, y in enumerate(series[:-k]):
        dists, state = f(y, state)
        if t >= 5:
            for h, d in enumerate(dists, start=1):
                loss = loss - d.logpdf(series[t + h])
    loss.backward()
    for name, p in list(ema.named_parameters()) + list(std.named_parameters()):
        assert p.grad is not None and math.isfinite(float(p.grad)), (name, p.grad)
    assert float(ema.alpha.grad) != 0.0
