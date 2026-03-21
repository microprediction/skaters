"""Tests for symbolic spec: naming, serialization, and build roundtrips."""

import json
import math
import random
from skaters.spec import (
    build, name, to_json, from_json,
    ema_spec, ensemble_spec, conjugate_spec, envelope_spec, calibrated_spec,
    diff_spec, frac_spec, std_spec,
)
from skaters.conventions import Skater


# --- Naming ---

class TestNaming:

    def test_ema_name(self):
        assert name(ema_spec(0.1, k=1)) == "ema(0.1)"

    def test_ema_integer_alpha(self):
        # alpha=0.0 is invalid for ema, but naming should still work
        s = {"op": "ema", "alpha": 1.0, "k": 1}
        # would fail to build, but name is fine
        assert name(s) == "ema(1)"

    def test_diff_conjugate_name(self):
        s = conjugate_spec(ema_spec(0.1, k=1), diff_spec())
        assert name(s) == "diff|ema(0.1)"

    def test_frac_conjugate_name(self):
        s = conjugate_spec(ema_spec(0.1, k=1), frac_spec(0.3))
        assert name(s) == "frac(0.3)|ema(0.1)"

    def test_frac_custom_window_name(self):
        s = conjugate_spec(ema_spec(0.1, k=1), frac_spec(0.3, window=20))
        assert name(s) == "frac(0.3,w=20)|ema(0.1)"

    def test_frac_default_window_omitted(self):
        s = conjugate_spec(ema_spec(0.1, k=1), frac_spec(0.3, window=50))
        assert "w=" not in name(s)

    def test_std_conjugate_name(self):
        s = conjugate_spec(ema_spec(0.1, k=1), std_spec(0.05))
        assert name(s) == "std(0.05)|ema(0.1)"

    def test_chain_name(self):
        inner = conjugate_spec(ema_spec(0.1, k=1), diff_spec())
        outer = conjugate_spec(inner, std_spec(0.05))
        assert name(outer) == "std(0.05)|diff|ema(0.1)"

    def test_ensemble_name(self):
        s = ensemble_spec(ema_spec(0.01, k=1), ema_spec(0.1, k=1), k=1)
        assert name(s) == "ensemble(ema(0.01),ema(0.1))"

    def test_ensemble_with_conjugates_name(self):
        s = ensemble_spec(
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            ema_spec(0.3, k=1),
            k=1,
        )
        assert name(s) == "ensemble(diff|ema(0.1),ema(0.3))"

    def test_envelope_name(self):
        s = envelope_spec(ema_spec(0.1, k=1), k=1)
        assert name(s) == "envelope[ema(0.1)]"

    def test_envelope_with_decay_name(self):
        s = envelope_spec(ema_spec(0.1, k=1), k=1, decay=0.95)
        assert name(s) == "envelope[ema(0.1),decay=0.95]"

    def test_calibrated_name(self):
        s = calibrated_spec(ema_spec(0.1, k=1), k=1)
        assert name(s) == "calibrated[ema(0.1)]"

    def test_calibrated_custom_target_name(self):
        s = calibrated_spec(ema_spec(0.1, k=1), k=1, target=0.95)
        assert name(s) == "calibrated[ema(0.1),target=0.95]"

    def test_calibrated_default_target_omitted(self):
        s = calibrated_spec(ema_spec(0.1, k=1), k=1, target=0.6827)
        assert "target=" not in name(s)

    def test_name_is_deterministic(self):
        s = ensemble_spec(
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            conjugate_spec(ema_spec(0.05, k=1), frac_spec(0.3)),
            k=1,
        )
        assert name(s) == name(s)


# --- Serialization ---

