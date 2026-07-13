"""Cross-backend parity for the opt-in skaters_fast (PyO3) backend.

Runs the same series through the pure Python laplace(1) and the accelerated
skaters_fast.laplace(1), and asserts:

  1. Cross-backend agreement: |logpdf difference| <= 1e-6 at 50 probe points.
  2. Within-backend bit-exact resume: state_json round-trips through
     from_state_json with no drift, and a resumed instance reproduces the
     original's predictions bit-for-bit on the continued stream.

Skipped when skaters_fast is not importable (the backend is optional; build it
with `maturin develop --release -m rust/python/Cargo.toml`).
"""
import math
import random

import pytest

from skaters import laplace as py_laplace

skaters_fast = pytest.importorskip("skaters_fast")

N = 600
BURN = 20
N_PROBES = 50
TOL = 1e-6


def make_series(n=N, seed=98765):
    rng = random.Random(seed)
    series = []
    lvl = 0.0
    for t in range(n):
        lvl += rng.gauss(0, 0.3)
        val = lvl + 2.0 * math.sin(2 * math.pi * t / 7) + rng.gauss(0, 1.0)
        series.append(val)
    return series


def test_cross_backend_logpdf_parity():
    series = make_series()

    # Probe steps: 50 evenly spaced indices after burn-in.
    span = N - BURN
    probe_steps = {BURN + (i * span) // N_PROBES for i in range(N_PROBES)}

    py_skater = py_laplace(1)
    py_state = None
    fast = skaters_fast.laplace(1)

    max_diff = 0.0
    n_checked = 0
    for t, y in enumerate(series):
        py_dists, py_state = py_skater(y, py_state)
        fast_dists = fast.step(y)
        if t in probe_steps:
            py_d = py_dists[0]
            fast_d = fast_dists[0]
            # Probe logpdf at the realized point and one point in each tail.
            for x in (y, py_d.mean + 2.0 * py_d.std, py_d.mean - 2.0 * py_d.std):
                a = py_d.logpdf(x)
                b = fast_d.logpdf(x)
                assert math.isfinite(a) and math.isfinite(b)
                diff = abs(a - b)
                max_diff = max(max_diff, diff)
                n_checked += 1
                assert diff <= TOL, (
                    f"logpdf mismatch at step {t}, x={x}: "
                    f"py={a!r} fast={b!r} diff={diff:.3e}"
                )

    assert n_checked >= N_PROBES
    print(f"cross-backend logpdf: {n_checked} probes, max |diff| = {max_diff:.3e}")


def test_within_backend_bit_exact_resume():
    series = make_series()
    split = N // 2

    original = skaters_fast.laplace(1)
    for y in series[:split]:
        original.step(y)

    # Checkpoint and resume.
    s = original.state_json()
    resumed = skaters_fast.Laplace.from_state_json(s, 1)
    assert resumed.state_json() == s, "state_json is not stable across resume"

    # Continue both on the identical tail; predictions must match bit-for-bit.
    for y in series[split:]:
        od = original.step(y)[0]
        rd = resumed.step(y)[0]
        # Bit-exact: identical floats, not merely within a tolerance.
        assert od.logpdf(y) == rd.logpdf(y)
        assert od.cdf(y) == rd.cdf(y)
        assert od.mean == rd.mean
        assert od.std == rd.std

    assert original.state_json() == resumed.state_json()
