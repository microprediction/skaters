"""Tier 3: known generating processes with exact conditional laws.

A chain that matches the generating process must, after burn-in, score within
a small, stated regret of the true conditional density, recover the generating
parameters, and have uniform PITs at every horizon tested. A wrong h-step
variance shows up here as non-vanishing regret and a non-uniform PIT even when
no one knows where the bug is.

Bounds are stated with their reasoning. Seeds are fixed. Default laplace is
held to looser bounds than the matching chain, because it must also pay for
model selection.
"""
import math
import pytest

from skaters.api import laplace
from skaters.conjugate import conjugate
from skaters.leaf import leaf, scale_mixture_leaf, garch_leaf
from skaters.transform import ar, holt_linear
import dgp


def _gauss_logpdf(x, m, v):
    return -0.5 * math.log(2 * math.pi * v) - 0.5 * (x - m) ** 2 / v


def _run_k(f, ys, k):
    """issued[t] = list of k Dists emitted after consuming ys[t]."""
    st, issued = None, []
    for y in ys:
        d, st = f(y, st)
        issued.append(d)
    return issued, st


# ------------------------------------------------------------ AR(1) chain
@pytest.mark.parametrize("seed", [1, 2])
def test_ar1_chain_regret_recovery_and_pit(seed):
    phi, sigma, k = [0.6], 1.0, 5
    y, _ = dgp.gaussian_ar(phi, sigma, n=2500, seed=seed)
    f = conjugate(leaf(k), ar(1), k)
    issued, st = _run_k(f, y, k)
    burn = 500
    # default ar() forgets with lam=0.99 (~100-point window): sd(phi_hat) ~ 0.065 over
    # 8 seeds, so 0.15 is ~2.3 sd. Exact recovery is tested with lam=1 below.
    assert abs(st["t_state"]["phi"][0] - 0.6) < 0.15, st["t_state"]["phi"]
    for h in (1, 5):
        reg, pit = [], []
        for t in range(burn, len(y) - h):
            d = issued[t][h - 1]
            m, v = dgp.ar_oracle(phi, sigma, y[:t + 1], h)
            reg.append(_gauss_logpdf(y[t + h], m, v) - d.logpdf(y[t + h]))
            pit.append(d.cdf(y[t + h]))
        mean_reg = sum(reg) / len(reg)
        # RLS(lam=0.99) ~ 100-point window: Var(phi_hat) ~ (1-phi^2)/100 -> ~0.005 nats
        # of regret at h=1; allow 6x headroom, more at h=5 where psi(phi_hat) compounds.
        assert mean_reg < (0.03 if h == 1 else 0.06), (h, mean_reg)
        # KS 5% critical value at n~2000 is 0.030; allow 0.05.
        assert dgp.ks_uniform(pit) < 0.05, (h, dgp.ks_uniform(pit))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ar1_rls_without_forgetting_recovers_phi(seed):
    y, _ = dgp.gaussian_ar([0.6], 1.0, n=2500, seed=seed)
    fwd, _ = ar(1, lam=1.0)
    st = None
    for v in y:
        _, st = fwd(v, st)
    # OLS sd at n=2500: sqrt((1-0.36)/2500) = 0.016; allow 3 sd.
    assert abs(st["phi"][0] - 0.6) < 0.05, st["phi"]


# ------------------------------------------------------------ Holt chain
def _holt_setup(seed=5):
    alpha, beta, sigma, k = 0.3, 0.2, 1.0, 5
    y, _, _ = dgp.holt_series(alpha, beta, sigma, n=2000, seed=seed)
    f = conjugate(leaf(k), holt_linear(alpha, beta), k)
    issued, _ = _run_k(f, y, k)
    return y, issued, alpha, beta, sigma


def _holt_pit_and_regret(y, issued, alpha, beta, sigma, h, burn=400):
    """Oracle: the chain's own point forecast (same alpha, beta as the DGP, so after
    the transient it is the DGP's conditional mean) with the ETS(A,A,N) variance."""
    var_h = dgp.ets_aan_var(alpha, alpha * beta, [sigma * sigma] * h)[h - 1]
    pit, reg = [], []
    for t in range(burn, len(y) - h):
        d = issued[t][h - 1]
        pit.append(d.cdf(y[t + h]))
        reg.append(_gauss_logpdf(y[t + h], d.mean, var_h) - d.logpdf(y[t + h]))
    return dgp.ks_uniform(pit), sum(reg) / len(reg)


def test_holt_chain_calibrated_at_h1():
    ks, reg = _holt_pit_and_regret(*_holt_setup(), h=1)
    assert ks < 0.05 and reg < 0.03, (ks, reg)


