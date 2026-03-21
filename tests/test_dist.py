"""Tests for the Gaussian mixture distributional type."""

import math
import random
from skaters.dist import Dist


# --- Construction ---

class TestConstruction:

    def test_single_gaussian(self):
        d = Dist.gaussian(0.0, 1.0)
        assert len(d) == 1
        assert d.components[0] == (1.0, 0.0, 1.0)

    def test_weights_normalized(self):
        d = Dist([(3.0, 0.0, 1.0), (7.0, 1.0, 1.0)])
        w_total = sum(w for w, _, _ in d.components)
        assert abs(w_total - 1.0) < 1e-12

    def test_mixture(self):
        d = Dist([(0.5, -1.0, 0.5), (0.5, 1.0, 0.5)])
        assert len(d) == 2


# --- PDF ---

class TestPdf:

    def test_standard_normal_at_zero(self):
        d = Dist.gaussian(0.0, 1.0)
        expected = 1.0 / math.sqrt(2.0 * math.pi)
        assert abs(d.pdf(0.0) - expected) < 1e-10

    def test_pdf_positive(self):
        d = Dist.gaussian(5.0, 2.0)
        assert d.pdf(5.0) > 0
        assert d.pdf(8.0) > 0  # 1.5σ away, clearly positive
        # Note: pdf(100.0) underflows to 0.0 in float64 (47.5σ away) — correct

    def test_pdf_symmetric(self):
        d = Dist.gaussian(0.0, 1.0)
        assert abs(d.pdf(1.0) - d.pdf(-1.0)) < 1e-12

    def test_mixture_pdf_is_weighted_sum(self):
        d1 = Dist.gaussian(0.0, 1.0)
        d2 = Dist.gaussian(5.0, 1.0)
        mix = Dist.combine([d1, d2])
        x = 2.5
        expected = 0.5 * d1.pdf(x) + 0.5 * d2.pdf(x)
        assert abs(mix.pdf(x) - expected) < 1e-12

    def test_pdf_integrates_to_one(self):
        """Crude numerical check that pdf integrates to ~1."""
        d = Dist([(0.3, -2.0, 0.5), (0.7, 3.0, 1.5)])
        dx = 0.01
        total = sum(d.pdf(x * dx) * dx for x in range(-1000, 1000))
        assert abs(total - 1.0) < 0.01


# --- CDF ---

class TestCdf:

    def test_standard_normal_at_zero(self):
        d = Dist.gaussian(0.0, 1.0)
        assert abs(d.cdf(0.0) - 0.5) < 1e-10

    def test_cdf_monotone(self):
        d = Dist([(0.5, -1.0, 0.5), (0.5, 1.0, 0.5)])
        xs = [-5.0, -1.0, 0.0, 1.0, 5.0]
        cdfs = [d.cdf(x) for x in xs]
        for i in range(len(cdfs) - 1):
            assert cdfs[i] <= cdfs[i + 1]

    def test_cdf_limits(self):
        d = Dist.gaussian(0.0, 1.0)
        assert d.cdf(-10.0) < 1e-10
        assert d.cdf(10.0) > 1.0 - 1e-10

    def test_cdf_at_known_quantiles(self):
        """Standard normal: CDF(1.96) ≈ 0.975."""
        d = Dist.gaussian(0.0, 1.0)
        assert abs(d.cdf(1.96) - 0.975) < 0.001

    def test_mixture_cdf_is_weighted_sum(self):
        d1 = Dist.gaussian(0.0, 1.0)
        d2 = Dist.gaussian(5.0, 1.0)
        mix = Dist.combine([d1, d2], [0.3, 0.7])
        x = 2.0
        expected = 0.3 * d1.cdf(x) + 0.7 * d2.cdf(x)
        assert abs(mix.cdf(x) - expected) < 1e-12


# --- Log PDF ---

class TestLogPdf:

    def test_logpdf_equals_log_pdf(self):
        d = Dist.gaussian(0.0, 1.0)
        for x in [-2.0, 0.0, 1.5]:
            assert abs(d.logpdf(x) - math.log(d.pdf(x))) < 1e-12

    def test_logpdf_at_zero_standard_normal(self):
        d = Dist.gaussian(0.0, 1.0)
        expected = -0.5 * math.log(2.0 * math.pi)
        assert abs(d.logpdf(0.0) - expected) < 1e-10

    def test_logpdf_far_tail(self):
        d = Dist.gaussian(0.0, 1.0)
        assert d.logpdf(100.0) < -1000


