"""skaters.torch leaf family against the reference: every horizon's predictive
probed as parity/gen_vectors.py probes (mean, std, logpdf, cdf, two
quantiles, crps) at round-off tolerance on seeded series of several kinds,
including a constant-then-noise series so the variance floors fire; and
finite gradients from a log score to the learnable rates. Skipped where
torch is absent."""
import math
import random

import pytest

torch = pytest.importorskip("torch")

import importlib                                                # noqa: E402
rl = importlib.import_module("skaters.leaf")   # the package re-exports a `leaf` function that shadows the module
from skaters.ema import ema as ref_ema                          # noqa: E402
import skaters.torch.leaf as tl                                  # noqa: E402
from skaters.torch.ema import ema as tor_ema                    # noqa: E402
from skaters.torch.parity import random_series                  # noqa: E402

PROBE, Q_LO, Q_HI = 0.37, 0.05, 0.95
TOL = 1e-9
QTOL = 1e-8          # bisection: the two ports may stop one half-step apart

FACTORIES = [
    ("leaf", lambda k: rl.leaf(k=k), lambda k: tl.leaf(k=k)),
    ("scale_mixture_leaf", lambda k: rl.scale_mixture_leaf(k=k), lambda k: tl.scale_mixture_leaf(k=k)),
    ("crps_leaf", lambda k: rl.crps_leaf(k=k), lambda k: tl.crps_leaf(k=k)),
    ("crps_leaf_sa03", lambda k: rl.crps_leaf(k=k, scale_alpha=0.03), lambda k: tl.crps_leaf(k=k, scale_alpha=0.03)),
    ("garch_leaf", lambda k: rl.garch_leaf(k=k), lambda k: tl.garch_leaf(k=k)),
    ("conforming_leaf", lambda k: rl.conforming_leaf(k=k), lambda k: tl.conforming_leaf(k=k)),
    ("ensemble_leaf", lambda k: rl.ensemble_leaf(k=k), lambda k: tl.ensemble_leaf(k=k)),
    ("ema", lambda k: ref_ema(0.05, k=k), lambda k: tor_ema(0.05, k=k)),
    ("ema_fast", lambda k: ref_ema(0.3, k=k), lambda k: tor_ema(0.3, k=k)),
]


def _series(kind, seed):
    if kind == "const_then_noise":
        rng = random.Random(seed)
        return [3.0] * 120 + [3.0 + 0.5 * rng.gauss(0, 1) for _ in range(180)]
    return random_series(300, seed=seed, kind=kind)


def _probe_ref(d):
    return (d.mean, d.std, d.logpdf(PROBE), d.cdf(PROBE), d.quantile(Q_LO), d.quantile(Q_HI), d.crps(PROBE))


def _probe_tor(d):
    return tuple(float(v) for v in (d.mean, d.std, d.logpdf(PROBE), d.cdf(PROBE),
                                    d.quantile(Q_LO), d.quantile(Q_HI), d.crps(PROBE)))


def _worst(ref_f, tor_f, series, k):
    s1 = s2 = None
    worst = [0.0] * 7
    with torch.no_grad():
        for y in series:
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            assert len(d1) == len(d2) == k
            for a, b in zip(d1, d2):
                assert len(a.components) == len(b)
                pa, pb = _probe_ref(a), _probe_tor(b)
                for i, (x, z) in enumerate(zip(pa, pb)):
                    if math.isinf(x) or math.isinf(z):
                        assert x == z, (x, z)
                        continue
                    worst[i] = max(worst[i], abs(x - z))
    return worst


@pytest.mark.parametrize("name,ref_fn,tor_fn", FACTORIES, ids=[f[0] for f in FACTORIES])
@pytest.mark.parametrize("kind,seed", [("ar", 1), ("positive", 2), ("seasonal", 3), ("const_then_noise", 4)])
@pytest.mark.parametrize("k", [1, 3])
def test_leaf_parity(name, ref_fn, tor_fn, kind, seed, k):
    worst = _worst(ref_fn(k), tor_fn(k), _series(kind, seed), k)
    for i, w in enumerate(worst):
        tol = QTOL if i in (4, 5) else TOL
        assert w < tol, (name, kind, k, ["mean", "std", "logpdf", "cdf", "q_lo", "q_hi", "crps"][i], worst)


@pytest.mark.parametrize("mk", [lambda: tl.crps_leaf(k=1), lambda: tl.scale_mixture_leaf(k=1),
                                lambda: tor_ema(0.1, k=1)], ids=["crps_leaf", "scale_mixture_leaf", "ema"])
def test_gradients_reach_every_parameter(mk):
    mod = mk()
    series = random_series(160, seed=7)
    state = None
    loss = torch.zeros((), dtype=torch.float64)
    for t, y in enumerate(series[:-1]):
        dists, state = mod(y, state)
        if t >= 120:                      # past the 1/n bootstrap, the rates are in use
            loss = loss - dists[0].logpdf(series[t + 1])
    loss.backward()
    params = dict(mod.named_parameters())
    assert params
    for n, p in params.items():
        assert p.grad is not None and math.isfinite(float(p.grad)), (n, p.grad)
        assert float(p.grad) != 0.0, n
