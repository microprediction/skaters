"""Integration tests: composability, edge cases, and end-to-end scenarios.

These test that the pieces work together correctly, not just in isolation.
"""

import math
import random
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize
from skaters.envelope import envelope
from skaters.calibrated import calibrated_envelope
from skaters.spec import (
    build, name, to_json, from_json,
    ema_spec, ensemble_spec, conjugate_spec, envelope_spec, calibrated_spec,
    diff_spec, frac_spec, std_spec,
)
from skaters.conventions import Skater


# ---------------------------------------------------------------------------
# Transform chaining
# ---------------------------------------------------------------------------

class TestTransformChains:

    def test_double_difference(self):
        """diff|diff|ema should work (second-order differencing)."""
        k = 1
        f = conjugate(conjugate(ema(alpha=0.1, k=k), difference(), k=k), difference(), k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0])

    def test_std_then_diff(self):
        """std|diff|ema — standardize, then difference the z-scores."""
        k = 1
        inner = conjugate(ema(alpha=0.1, k=k), difference(), k=k)
        f = conjugate(inner, standardize(), k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(100, 10), state)
        assert math.isfinite(x[0])
        assert abs(x[0] - 100) < 50  # should be in original scale

    def test_diff_then_frac(self):
        """diff|frac|ema — fractional diff the differences."""
        k = 1
        inner = conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.3), k=k)
        f = conjugate(inner, difference(), k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0])

    def test_triple_chain(self):
        """std|diff|frac|ema — three transforms deep."""
        k = 1
        f = ema(alpha=0.1, k=k)
        f = conjugate(f, fractional_difference(d=0.2, window=20), k=k)
        f = conjugate(f, difference(), k=k)
        f = conjugate(f, standardize(alpha=0.02), k=k)
        state = None
        random.seed(42)
        for _ in range(300):
            x, state = f(random.gauss(50, 5), state)
        assert math.isfinite(x[0])

    def test_chain_multistep(self):
        """Chained transforms with k=5."""
        k = 5
        f = conjugate(
            conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            standardize(), k=k,
        )
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 1), state)
        assert len(x) == k
        assert all(math.isfinite(v) for v in x)


# ---------------------------------------------------------------------------
# Ensemble of conjugated models
# ---------------------------------------------------------------------------