# --- Quantile ---

class TestQuantile:

    def test_median_of_symmetric(self):
        d = Dist.gaussian(5.0, 2.0)
        assert abs(d.quantile(0.5) - 5.0) < 1e-6

    def test_known_quantiles_standard_normal(self):
        d = Dist.gaussian(0.0, 1.0)
        assert abs(d.quantile(0.025) - (-1.96)) < 0.01
        assert abs(d.quantile(0.975) - 1.96) < 0.01
        assert abs(d.quantile(0.5) - 0.0) < 1e-6

    def test_quantile_ordering(self):
        d = Dist([(0.5, -1.0, 1.0), (0.5, 3.0, 0.5)])
        qs = [d.quantile(p) for p in [0.1, 0.25, 0.5, 0.75, 0.9]]
        for i in range(len(qs) - 1):
            assert qs[i] < qs[i + 1]

    def test_quantile_inverts_cdf(self):
        d = Dist([(0.3, -2.0, 1.0), (0.7, 2.0, 0.5)])
        for p in [0.1, 0.5, 0.9]:
            x = d.quantile(p)
            assert abs(d.cdf(x) - p) < 1e-6


# --- Mean and Variance ---

class TestMoments:

    def test_gaussian_mean(self):
        d = Dist.gaussian(7.0, 3.0)
        assert abs(d.mean - 7.0) < 1e-12

    def test_gaussian_var(self):
        d = Dist.gaussian(7.0, 3.0)
        assert abs(d.var - 9.0) < 1e-10

    def test_gaussian_std(self):
        d = Dist.gaussian(7.0, 3.0)
        assert abs(d.std - 3.0) < 1e-10

    def test_mixture_mean(self):
        d = Dist([(0.5, 0.0, 1.0), (0.5, 10.0, 1.0)])
        assert abs(d.mean - 5.0) < 1e-12

    def test_mixture_var_law_of_total_variance(self):
        """Var = E[Var] + Var[E] = 0.5*(1+1) + 0.5*(0^2+10^2) - 5^2 = 1 + 25 = 26."""
        d = Dist([(0.5, 0.0, 1.0), (0.5, 10.0, 1.0)])
        expected = 1.0 + 25.0  # E[sigma^2] + Var[mu]
        assert abs(d.var - expected) < 1e-10


# --- Combine ---

class TestCombine:

    def test_equal_weight_default(self):
        d1 = Dist.gaussian(0.0, 1.0)
        d2 = Dist.gaussian(10.0, 1.0)
        mix = Dist.combine([d1, d2])
        assert len(mix) == 2
        assert abs(mix.components[0][0] - 0.5) < 1e-12
        assert abs(mix.components[1][0] - 0.5) < 1e-12

    def test_custom_weights(self):
        d1 = Dist.gaussian(0.0, 1.0)
        d2 = Dist.gaussian(10.0, 1.0)
        mix = Dist.combine([d1, d2], weights=[0.8, 0.2])
        assert abs(mix.components[0][0] - 0.8) < 1e-12
        assert abs(mix.components[1][0] - 0.2) < 1e-12

    def test_combine_preserves_total_components(self):
        d1 = Dist([(0.5, 0.0, 1.0), (0.5, 1.0, 1.0)])
        d2 = Dist([(0.5, 5.0, 1.0), (0.5, 6.0, 1.0)])
        mix = Dist.combine([d1, d2])
        assert len(mix) == 4

    def test_combine_many(self):
        dists = [Dist.gaussian(float(i), 1.0) for i in range(10)]
        mix = Dist.combine(dists)
        assert len(mix) == 10
        assert abs(mix.mean - 4.5) < 1e-10

    def test_combine_single(self):
        d = Dist.gaussian(5.0, 2.0)
        mix = Dist.combine([d])
        assert abs(mix.mean - 5.0) < 1e-12


# --- Transforms ---

