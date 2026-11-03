"""skaters.torch sticky / parade / gpdtails against the reference wrappers,
each around the same inner skater, probed at every horizon and step
(mean, std, logpdf, cdf, two quantiles, crps) at 1e-9."""
import math
import random

import pytest

torch = pytest.importorskip("torch")

import importlib                                                             # noqa: E402
# the package re-exports functions under these names; fetch the modules themselves
rsticky = importlib.import_module("skaters.sticky")
rparade = importlib.import_module("skaters.parade")
rtails = importlib.import_module("skaters.tails")
from skaters.api import _laplace_single_scale                               # noqa: E402
from skaters.conjugate import conjugate as rconjugate                        # noqa: E402
from skaters.leaf import leaf                                                # noqa: E402
from skaters.transform import ema_transform                                  # noqa: E402
from skaters.torch.conjugate import reference_skater                          # noqa: E402
from skaters.torch.parade import parade as tparade                            # noqa: E402
from skaters.torch.parity import random_series                                # noqa: E402
from skaters.torch.sticky import sticky as tsticky                            # noqa: E402
from skaters.torch.tails import gpdtails as tgpdtails, TorchSplicedDist       # noqa: E402

TOL = 1e-9
PROBE = 0.3


def _probe(d, x):
    """(mean, std, logpdf, cdf, q10, q90, crps) as floats, for either port."""
    vals = (d.mean, d.std, d.logpdf(x), d.cdf(x), d.quantile(0.1), d.quantile(0.9), d.crps(x))
    return [float(v) for v in vals]


def _run_pair(ref_f, tor_f, series, k, probes=(PROBE,), skip=0):
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for t, y in enumerate(series):
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            assert len(d1) == len(d2) == k
            if t < skip:
                continue
            for a, b in zip(d1, d2):
                assert type(a).__name__.startswith("Spliced") == type(b).__name__.startswith("TorchSpliced"), (t, type(a), type(b))
                for x in probes + ((y,) if (isinstance(y, float) and math.isfinite(y)) else ()):
                    pa, pb = _probe(a, x), _probe(b, x)
                    for u, v in zip(pa, pb):
                        if math.isfinite(u) and math.isfinite(v):
                            worst = max(worst, abs(u - v))
                        else:
                            assert (math.isfinite(u), u > 0) == (math.isfinite(v), v > 0), (t, pa, pb)
    return worst, s1, s2


def _lattice_series(n=260, seed=3):
    rng = random.Random(seed)
    vals = [0.0, 0.25, 0.5, 1.0]
    out = []
    for t in range(n):
        out.append(rng.choice(vals) if rng.random() < 0.7 else round(rng.gauss(0.5, 0.4), 2))
    return out


INNERS = {
    "leaf": lambda k: leaf(k=k),
    "trunk": lambda k: _laplace_single_scale(k, "crps", False, None, 0.03),
}


@pytest.mark.parametrize("inner", ["leaf", "trunk"])
@pytest.mark.parametrize("k", [1, 3])
@pytest.mark.parametrize("kind", ["ar", "lattice", "rounded"])
def test_sticky_matches_reference(inner, k, kind):
    if kind == "ar":
        series = random_series(220, seed=31)
    elif kind == "lattice":
        series = _lattice_series()
    else:
        series = [round(v, 1) for v in random_series(220, seed=32)]
    ref_f = rsticky.sticky(INNERS[inner](k), k=k)
    tor_f = tsticky(reference_skater(INNERS[inner](k)), k=k)
    worst, s1, _ = _run_pair(ref_f, tor_f, series, k)
    assert worst < TOL, worst
    if kind == "lattice":
        assert s1["counts"], "the lattice series should populate the value table"


