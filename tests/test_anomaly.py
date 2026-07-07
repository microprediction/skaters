"""Tests for the streaming Mahalanobis anomaly detector."""

import math
import random
import pytest
from skaters import laplace
from skaters.anomaly import mahalanobis, chi2_sf, chi2_ppf

SCATTERS = ("factor", "shrink")


# --- chi-square math ---

def test_chi2_sf_known_values():
    # sf(x, 2) = exp(-x/2) exactly
    for x in (0.5, 1.0, 3.0, 10.0):
        assert abs(chi2_sf(x, 2) - math.exp(-0.5 * x)) < 1e-10
    # sf(1, 1) = 2 * (1 - Phi(1))
    phi1 = 0.5 * (1.0 + math.erf(1.0 / math.sqrt(2.0)))
    assert abs(chi2_sf(1.0, 1) - 2.0 * (1.0 - phi1)) < 1e-10
    assert chi2_sf(0.0, 5) == 1.0
    assert chi2_sf(1e9, 3) < 1e-12


def test_chi2_ppf_roundtrip():
    for dof in (1, 2, 3, 8):
        for p in (0.5, 0.9, 0.99, 0.999):
            x = chi2_ppf(p, dof)
            assert abs((1.0 - chi2_sf(x, dof)) - p) < 1e-8


# --- detector behaviour ---

def _run(f, ys):
    state = None
    out = []
    for y in ys:
        _, state = f(y, state)
        out.append((state["d2"], state["pvalue"], state["run"]))
    return out, state


def test_pass_through_and_warmup():
    k = 3
    f = mahalanobis(laplace(k), k=k)
    state = None
    d, state = f(0.1, state)
    assert len(d) == k                       # forecasts pass through
    assert state["d2"] is None               # nothing matured yet
    for y in (0.2, 0.15, 0.3, 0.25):
        d, state = f(y, state)
    assert state["d2"] is not None and math.isfinite(state["d2"])
    assert 0.0 <= state["pvalue"] <= 1.0


@pytest.mark.parametrize('scatter', SCATTERS)
def test_calibrated_null(scatter):
    """On a well-specified stream the p-values are roughly Uniform(0,1) —
    the empirical null absorbs the cross-horizon correlation of z (near
    rank-1 on smooth streams), so this is the calibration claim, not the raw
    d2 scale."""
    random.seed(5)
    k = 3
    f = mahalanobis(laplace(k), k=k, scatter=scatter)
    out, _ = _run(f, [random.gauss(0, 1) for _ in range(900)])
    ps = [p for d2, p, _ in out[200:] if d2 is not None]
    n = len(ps)
    assert n > 600
    frac_10 = sum(1 for p in ps if p < 0.1) / n
    frac_50 = sum(1 for p in ps if p < 0.5) / n
    assert 0.02 < frac_10 < 0.30
    assert 0.30 < frac_50 < 0.70
    assert 0.30 < sum(ps) / n < 0.70          # mean ~ 1/2


@pytest.mark.parametrize('scatter', SCATTERS)
def test_point_outlier_fires_once(scatter):
    """An isolated outlier must yield a tiny p-value and read as a spike
    (small run), with the detector recovering afterwards."""
    random.seed(11)
    k = 3
    f = mahalanobis(laplace(k), k=k, scatter=scatter)
    state = None
    for _ in range(300):
        _, state = f(random.gauss(0, 0.1), state)
    _, state = f(30.0, state)                # a screaming outlier
    assert state["pvalue"] < 1e-6
    assert state["run"] >= 1
    # recovery: within a couple dozen quiet ticks the p-values normalise
    ps = []
    for _ in range(40):
        _, state = f(random.gauss(0, 0.1), state)
        ps.append(state["pvalue"])
    assert max(ps[-10:]) > 0.01


def test_level_shift_reads_as_run_and_readapts():
    """A persistent level shift produces a multi-tick run (vs an isolated
    spike) and the system — base forecaster included — re-adapts, with
    p-values recovering. The run length scales with the forecaster's
    adaptation time, not the shift's duration: laplace absorbs the new level
    within a few ticks."""
    random.seed(2)
    k = 2
    f = mahalanobis(laplace(k), k=k, adapt_after=3)
    state = None
    for _ in range(300):
        _, state = f(random.gauss(0, 0.1), state)
    max_run = 0
    ps_late = []
    for i in range(120):
        _, state = f(8.0 + random.gauss(0, 0.1), state)   # shifted regime
        max_run = max(max_run, state["run"])
        if i >= 80:
            ps_late.append(state["pvalue"])
    assert max_run >= 3                       # a run, not an isolated spike
    assert max(ps_late) > 0.01                # ...then re-adapted


@pytest.mark.parametrize('scatter', SCATTERS)
def test_masking_resistance(scatter):
    """Repeated outliers must not inflate the scatter enough to hide later
    ones: the last injected outlier still fires as hard as the first."""
    random.seed(7)
    k = 2
    f = mahalanobis(laplace(k), k=k, scatter=scatter)
    state = None
    pvals = []
    t = 0
    for _ in range(600):
        y = 12.0 if (t % 40 == 39 and t > 100) else random.gauss(0, 0.1)
        _, state = f(y, state)
        if t % 40 == 39 and t > 100:
            pvals.append(state["pvalue"])
        t += 1
    assert len(pvals) >= 10
    assert all(p < 1e-3 for p in pvals)       # every outlier still fires


def _scripted_z(z_seq, k):
    """A mock parade-wrapped skater emitting a scripted z-vector each tick."""
    from skaters.dist import Dist
    def f(y, state):
        t = 0 if state is None else state["t"] + 1
        return [Dist.gaussian(0.0, 1.0)] * k, {"t": t, "z": list(z_seq[t])}
    return f


def test_factor_scatter_detects_disagreement_anomalies():
    """The z-vector is near rank-1 ('all horizons surprised together'); the
    diagnostic directions are the small ones ('the forecasts disagreed').
    Identity shrinkage floors those variances and suppresses exactly that
    signal; the factor model keeps their estimated scale. An anomaly pattern
    orthogonal to the common factor, with every |z| component modest, must
    fire under the factor scatter — and this is precisely where it should
    dominate the shrink scatter."""
    random.seed(3)
    k = 3
    n = 900
    zs = []
    for t in range(n):
        g = random.gauss(0, 1)                        # common factor
        zs.append([g + random.gauss(0, 0.05) for _ in range(k)])
    anomaly_at = 700
    # Disagreement pattern: +-0.6, orthogonal-ish to (1,1,1); every |z| < 1,
    # so no per-horizon rule (and no common-mode detector) can see it.
    zs[anomaly_at] = [0.6, -0.6, 0.0]

    pv = {}
    for scatter in SCATTERS:
        f = mahalanobis(_scripted_z(zs, k), k=k, scatter=scatter)
        state = None
        for t in range(n):
            _, state = f(0.0, state)
            if t == anomaly_at:
                pv[scatter] = state["pvalue"]

    assert pv["factor"] < 1e-4                 # screams under the factor model
    assert pv["factor"] < pv["shrink"] * 1e-2  # and beats shrinkage by orders


def test_k1_and_constant_stream_no_crash():
    f = mahalanobis(laplace(1), k=1)
    state = None
    for y in [3.3] * 60 + [9.9, 3.3, 3.3]:
        _, state = f(y, state)
        if state["d2"] is not None:
            assert math.isfinite(state["d2"])
            assert 0.0 <= state["pvalue"] <= 1.0
