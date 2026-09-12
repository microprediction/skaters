"""Dist input validation and quantile bracketing (issue #200).

Before these checks, Dist accepted objects that are not probability
distributions (negative weights gave pdf(10) = -0.399 while logpdf ignored
the negative component), combine() zip-dropped members on length mismatch,
and quantile() bisected a fixed mu +- 8 sigma bracket, converging silently
to the endpoint whenever the true quantile lay outside it.
"""
import math

import pytest

from skaters.dist import Dist


# --- constructor -----------------------------------------------------------

def test_negative_weight_rejected():
    with pytest.raises(ValueError):
        Dist([(2.0, 0.0, 1.0), (-1.0, 10.0, 1.0)])


def test_negative_std_rejected():
    with pytest.raises(ValueError):
        Dist([(1.0, 0.0, -1.0)])


def test_nonfinite_params_rejected():
    for bad in [(math.nan, 0.0, 1.0), (1.0, math.inf, 1.0), (1.0, 0.0, math.nan)]:
        with pytest.raises(ValueError):
            Dist([bad])


def test_empty_rejected():
    with pytest.raises(ValueError):
        Dist([])


def test_zero_total_weight_rejected():
    with pytest.raises(ValueError):
        Dist([(0.0, 0.0, 1.0), (0.0, 1.0, 1.0)])


def test_zero_weight_component_allowed():
    # leaves can softmax-underflow a weight to exactly 0
    d = Dist([(0.0, 0.0, 1.0), (1.0, 1.0, 1.0)])
    assert abs(d.mean - 1.0) < 1e-12


def test_point_mass_allowed():
    # the lattice projection emits Dirac components
    d = Dist([(0.5, 0.0, 1.0), (0.5, 2.0, 0.0)])
    assert math.isfinite(d.mean)


def test_pdf_matches_logpdf_on_valid_dist():
    d = Dist([(0.6, 0.0, 1.0), (0.4, 3.0, 0.5)])
    for x in (-2.0, 0.0, 1.5, 3.0, 10.0):
        assert d.pdf(x) == pytest.approx(math.exp(d.logpdf(x)), rel=1e-12)


# --- combine ---------------------------------------------------------------

def test_combine_length_mismatch_rejected():
    ds = [Dist.gaussian(0.0), Dist.gaussian(1.0), Dist.gaussian(2.0)]
    with pytest.raises(ValueError):
        Dist.combine(ds, weights=[0.5, 0.5])


def test_combine_empty_rejected():
    with pytest.raises(ValueError):
        Dist.combine([])


def test_combine_zero_weights_rejected():
    ds = [Dist.gaussian(0.0), Dist.gaussian(1.0)]
    with pytest.raises(ValueError):
        Dist.combine(ds, weights=[0.0, 0.0])


def test_combine_unchanged_for_valid_input():
    ds = [Dist.gaussian(0.0, 1.0), Dist.gaussian(4.0, 2.0)]
    d = Dist.combine(ds, weights=[0.25, 0.75])
    assert d.mean == pytest.approx(3.0)


# --- quantile --------------------------------------------------------------

def test_quantile_p_out_of_range_rejected():
    d = Dist.gaussian()
    for p in (0.0, 1.0, -0.1, 1.1):
        with pytest.raises(ValueError):
            d.quantile(p)


def test_quantile_far_component_bracket_expands():
    # weight 0.001 at 1e6: the 0.9995 quantile is near 1e6, far outside
    # mu +- 8 sigma (~2.5e5). The fixed bracket returned ~253856 here.
    d = Dist([(0.999, 0.0, 1.0), (0.001, 1e6, 1.0)])
    q = d.quantile(0.9995)
    assert q > 9.9e5
    assert d.cdf(q) == pytest.approx(0.9995, abs=1e-6)


def test_quantile_far_component_lower_tail():
    d = Dist([(0.001, -1e6, 1.0), (0.999, 0.0, 1.0)])
    q = d.quantile(0.0005)
    assert q < -9.9e5
    assert d.cdf(q) == pytest.approx(0.0005, abs=1e-6)


def test_quantile_ordinary_cases_unchanged():
    # the expansion must not fire when the default bracket suffices
    d = Dist([(0.5, 0.0, 1.0), (0.5, 2.0, 3.0)])
    for p in (0.01, 0.25, 0.5, 0.75, 0.99):
        q = d.quantile(p)
        assert d.cdf(q) == pytest.approx(p, abs=1e-7)