class TestSerialization:

    def test_json_roundtrip_ema(self):
        s = ema_spec(0.1, k=3)
        assert from_json(to_json(s)) == s

    def test_json_roundtrip_ensemble(self):
        s = ensemble_spec(ema_spec(0.01, k=1), ema_spec(0.1, k=1), k=1)
        assert from_json(to_json(s)) == s

    def test_json_roundtrip_conjugate(self):
        s = conjugate_spec(ema_spec(0.1, k=2), diff_spec())
        assert from_json(to_json(s)) == s

    def test_json_roundtrip_chain(self):
        s = conjugate_spec(
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            std_spec(0.05),
        )
        assert from_json(to_json(s)) == s

    def test_json_roundtrip_calibrated(self):
        s = calibrated_spec(
            ensemble_spec(ema_spec(0.1, k=1), ema_spec(0.3, k=1), k=1),
            k=1, target=0.95,
        )
        assert from_json(to_json(s)) == s

    def test_json_is_valid_json(self):
        s = ensemble_spec(
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            ema_spec(0.3, k=1),
            k=1,
        )
        j = to_json(s)
        json.loads(j)  # should not raise


# --- Build ---

class TestBuild:

    def test_build_ema(self):
        f = build(ema_spec(0.1, k=1))
        x, state = f(1.0, None)
        assert isinstance(x, list)
        assert len(x) == 1

    def test_build_ensemble(self):
        s = ensemble_spec(ema_spec(0.01, k=2), ema_spec(0.1, k=2), k=2)
        f = build(s)
        x, _ = f(1.0, None)
        assert len(x) == 2

    def test_build_conjugate_diff(self):
        s = conjugate_spec(ema_spec(0.1, k=1), diff_spec())
        f = build(s)
        state = None
        for y in [1.0, 2.0, 3.0, 4.0, 5.0]:
            x, state = f(y, state)
        assert math.isfinite(x[0])

    def test_build_conjugate_frac(self):
        s = conjugate_spec(ema_spec(0.1, k=1), frac_spec(0.3))
        f = build(s)
        state = None
        random.seed(42)
        for _ in range(100):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0])

    def test_build_chain(self):
        s = conjugate_spec(
            conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
            std_spec(0.05),
        )
        f = build(s)
        state = None
        random.seed(42)
        for _ in range(100):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0])

    def test_build_envelope(self):
        s = envelope_spec(ema_spec(0.1, k=1), k=1, decay=0.95)
        f = build(s)
        state = None
        random.seed(42)
        for _ in range(50):
            out, state = f(random.gauss(0, 1), state)
        assert "mean" in out
        assert "std" in out

    def test_build_calibrated(self):
        s = calibrated_spec(ema_spec(0.1, k=1), k=1)
        f = build(s)
        state = None
        random.seed(42)
        for _ in range(50):
            out, state = f(random.gauss(0, 1), state)
        assert "mean" in out
        assert "std" in out

    def test_build_satisfies_protocol(self):
        s = conjugate_spec(ema_spec(0.1, k=1), diff_spec())
        f = build(s)
        assert isinstance(f, Skater)

    def test_build_name_matches_spec_name(self):
        s = conjugate_spec(
            ensemble_spec(ema_spec(0.01, k=1), ema_spec(0.1, k=1), k=1),
            diff_spec(),
        )
        f = build(s)
        assert f.__name__ == name(s)


# --- Full roundtrip: spec -> JSON -> spec -> build -> run ---

class TestFullRoundtrip:

    def test_ema_roundtrip(self):
        s = ema_spec(0.2, k=3)
        f = build(from_json(to_json(s)))
        state = None
        for _ in range(20):
            x, state = f(1.0, state)
        assert len(x) == 3

    def test_complex_roundtrip(self):
        """Build a complex spec, serialize, deserialize, build, run."""
        s = calibrated_spec(
            ensemble_spec(
                conjugate_spec(ema_spec(0.1, k=2), diff_spec()),
                conjugate_spec(ema_spec(0.05, k=2), frac_spec(0.3)),
                ema_spec(0.2, k=2),
                k=2,
            ),
            k=2,
        )
        j = to_json(s)
        s2 = from_json(j)
        assert s == s2
        assert name(s) == name(s2)

        f = build(s2)
        state = None
        random.seed(42)
        for _ in range(100):
            out, state = f(random.gauss(0, 1), state)
        assert "mean" in out
        assert len(out["mean"]) == 2
        assert all(math.isfinite(v) for v in out["mean"])
