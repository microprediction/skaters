"""Every transform chain in laplace's candidate pool (api._build_candidates),
rebuilt in torch around the reference leaf, matches the reference chain at
1e-9 on seeded series: emissions, every horizon, every component. This is
the claim behind the port: a model initialised at laplace's parameters is
laplace."""
import pytest

torch = pytest.importorskip("torch")

import skaters.transform as rt                                  # noqa: E402
from skaters.conjugate import conjugate as ref_conjugate        # noqa: E402
from skaters.leaf import leaf                                   # noqa: E402
from skaters.torch import from_reference                        # noqa: E402
from skaters.torch.conjugate import conjugate, reference_skater  # noqa: E402
from skaters.torch.parity import random_series                  # noqa: E402

TOL = 1e-9

# chains as (outer ... inner), mirroring api._build_candidates
POOL = (
    [[("ema_transform", {"alpha": a})] for a in (0.01, 0.05, 0.1, 0.3)]
    + [[("difference", {})]]
    + [[("drift", {"alpha": a, "shrinkage": s})] for a, s in ((0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002))]
    + [[("theta", {"alpha": a})] for a in (0.05, 0.1, 0.3)]
    + [[("ar", {"order": 1})], [("ar", {"order": 2, "decay": 1})]]
    + [[("holt_linear", {"alpha": a, "beta": b})] for a, b in ((0.1, 0.02), (0.1, 0.05), (0.3, 0.1))]
    + [[("seasonal_difference", {"period": p})] for p in (7, 12, 24)]
    + [[("seasonal_anchor", {"period": p})] for p in (7, 12, 24)]
    + [[("seasonal_difference", {"period": p}), ("ema_transform", {"alpha": a})] for p in (7, 12, 24) for a in (0.05, 0.1)]
    + [[("difference", {}), ("ema_transform", {"alpha": a})] for a in (0.05, 0.1, 0.3)]
    + [[("standardize", {}), ("ema_transform", {"alpha": a})] for a in (0.05, 0.1)]
    + [[("fractional_difference", {"d": d, "window": 30}), ("ema_transform", {"alpha": 0.1})] for d in (0.2, 0.4)]
    + [[("drift", {"alpha": ad, "shrinkage": sd}), ("ema_transform", {"alpha": ae})]
       for ad, sd in ((0.002, 0.001), (0.0005, 0.0002)) for ae in (0.05, 0.1)]
    + [[("drift", {"alpha": 0.001, "shrinkage": 0.0005}), ("holt_linear", {"alpha": 0.1, "beta": 0.05})]]
    + [[("garch", {}), ("ema_transform", {"alpha": 0.1})]]
    + [[("power_transform", {"p": 0.5}), ("ema_transform", {"alpha": 0.1})]]
)


def _build(chain, k, torch_side):
    f = reference_skater(leaf(k=k)) if torch_side else leaf(k=k)
    for name, kw in reversed(chain):            # inner first
        if torch_side:
            f = conjugate(f, from_reference(name, **kw), k=k)
        else:
            f = ref_conjugate(f, getattr(rt, name)(**kw), k=k)
    return f


def _worst(ref_f, tor_f, series, k):
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for y in series:
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            for a, b in zip(d1, d2):
                bc = b.to_reference().components
                assert len(a.components) == len(bc)
                for (w1, m1, v1), (w2, m2, v2) in zip(a.components, bc):
                    worst = max(worst, abs(w1 - w2), abs(m1 - m2), abs(v1 - v2))
    return worst


@pytest.mark.parametrize("chain", POOL, ids=lambda c: "/".join(n for n, _ in c))
@pytest.mark.parametrize("k", [1, 3])
def test_pool_chain_parity(chain, k):
    kind = "positive" if chain[0][0] == "power_transform" else "seasonal" if "seasonal" in chain[0][0] else "ar"
    series = random_series(220, seed=11, kind=kind)
    assert _worst(_build(chain, k, False), _build(chain, k, True), series, k) < TOL
