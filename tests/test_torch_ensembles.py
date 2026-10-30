"""The torch ensembles (precision-weighted, Bayesian, multiscale) against the
reference on the parity scenarios' constructions: same inner skaters, every
horizon's predictive probed (mean, std, logpdf, cdf, two quantiles, crps) at
1e-9 on seeded series; finite gradients at the ensembles' parameters."""
import math

import pytest

torch = pytest.importorskip("torch")

import skaters.transform as rt                                           # noqa: E402
from skaters.bayesian import bayesian_ensemble as ref_bayes               # noqa: E402
from skaters.conjugate import conjugate as ref_conjugate                 # noqa: E402
from skaters.ema import ema                                              # noqa: E402
from skaters.ensemble import precision_weighted_ensemble as ref_pw       # noqa: E402
from skaters.leaf import leaf                                            # noqa: E402
from skaters.multiscale import multiscale as ref_multiscale              # noqa: E402
from skaters.torch import from_reference                                 # noqa: E402
from skaters.torch.bayesian import bayesian_ensemble                     # noqa: E402
from skaters.torch.conjugate import conjugate, reference_skater          # noqa: E402
from skaters.torch.ensemble import precision_weighted_ensemble           # noqa: E402
from skaters.torch.multiscale import multiscale                          # noqa: E402
from skaters.torch.parity import random_series                           # noqa: E402

TOL = 1e-9
PROBE, Q_LO, Q_HI = 0.37, 0.05, 0.95


def _probe_ref(d):
    return [d.mean, d.std, d.logpdf(PROBE), d.cdf(PROBE), d.quantile(Q_LO), d.quantile(Q_HI), d.crps(PROBE)]


def _probe_tor(d):
    return [float(d.mean), float(d.std), float(d.logpdf(PROBE)), float(d.cdf(PROBE)),
            float(d.quantile(Q_LO)), float(d.quantile(Q_HI)), float(d.crps(PROBE))]


def _worst(ref_f, tor_f, series, k):
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for y in series:
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            assert len(d1) == len(d2) == k
            for a, b in zip(d1, d2):
                assert len(a.components) == len(b)
                for x, z in zip(_probe_ref(a), _probe_tor(b)):
                    if math.isfinite(x) or math.isfinite(z):
                        worst = max(worst, abs(x - z))
    return worst


def _pw(k):
    ref_f = ref_pw([ema(0.05, k=k), ema(0.2, k=k)], k=k)
    tor_f = precision_weighted_ensemble([reference_skater(ema(0.05, k=k)), reference_skater(ema(0.2, k=k))], k=k)
    return ref_f, tor_f


def _bayes(k):
    ref_f = ref_bayes([ema(0.05, k=k), ref_conjugate(leaf(k=k), rt.difference(), k=k)],
                      k=k, learning_rate=0.5, complexity_penalty=0.02, depths=[1, 1])
    tor_f = bayesian_ensemble([reference_skater(ema(0.05, k=k)),
                               conjugate(reference_skater(leaf(k=k)), from_reference("difference"), k=k)],
                              k=k, learning_rate=0.5, complexity_penalty=0.02, depths=[1, 1])
    return ref_f, tor_f


def _ms(k):
    ref_f = ref_multiscale(lambda kk: ref_conjugate(leaf(k=kk), rt.ema_transform(0.1), k=kk), k)
    tor_f = multiscale(lambda kk: conjugate(reference_skater(leaf(k=kk)),
                                            from_reference("ema_transform", alpha=0.1), k=kk), k)
    return ref_f, tor_f


BUILDERS = {"pw_ensemble": _pw, "bayes_ensemble": _bayes, "multiscale": _ms}


@pytest.mark.parametrize("name", sorted(BUILDERS))
@pytest.mark.parametrize("k", [1, 3])
@pytest.mark.parametrize("kind,seed", [("ar", 31), ("seasonal", 32), ("positive", 33)])
def test_ensemble_parity(name, k, kind, seed):
    series = random_series(300, seed=seed, kind=kind)
    ref_f, tor_f = BUILDERS[name](k)
    assert _worst(ref_f, tor_f, series, k) < TOL


@pytest.mark.parametrize("k", [1, 3])
def test_multiscale_more_scales(k):
    """Four scales at k=8: every eligible stride mixes at every horizon."""
    series = random_series(300, seed=34)
    kk = 8
    ref_f = ref_multiscale(lambda j: ref_conjugate(leaf(k=j), rt.ema_transform(0.1), k=j), kk, scales=[1, 2, 3, 8])
    tor_f = multiscale(lambda j: conjugate(reference_skater(leaf(k=j)), from_reference("ema_transform", alpha=0.1), k=j),
                       kk, scales=[1, 2, 3, 8])
    assert _worst(ref_f, tor_f, series, kk) < TOL


def test_single_scale_returns_the_base():
    base = lambda kk: conjugate(reference_skater(leaf(k=kk)), from_reference("ema_transform", alpha=0.1), k=kk)
    f = multiscale(base, 1)
    assert not hasattr(f, "subs")


def _grad_loss(tor_f, series, k):
    state = None
    loss = torch.zeros((), dtype=torch.float64)
    for t, y in enumerate(series[:-k]):
        dists, state = tor_f(y, state)
        if t >= 10:
            for h, d in enumerate(dists, start=1):
                loss = loss - d.logpdf(series[t + h])
    loss.backward()


def test_gradients_reach_the_parameters():
    series = random_series(80, seed=35)
    k = 2
    ema_mod = from_reference("ema_transform", alpha=0.1)
    tor_pw = precision_weighted_ensemble([reference_skater(ema(0.05, k=k)),
                                          conjugate(reference_skater(leaf(k=k)), ema_mod, k=k)], k=k)
    _grad_loss(tor_pw, series, k)
    assert tor_pw.floor.grad is not None and math.isfinite(float(tor_pw.floor.grad))
    assert ema_mod.alpha.grad is not None and math.isfinite(float(ema_mod.alpha.grad)) and float(ema_mod.alpha.grad) != 0.0

    ema_mod2 = from_reference("ema_transform", alpha=0.1)
    tor_b = bayesian_ensemble([reference_skater(ema(0.05, k=k)),
                               conjugate(reference_skater(leaf(k=k)), ema_mod2, k=k)],
                              k=k, learning_rate=0.5, complexity_penalty=0.02, depths=[1, 1])
    _grad_loss(tor_b, series, k)
    for p in (tor_b.learning_rate, tor_b.complexity_penalty, tor_b.prior_log_weights):
        assert p.grad is not None and bool(torch.isfinite(p.grad).all())
    assert ema_mod2.alpha.grad is not None and float(ema_mod2.alpha.grad) != 0.0

    mods = []

    def base(kk):
        m = from_reference("ema_transform", alpha=0.1)
        mods.append(m)
        return conjugate(reference_skater(leaf(k=kk)), m, k=kk)

    tor_m = multiscale(base, 3)
    _grad_loss(tor_m, series, 3)
    assert tor_m.forget.grad is not None and math.isfinite(float(tor_m.forget.grad))
    assert any(m.alpha.grad is not None and float(m.alpha.grad) != 0.0 for m in mods)