class TestTransforms:

    def test_shift(self):
        d = Dist.gaussian(0.0, 1.0)
        shifted = d.shift(5.0)
        assert abs(shifted.mean - 5.0) < 1e-12
        assert abs(shifted.std - 1.0) < 1e-12

    def test_scale(self):
        d = Dist.gaussian(2.0, 1.0)
        scaled = d.scale(3.0)
        assert abs(scaled.mean - 6.0) < 1e-12
        assert abs(scaled.std - 3.0) < 1e-12

    def test_scale_negative(self):
        d = Dist.gaussian(2.0, 1.0)
        scaled = d.scale(-2.0)
        assert abs(scaled.mean - (-4.0)) < 1e-12
        assert abs(scaled.std - 2.0) < 1e-12

    def test_affine(self):
        d = Dist.gaussian(0.0, 1.0)
        transformed = d.affine(2.0, 3.0)
        assert abs(transformed.mean - 3.0) < 1e-12
        assert abs(transformed.std - 2.0) < 1e-12

    def test_shift_preserves_shape(self):
        d = Dist([(0.3, 0.0, 1.0), (0.7, 5.0, 2.0)])
        shifted = d.shift(10.0)
        assert abs(shifted.pdf(10.0) - d.pdf(0.0)) < 1e-12

    def test_transforms_on_mixture(self):
        d = Dist([(0.5, -1.0, 0.5), (0.5, 1.0, 0.5)])
        shifted = d.shift(10.0)
        assert abs(shifted.mean - 10.0) < 1e-12
        scaled = d.scale(3.0)
        assert abs(scaled.mean - 0.0) < 1e-12
        assert abs(scaled.std - d.std * 3.0) < 1e-10


# --- Pruning ---

class TestPruning:

    def test_prune_reduces_components(self):
        components = [(1.0, float(i), 1.0) for i in range(50)]
        d = Dist(components)
        assert len(d) == 50
        pruned = d.prune(max_components=5)
        assert len(pruned) == 5

    def test_prune_preserves_mean(self):
        random.seed(42)
        components = [(random.random(), random.gauss(0, 5), 1.0) for _ in range(30)]
        d = Dist(components)
        pruned = d.prune(max_components=5)
        assert abs(pruned.mean - d.mean) < 0.5

    def test_prune_noop_if_under_budget(self):
        d = Dist([(0.5, 0.0, 1.0), (0.5, 1.0, 1.0)])
        pruned = d.prune(max_components=10)
        assert len(pruned) == 2

    def test_prune_to_one(self):
        d = Dist([(0.5, 0.0, 1.0), (0.5, 10.0, 1.0)])
        pruned = d.prune(max_components=1)
        assert len(pruned) == 1
        assert abs(pruned.mean - 5.0) < 1e-10


# --- Serialization ---

class TestSerialization:

    def test_roundtrip(self):
        d = Dist([(0.3, -1.0, 0.5), (0.7, 2.0, 1.5)])
        d2 = Dist.from_dict(d.to_dict())
        assert d == d2

    def test_to_dict_structure(self):
        d = Dist.gaussian(0.0, 1.0)
        data = d.to_dict()
        assert "components" in data
        assert len(data["components"]) == 1


# --- Repr ---

class TestRepr:

    def test_single_component_repr(self):
        d = Dist.gaussian(5.0, 2.0)
        s = repr(d)
        assert "μ=" in s
        assert "σ=" in s

    def test_mixture_repr(self):
        d = Dist([(0.5, 0.0, 1.0), (0.5, 5.0, 1.0)])
        s = repr(d)
        assert "2 components" in s


# --- Log-likelihood on a sequence ---

class TestLogLikelihood:

    def test_loglike_series(self):
        """Log-likelihood of data generated from a known distribution."""
        random.seed(42)
        d_true = Dist.gaussian(0.0, 1.0)
        d_wrong = Dist.gaussian(10.0, 1.0)
        data = [random.gauss(0, 1) for _ in range(200)]

        ll_true = sum(d_true.logpdf(x) for x in data)
        ll_wrong = sum(d_wrong.logpdf(x) for x in data)
        assert ll_true > ll_wrong

    def test_loglike_mixture_vs_single(self):
        """Mixture that covers the data should have higher LL than wrong single Gaussian."""
        random.seed(42)
        # Data from bimodal: half from N(-5,1), half from N(5,1)
        data = [random.gauss(-5, 1) for _ in range(100)]
        data += [random.gauss(5, 1) for _ in range(100)]

        d_bimodal = Dist([(0.5, -5.0, 1.0), (0.5, 5.0, 1.0)])
        d_unimodal = Dist.gaussian(0.0, 5.0)  # covers both but poorly

        ll_bi = sum(d_bimodal.logpdf(x) for x in data)
        ll_uni = sum(d_unimodal.logpdf(x) for x in data)
        assert ll_bi > ll_uni