@pytest.mark.parametrize("inner", ["leaf", "trunk"])
@pytest.mark.parametrize("k", [1, 3])
def test_parade_matches_reference_and_tracks_pit_z(inner, k):
    series = random_series(200, seed=33)
    ref_f = rparade.parade(INNERS[inner](k), k=k)
    tor_f = tparade(reference_skater(INNERS[inner](k)), k=k)
    s1 = s2 = None
    worst = 0.0
    worst_z = 0.0
    with torch.no_grad():
        for y in series:
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            for a, b in zip(d1, d2):
                for u, v in zip(_probe(a, PROBE), _probe(b, PROBE)):
                    worst = max(worst, abs(u - v))
            for a, b in zip(s1["pit"], s2["pit"]):
                assert (a is None) == (b is None)
                if a is not None:
                    worst = max(worst, abs(a - b))
            for a, b in zip(s1["z"], s2["z"]):
                assert (a is None) == (b is None)
                if a is not None:
                    # z = Phi^-1(pit): near the 1e-12 clamp |z| ~ 7 and dz/du ~ 1e11,
                    # so round-off in the PIT (math.erf vs torch.erf, ~1e-16) is
                    # amplified by five orders; compare where the map is tame
                    if abs(a) < 5.0:
                        worst_z = max(worst_z, abs(a - b))
                    else:
                        assert (a > 0) == (b > 0) and abs(a - b) < 1e-3
    assert worst < TOL, worst
    assert worst_z < 1e-8, worst_z


@pytest.mark.parametrize("k", [1, 3])
def test_parade_missing_observations(k):
    series = random_series(160, seed=34)
    for i in (0, 1, 40, 41, 42, 100):          # leading gap, a run of gaps, an isolated gap
        series[i] = float("nan")
    ref_f = rparade.parade(leaf(k=k), k=k)
    tor_f = tparade(reference_skater(leaf(k=k)), k=k)
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for y in series:
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            assert len(d1) == len(d2) == k
            for a, b in zip(d1, d2):
                for u, v in zip(_probe(a, PROBE), _probe(b, PROBE)):
                    worst = max(worst, abs(u - v))
            assert [p is None for p in s1["pit"]] == [p is None for p in s2["pit"]]
    assert s1["skipped"] == s2["skipped"] == 6
    assert worst < TOL, worst


def _gpd_pair(k, nexc=50, warmup=100):
    ref_f = rtails.gpdtails(rconjugate(leaf(k=k), ema_transform(0.1), k=k), k=k,
                            level=0.9, nexc=nexc, warmup=warmup)
    tor_f = tgpdtails(reference_skater(rconjugate(leaf(k=k), ema_transform(0.1), k=k)), k=k,
                      level=0.9, nexc=nexc, warmup=warmup)
    return ref_f, tor_f


@pytest.mark.parametrize("k", [1, 3])
def test_gpdtails_matches_reference_after_freezing(k):
    """The gen_vectors gpd_tails scenario (level 0.9, nexc 50, warmup 100),
    run long enough that both tails are fitted and spliced."""
    series = random_series(1200, seed=35)
    ref_f, tor_f = _gpd_pair(k)
    worst, s1, s2 = _run_pair(ref_f, tor_f, series, k, probes=(PROBE, 5.0, -5.0))
    assert worst < TOL, worst
    th = s1["tails"][0]
    assert th["up"]["t"] is not None and len(th["up"]["exc"]) >= 8 and len(th["lo"]["exc"]) >= 8
    # the torch tail state equals the reference tail state (pure floats)
    for a, b in zip(s1["tails"], s2["tails"]):
        for side in ("up", "lo"):
            assert a[side]["t"] == b[side]["t"] or abs(a[side]["t"] - b[side]["t"]) < TOL
            assert abs(a[side]["g"] - b[side]["g"]) < TOL and abs(a[side]["s"] - b[side]["s"]) < TOL
            assert abs(a[side]["r"] - b[side]["r"]) < TOL


def test_spliced_dist_round_trips_and_differentiates():
    series = random_series(700, seed=36)
    ref_f, tor_f = _gpd_pair(1)
    s2 = None
    d2 = None
    for y in series:
        d2, s2 = tor_f(y, s2)
    sd = d2[0]
    assert isinstance(sd, TorchSplicedDist)
    back = TorchSplicedDist.from_reference(sd.to_reference())
    assert abs(float(back.logpdf(PROBE)) - float(sd.logpdf(PROBE))) < 1e-12
    # a log score in the tail region differentiates through the body
    m = torch.tensor(float(sd.body.mean), dtype=torch.float64, requires_grad=True)
    body = sd.body.shift(m - float(sd.body.mean))
    tail_x = float(sd.quantile(0.999)) + 1.0
    d = TorchSplicedDist(body, sd.t_lo, sd.t_up, sd.zeta_lo, sd.zeta_up, sd.g_lo, sd.s_lo, sd.g_up, sd.s_up)
    d.logpdf(tail_x).backward()
    assert m.grad is not None and math.isfinite(float(m.grad)) and float(m.grad) != 0.0