def test_holt_chain_calibrated_at_h5():
    ks, reg = _holt_pit_and_regret(*_holt_setup(), h=5)
    assert ks < 0.05 and reg < 0.03, (ks, reg)


# ------------------------------------------------------------ GARCH leaf
def _garch_setup(seed=7):
    om, al, be = 0.05, 0.08, 0.90
    r, h_next = dgp.garch11(om, al, be, n=3000, seed=seed)
    f = garch_leaf(1)
    issued, st = _run_k(f, r, 1)
    return r, h_next, issued, st, (om, al, be)


def _unit_scale(d):
    """sigma of the leaf: the mixture component with relative scale 1.0 is the
    median-scale component of the fixed basis (0.7, 1.0, 1.6, 3.0, 6.0)."""
    s = sorted(c[2] for c in d.components)
    return s[1]


def test_garch_leaf_recovers_alpha_beta():
    """Issue #244 (fixed). Before the fix the refit landed on the grid corner
    (0.20, 0.72) for truth (0.08, 0.90), because r_t entered its own h_t."""
    _, _, _, st, (om, al, be) = _garch_setup()
    # grid is 0.02-step in alpha near 0.08 and 0.04-step in beta near 0.90
    assert abs(st["alpha"] - al) <= 0.05 and abs(st["beta"] - be) <= 0.06, (st["alpha"], st["beta"])


def test_garch_leaf_on_iid_data_picks_smallest_alpha():
    """iid N(0,1) has no ARCH effect: a correct QMLE picks the smallest alpha on the
    grid. A criterion that lets r_t into h_t prefers large alpha even here."""
    y = dgp.iid(3000, seed=31)
    f = garch_leaf(1)
    st = None
    for v in y:
        _, st = f(v, st)
    assert st["alpha"] <= 0.04, (st["alpha"], st["beta"])


def _corr(a, b):
    n = len(a); ma = sum(a) / n; mb = sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def test_garch_leaf_variance_tracks_next_step_not_current():
    r, h_next, issued, _, _ = _garch_setup()
    burn = 1000
    emitted = [math.log(_unit_scale(issued[t][0]) ** 2) for t in range(burn, len(r) - 1)]
    nxt = [math.log(h_next[t]) for t in range(burn, len(r) - 1)]          # true Var(r_{t+1} | F_t)
    cur = [math.log(h_next[t - 1]) for t in range(burn, len(r) - 1)]      # true Var(r_t | F_{t-1})
    c_next, c_cur = _corr(emitted, nxt), _corr(emitted, cur)
    assert c_next > c_cur, (c_next, c_cur)


# ------------------------------------------------------------ known volatility path
def test_scale_mixture_leaf_tracks_known_sigma_path():
    levels = (1.0, 3.0, 0.5, 2.0)
    y, sd = dgp.sigma_path(n=1600, seed=9, levels=levels)
    f = scale_mixture_leaf(1, scale_alpha=0.1)
    issued, _ = _run_k(f, y, 1)
    seg = len(y) // len(levels)
    for i, lv in enumerate(levels):
        lo, hi = i * seg + 80, (i + 1) * seg - 1     # interior, after ~8 half-lives
        est = [_unit_scale(issued[t][0]) for t in range(lo, hi)]
        med = sorted(est)[len(est) // 2]
        assert abs(med / lv - 1.0) < 0.25, (i, lv, med)


# ------------------------------------------------------------ default laplace
def test_laplace_k1_on_iid_gaussian_is_calibrated():
    y = dgp.iid(1500, seed=21)
    issued, _ = _run_k(laplace(1), y, 1)
    burn = 300
    pit = [issued[t][0].cdf(y[t + 1]) for t in range(burn, len(y) - 1)]
    reg = [_gauss_logpdf(y[t + 1], 0.0, 1.0) - issued[t][0].logpdf(y[t + 1]) for t in range(burn, len(y) - 1)]
    # KS 5% critical at n=1200 is 0.039; model selection plus scale tracking earns 0.06.
    assert dgp.ks_uniform(pit) < 0.06, dgp.ks_uniform(pit)
    assert sum(reg) / len(reg) < 0.08, sum(reg) / len(reg)


def test_laplace_k5_on_random_walk_is_calibrated_at_h5():
    y = dgp.random_walk(1.0, n=1200, seed=22)
    issued, _ = _run_k(laplace(5), y, 5)
    burn, h = 300, 5
    pit = [issued[t][h - 1].cdf(y[t + h]) for t in range(burn, len(y) - h)]
    assert dgp.ks_uniform(pit) < 0.08, dgp.ks_uniform(pit)
