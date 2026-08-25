"""quantile must invert cdf at every scale and for uneven mixtures.

The README contract is `quantile  # inverse CDF`. Two regimes broke it:

1. Tiny scales: the bisection's ABSOLUTE tolerance (1e-9) exceeds the whole
   initial bracket when the mixture std is small, so the loop stops after
   one halving — the median of N(0, 1e-11) resolved to the ~0.003rd
   percentile.
2. Tiny-weight far components: the initial bracket is built from MIXTURE
   moments (mu +/- 8*sigma), so quantiles owned by a low-weight distant
   component lie outside the bracket and bisection returns the bracket
   edge: quantile(1-1e-6) of 0.9999*N(0,1) + 1e-4*N(1000,1) returned ~80
   (true 1002.3263).

A third regime appears once those two are addressed: with a narrow
component beside a hugely separated one, bisecting the whole span needs
~133 halvings against max_iter=100, so the search never reaches the
tolerance at all.

The fix localizes before bisecting: the component +/- 8 sigma endpoints
are sorted and binary-searched for a gap containing p, the stopping
tolerance is `tol` times the SMALLEST component sigma (x-space, never
probability-space, so parade's deep-tail z diagnostic survives), and the
result is `hi` — the tightest point known to satisfy cdf(x) >= p, which
is the quantile's definition and matters where float64 resolves a
component to a single representable point. These tests pin the contract,
including the float64 limit beyond which no algorithm can satisfy it.
"""
import math

from skaters.dist import Dist


def _roundtrip_err(d, p):
    return abs(d.cdf(d.quantile(p)) - p)


def test_quantile_inverts_cdf_at_tiny_scale():
    d = Dist([(1.0, 0.0, 1e-11)])
    assert _roundtrip_err(d, 0.5) < 1e-6
    assert _roundtrip_err(d, 0.99) < 1e-6
    assert _roundtrip_err(d, 0.01) < 1e-6
    # and the values themselves are right (Phi^-1(0.99) ~ 2.3263)
    assert abs(d.quantile(0.99) - 2.3263478740408408e-11) < 1e-13


def test_quantile_inverts_cdf_at_huge_scale():
    d = Dist([(1.0, 1e9, 1e7)])
    for p in (0.01, 0.5, 0.99):
        assert _roundtrip_err(d, p) < 1e-6


def test_quantile_reaches_tiny_weight_far_component():
    d = Dist([(0.9999, 0.0, 1.0), (1e-4, 1000.0, 1.0)])
    p = 1.0 - 1e-6
    q = d.quantile(p)
    assert q > 990.0, f"quantile stuck at bracket edge: {q}"
    assert _roundtrip_err(d, p) < 1e-5


def test_quantile_far_component_low_side():
    d = Dist([(1e-4, -1000.0, 1.0), (0.9999, 0.0, 1.0)])
    p = 1e-6
    q = d.quantile(p)
    assert q < -990.0, f"quantile stuck at bracket edge: {q}"
    assert _roundtrip_err(d, p) < 1e-5


def test_quantile_unit_scale_unchanged():
    # ordinary mixtures must keep inverting cdf tightly at unit scale
    d = Dist([(0.6, 0.0, 1.0), (0.4, 3.0, 2.0)])
    for p in (0.1, 0.5, 0.9):
        assert _roundtrip_err(d, p) < 1e-6


def test_quantile_monotone_across_levels_tiny_scale():
    d = Dist([(0.5, 0.0, 1e-11), (0.5, 5e-11, 2e-11)])
    ps = [0.001, 0.01, 0.1, 0.5, 0.9, 0.99, 0.999]
    qs = [d.quantile(p) for p in ps]
    assert all(b >= a for a, b in zip(qs, qs[1:])), qs
    for p, q in zip(ps, qs):
        assert abs(d.cdf(q) - p) < 1e-5


def test_quantile_mixed_scales_narrow_inside_wide():
    # reviewer counterexample: narrow component inside a wide mixture —
    # a mixture-scale-relative tolerance stalls before resolving it
    d = Dist([(0.5, 0.0, 1e-11), (0.5, 1000.0, 1.0)])
    q = d.quantile(0.25)
    assert _roundtrip_err(d, 0.25) < 1e-6, (q, d.cdf(q))
    assert abs(q) < 1e-9, f"p=0.25 lives at the narrow component median, got {q}"


def test_quantile_mixed_scales_dominant_narrow():
    d = Dist([(0.9999, 0.0, 1e-11), (1e-4, 1000.0, 1.0)])
    q = d.quantile(0.5)
    assert _roundtrip_err(d, 0.5) < 1e-6, (q, d.cdf(q))
    assert abs(q) < 1e-9


def test_quantile_mixed_scales_mirrored():
    d = Dist([(0.5, -1000.0, 1.0), (0.5, 0.0, 1e-11)])
    for p in (0.75, 0.9):
        assert _roundtrip_err(d, p) < 1e-6


def test_quantile_astronomical_separation_with_narrow_component():
    # A narrow component beside a hugely separated one: bisecting the GLOBAL
    # span needs ~133 halvings to reach the narrow scale, but max_iter is 100.
    # Localizing the bracket to the component endpoints that contain p keeps
    # the search inside a region the tolerance can actually resolve.
    for sep in (1e20, 1e40, 1e80):
        d = Dist([(0.5, 0.0, 1e-11), (0.5, sep, 1.0)])
        assert _roundtrip_err(d, 0.25) < 1e-6, (sep, d.quantile(0.25))
        assert _roundtrip_err(d, 0.75) < 1e-6, (sep, d.quantile(0.75))


def test_quantile_localization_costs_no_precision_at_unit_scale():
    # Localization must not change well-conditioned answers.
    d = Dist([(0.5, -2.0, 1.0), (0.5, 2.0, 1.0)])
    for p in (0.05, 0.25, 0.5, 0.75, 0.95):
        assert _roundtrip_err(d, p) < 1e-9


def test_quantile_representation_limit_is_documented_not_silent():
    # KNOWN LIMIT, not a defect: when ulp(mean) exceeds the component scale,
    # float64 has no representable point between the mean and mean +/- sigma,
    # so every quantile collapses to the mean. No algorithm can do better;
    # this test exists so the boundary is explicit rather than surprising.
    d = Dist([(1.0, 8.386e41, 3.853e6)])
    assert math.ulp(8.386e41) > 8.0 * 3.853e6
    assert d.quantile(0.25) == d.quantile(0.75) == 8.386e41