class TestEnsembleOfConjugates:

    def test_mixed_transforms_ensemble(self):
        """Ensemble where each model uses a different transform."""
        k = 1
        f = precision_weighted_ensemble([
            ema(alpha=0.1, k=k),
            conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.3), k=k),
            conjugate(ema(alpha=0.1, k=k), standardize(), k=k),
        ], k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0])
        assert isinstance(f, Skater)

    def test_ensemble_of_chains(self):
        """Ensemble of multiply-conjugated models."""
        k = 1
        f = precision_weighted_ensemble([
            conjugate(conjugate(ema(alpha=0.1, k=k), difference(), k=k), standardize(), k=k),
            conjugate(ema(alpha=0.2, k=k), difference(), k=k),
            ema(alpha=0.3, k=k),
        ], k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0])

    def test_nested_ensembles(self):
        """Ensemble of ensembles."""
        k = 1
        inner1 = precision_weighted_ensemble(
            [ema(alpha=0.05, k=k), ema(alpha=0.2, k=k)], k=k
        )
        inner2 = precision_weighted_ensemble(
            [conjugate(ema(alpha=0.1, k=k), difference(), k=k),
             conjugate(ema(alpha=0.3, k=k), difference(), k=k)], k=k
        )
        outer = precision_weighted_ensemble([inner1, inner2], k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = outer(random.gauss(0, 1), state)
        assert math.isfinite(x[0])


# ---------------------------------------------------------------------------
# Envelope and calibration on composed models
# ---------------------------------------------------------------------------

class TestEnvelopeOnCompositions:

    def test_envelope_on_conjugate(self):
        k = 2
        inner = conjugate(ema(alpha=0.1, k=k), difference(), k=k)
        f = envelope(inner, k=k)
        state = None
        random.seed(42)
        for _ in range(100):
            out, state = f(random.gauss(0, 1), state)
        assert all(math.isfinite(s) for s in out["std"])

    def test_envelope_on_ensemble_of_conjugates(self):
        k = 1
        inner = precision_weighted_ensemble([
            conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            ema(alpha=0.2, k=k),
        ], k=k)
        f = envelope(inner, k=k, decay=0.95)
        state = None
        random.seed(42)
        for _ in range(100):
            out, state = f(random.gauss(0, 1), state)
        assert math.isfinite(out["std"][0])

    def test_calibrated_on_chain(self):
        k = 1
        inner = conjugate(
            conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            standardize(), k=k,
        )
        f = calibrated_envelope(inner, k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            out, state = f(random.gauss(0, 1), state)
        assert math.isfinite(out["std"][0])

    def test_calibrated_coverage_on_mixed_ensemble(self):
        """Calibrated envelope on a meta-ensemble should have reasonable coverage."""
        random.seed(123)
        k = 1
        inner = precision_weighted_ensemble([
            ema(alpha=0.1, k=k),
            conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            conjugate(ema(alpha=0.2, k=k), fractional_difference(d=0.3), k=k),
        ], k=k)
        f = calibrated_envelope(inner, k=k)
        state = None
        preds, stds = [], []
        for i in range(1000):
            y = random.gauss(0, 1)
            out, state = f(y, state)
            if preds:
                preds.append((preds_last, stds_last, y))
            preds_last = out["mean"][0]
            stds_last = out["std"][0]
        # Check coverage over last 500
        hits = 0
        total = 0
        for pred, std, actual in preds[-500:]:
            if math.isfinite(std) and std > 0:
                total += 1
                if abs(actual - pred) <= std:
                    hits += 1
        if total > 100:
            coverage = hits / total
            assert 0.4 < coverage < 0.95, f"coverage={coverage:.2%}"


# ---------------------------------------------------------------------------
# Spec roundtrips for composed models
# ---------------------------------------------------------------------------

class TestSpecCompositions:

    def test_chain_spec_roundtrip(self):
        s = conjugate_spec(
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            std_spec(0.05),
        )
        j = to_json(s)
        s2 = from_json(j)
        assert s == s2
        f = build(s2)
        state = None
        for _ in range(50):
            x, state = f(1.0, state)
        assert math.isfinite(x[0])

    def test_meta_ensemble_spec(self):
        s = ensemble_spec(
            ema_spec(0.1, k=1),
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            conjugate_spec(ema_spec(0.1, k=1), frac_spec(0.3)),
            conjugate_spec(ema_spec(0.1, k=1), std_spec(0.05)),
            k=1,
        )
        n = name(s)
        assert "ensemble(" in n
        assert "diff|" in n
        assert "frac(" in n
        assert "std(" in n
        f = build(s)
        state = None
        random.seed(42)
        for _ in range(100):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0])

    def test_calibrated_chain_spec(self):
        s = calibrated_spec(
            conjugate_spec(
                conjugate_spec(ema_spec(0.1, k=3), diff_spec()),
                std_spec(0.02),
            ),
            k=3,
        )
        n = name(s)
        assert n == "calibrated[std(0.02)|diff|ema(0.1)]"
        f = build(s)
        state = None
        random.seed(42)
        for _ in range(100):
            out, state = f(random.gauss(0, 1), state)
        assert len(out["mean"]) == 3

    def test_deeply_nested_spec(self):
        """calibrated[ensemble(diff|ema, frac|ensemble(ema,ema), std|diff|ema)]"""
        s = calibrated_spec(
            ensemble_spec(
                conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
                conjugate_spec(
                    ensemble_spec(ema_spec(0.05, k=1), ema_spec(0.2, k=1), k=1),
                    frac_spec(0.3),
                ),
                conjugate_spec(
                    conjugate_spec(ema_spec(0.15, k=1), diff_spec()),
                    std_spec(0.05),
                ),
                k=1,
            ),
            k=1,
        )
        j = to_json(s)
        s2 = from_json(j)
        assert s == s2
        f = build(s2)
        state = None
        random.seed(42)
        for _ in range(200):
            out, state = f(random.gauss(0, 1), state)
        assert math.isfinite(out["std"][0])

    def test_two_builds_from_same_spec_are_independent(self):
        """Two skaters built from the same spec should not share state."""
        s = conjugate_spec(ema_spec(0.1, k=1), diff_spec())
        f1 = build(s)
        f2 = build(s)
        s1 = s2 = None
        # Feed different data
        random.seed(42)
        for _ in range(50):
            _, s1 = f1(random.gauss(0, 1), s1)
        random.seed(99)
        for _ in range(50):
            x2, s2 = f2(random.gauss(100, 1), s2)
        # f2 should be near 100, not near 0
        assert x2[0] > 50


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_zero_series(self):
        """All zeros should not crash anything."""
        k = 1
        for factory in [
            lambda: ema(alpha=0.1, k=k),
            lambda: conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            lambda: conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.3), k=k),
            lambda: conjugate(ema(alpha=0.1, k=k), standardize(), k=k),
            lambda: precision_weighted_ensemble([ema(alpha=0.1, k=k), ema(alpha=0.3, k=k)], k=k),
        ]:
            f = factory()
            state = None
            for _ in range(100):
                x, state = f(0.0, state)
            assert all(math.isfinite(v) for v in x)

    def test_large_values(self):
        """Very large values should not cause overflow."""
        k = 1
        f = conjugate(ema(alpha=0.1, k=k), difference(), k=k)
        state = None
        for _ in range(100):
            x, state = f(1e15, state)
        assert all(math.isfinite(v) for v in x)

    def test_tiny_values(self):
        """Very small values should not cause underflow issues."""
        k = 1
        f = conjugate(ema(alpha=0.1, k=k), standardize(), k=k)
        state = None
        for _ in range(100):
            x, state = f(1e-15, state)
        assert all(math.isfinite(v) for v in x)

    def test_alternating_extreme_values(self):
        k = 1
        f = envelope(
            conjugate(ema(alpha=0.3, k=k), difference(), k=k), k=k
        )
        state = None
        for i in range(200):
            y = 1000.0 if i % 2 == 0 else -1000.0
            out, state = f(y, state)
        assert math.isfinite(out["mean"][0])
        assert math.isfinite(out["std"][0])

    def test_single_observation(self):
        """Everything should handle a single observation without crashing."""
        k = 1
        for factory in [
            lambda: ema(alpha=0.1, k=k),
            lambda: conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            lambda: envelope(ema(alpha=0.1, k=k), k=k),
            lambda: calibrated_envelope(ema(alpha=0.1, k=k), k=k),
        ]:
            f = factory()
            out, state = f(42.0, None)
            # Should not crash

    def test_k_equals_1(self):
        f = build(calibrated_spec(
            ensemble_spec(
                conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
                ema_spec(0.3, k=1),
                k=1,
            ), k=1,
        ))
        state = None
        random.seed(42)
        for _ in range(50):
            out, state = f(random.gauss(0, 1), state)
        assert len(out["mean"]) == 1

    def test_large_k(self):
        k = 20
        f = conjugate(ema(alpha=0.1, k=k), difference(), k=k)
        state = None
        random.seed(42)
        for _ in range(100):
            x, state = f(random.gauss(0, 1), state)
        assert len(x) == 20
        assert all(math.isfinite(v) for v in x)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_same_seed_same_results(self):
        """Same input sequence should produce identical output."""
        s = ensemble_spec(
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            ema_spec(0.3, k=1),
            k=1,
        )
        results = []
        for _ in range(2):
            f = build(s)
            state = None
            random.seed(42)
            for _ in range(100):
                x, state = f(random.gauss(0, 1), state)
            results.append(x[0])
        assert results[0] == results[1]

    def test_spec_name_stable_across_builds(self):
        s = calibrated_spec(
            ensemble_spec(
                conjugate_spec(ema_spec(0.1, k=2), diff_spec()),
                conjugate_spec(ema_spec(0.05, k=2), frac_spec(0.3)),
                k=2,
            ), k=2,
        )
        f = build(s)
        assert f.__name__ == name(s)
        # Build again
        f2 = build(from_json(to_json(s)))
        assert f2.__name__ == f.__name__
