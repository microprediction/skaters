"""Pin the ``standardize`` emission contract, which shipped broken until #169.

``standardize`` must emit against the PRIOR variance. Dividing by the
post-update EWMA std makes the emission self-normalized: with
var_new = (1-a) var + a d^2, the emitted z = d / sqrt(var_new) is bounded by
1/sqrt(alpha) for ANY input, so a million-sigma move is indistinguishable from
a five-sigma one and the affine inverse is not the forward map's inverse. The
bound is ~4.47 at the default alpha=0.05.

The fix landed in Python only; the JS twin and the Rust port kept the capped
version for six days (CI red from 1f70895 to fc475d6) because the parity suite
compares against vectors regenerated from Python and nobody read the failure.
These assertions are cheap and language-independent in spirit -- the ports are
held to them through parity/gen_vectors.py.
"""
import math

from skaters.transform import standardize


def test_standardize_emits_beyond_the_self_normalized_bound():
    alpha = 0.05
    forward, _ = standardize(alpha)
    bound = 1.0 / math.sqrt(alpha)          # 4.4721: the old code's hard ceiling
    z, _ = forward(1000.0, {"mu": 0.0, "var": 1.0})
    assert z == 1000.0, f"a 1000-sigma move must emit z=1000, got {z}"
    assert z > bound


def test_standardize_forward_matches_the_inverse_it_is_paired_with():
    """inverse_k must undo forward: the sigma it applies has to be the one the
    next forward call divides by, which is only true for the prior state."""
    forward, inverse_k = standardize(0.05)
    state = {"mu": 0.3, "var": 4.0}
    y = 7.5
    z, _ = forward(y, dict(state))
    from skaters.dist import Dist
    back = inverse_k([Dist.gaussian(z, 1e-9)], state)[0].mean
    assert abs(back - y) < 1e-6, f"inverse did not recover y: {back} vs {y}"


def test_standardize_cold_start_first_informative_emission_is_unit():
    """With var still uninformative, scale by the first nonzero residual so the
    emission is +-1 rather than diff/eps (which was ~1e8 and swamped the leaf)."""
    forward, _ = standardize(0.05)
    z, state = forward(5.0, {"mu": 3.0, "var": 0.0})
    assert z == 1.0, f"first informative emission must be +1, got {z}"
    z2, _ = forward(1.0, {"mu": 3.0, "var": 0.0})
    assert z2 == -1.0, f"downward first emission must be -1, got {z2}"
