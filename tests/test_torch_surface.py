"""skaters.torch exports the reference's surface (all but the multivariate
anomaly scorers), its spec JSON is the reference's string for string, and the
terminal ensemble's adaptive temperature matches the reference at 1e-9 with
its gradient reaching the learning rate."""

import math
import os
import random
import sys

import pytest

torch = pytest.importorskip("torch")

import skaters  # noqa: E402
import skaters.torch as T  # noqa: E402
from skaters.terminal import terminal_leaf_ensemble as r_tle  # noqa: E402
from skaters.ema import ema as r_ema  # noqa: E402
from skaters.leaf import leaf as r_leaf  # noqa: E402
from skaters.conjugate import conjugate as r_conj  # noqa: E402
from skaters.transform import difference as r_diff  # noqa: E402

TOL = 1e-9
EXCLUDED = {"mahalanobis", "zbank"}


def series(n=200, seed=17):
    rng = random.Random(seed)
    lvl, out = 0.0, []
    for t in range(n):
        lvl += rng.gauss(0, 0.3)
        out.append(lvl + 2.0 * math.sin(2 * math.pi * t / 7) + rng.gauss(0, 1.0))
    return out


def test_every_reference_export_is_in_torch():
    missing = sorted(set(skaters.__all__) - set(T.__all__) - EXCLUDED)
    assert not missing, f"skaters.torch lacks {missing}"
    for name in set(skaters.__all__) - EXCLUDED:
        assert hasattr(T, name), name


def test_spec_json_is_the_reference_string():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parity"))
    from gen_vectors import spec_examples
    for sp in spec_examples():
        text = skaters.to_json(sp)
        back = T.from_json(text)
        assert T.to_json(back) == text
        assert T.spec_name(back) == skaters.spec_name(sp)
        T.build(back)


def test_transform_factories_match_the_registry():
    assert type(T.ema_transform(0.1)) is T.REGISTRY["ema_transform"]
    assert float(T.yeo_johnson(0.5).lmbda) == 0.5


def test_top_periods_matches_reference():
    from skaters.periodicity import period_detector as r_pd, top_periods as r_top
    a, b = r_pd(), T.period_detector()
    sa = sb = None
    with torch.no_grad():
        for y in series(300):
            ra, sa = a(y, sa)
            rb, sb = b(y, sb)
            assert r_top(ra) == T.top_periods(rb)


@pytest.mark.parametrize("k,kw", [(1, {}), (1, {"temp_rho": 0.1, "depths": [0, 1]}),
                                  (3, {"forget": 0.99, "depths": [0, 1]}),
                                  (2, {"temp_band": 1.5, "learning_rate": 0.8})])
def test_adaptive_temperature_matches_reference(k, kw):
    ref = r_tle([r_ema(0.05, k=k), r_conj(r_leaf(k=k), r_diff(), k=k)], k=k,
                adaptive_temperature=True, **kw)
    tor = T.terminal_leaf_ensemble([T.ema(0.05, k=k), T.conjugate(T.leaf(k=k), T.difference(), k=k)],
                                   k=k, adaptive_temperature=True, **kw)
    sa = sb = None
    with torch.no_grad():
        for i, y in enumerate(series()):
            da, sa = ref(y, sa)
            db, sb = tor(y, sb)
            for h, (x, z) in enumerate(zip(da, db)):
                for p in (0.3, -2.0):
                    assert abs(x.logpdf(p) - float(z.logpdf(p))) <= TOL * (1 + abs(x.logpdf(p))), (i, h)
                    assert abs(x.cdf(p) - float(z.cdf(p))) <= TOL, (i, h)
                assert abs(x.mean - float(z.mean)) <= TOL * (1 + abs(x.mean)), (i, h)
            assert abs(sa["adapt"]["log_eta"] - float(sb["adapt"]["log_eta"])) <= TOL, i


def test_adaptive_temperature_gradient_reaches_learning_rate():
    tor = T.terminal_leaf_ensemble([T.ema(0.05, k=1), T.conjugate(T.leaf(k=1), T.difference(), k=1)],
                                   k=1, adaptive_temperature=True)
    ys = series(80)
    st = None
    loss = torch.zeros((), dtype=torch.float64)
    for i, y in enumerate(ys[:-1]):
        d, st = tor(y, st)
        if i > 30:
            loss = loss - d[0].logpdf(ys[i + 1])
    loss.backward()
    g = tor.learning_rate.grad
    assert g is not None and math.isfinite(float(g)) and float(g) != 0.0
