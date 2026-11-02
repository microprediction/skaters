"""skaters.torch.learned (#297 step 2): laplace at worst.

At initialisation the learned expert equals laplace and so does the mixture;
the Aggregating-Algorithm bound holds at every prefix even when the learned
expert is deliberately corrupted; the forecast issued for y_t cannot depend on
y_t; gradients reach the gate and the transform parameters; projection keeps
parameters inside their bounds. Skipped where torch is absent."""
import copy
import math
import random

import pytest

torch = pytest.importorskip("torch")

from skaters.api import laplace as ref_laplace                  # noqa: E402
from skaters.torch.learned import LearnedLaplace, MixtureDist, BOUNDS, learned  # noqa: E402
from skaters.torch.dist import TorchDist                         # noqa: E402

TOL = 1e-6


def _series(n, seed, kind="ar"):
    rng = random.Random(seed)
    x, out = 0.0, []
    for t in range(n):
        if kind == "ar":
            x = 0.6 * x + rng.gauss(0, 1)
        elif kind == "seasonal":
            x = math.sin(2 * math.pi * t / 12) + 0.3 * rng.gauss(0, 1)
        elif kind == "jumps":
            x = x + rng.gauss(0, 1) + (8.0 if rng.random() < 0.05 else 0.0)
        out.append(x)
    return out


def _probe(d, y):
    return [float(d.logpdf(y)), float(d.cdf(y)), float(d.mean), float(d.std),
            float(d.quantile(0.05)), float(d.quantile(0.5)), float(d.quantile(0.95))]


@pytest.mark.parametrize("k", [1, 3])
@pytest.mark.parametrize("kind,seed", [("ar", 1), ("seasonal", 2)])
def test_initialisation_equals_laplace(k, kind, seed):
    ys = _series(160, seed, kind)
    f = learned(k)
    g = ref_laplace(k)
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for t, y in enumerate(ys):
            d1, s1 = f(y, s1)
            d2, s2 = g(y, s2)
            assert len(d1) == len(d2) == k
            if t < 30:
                continue
            for a, b in zip(d1, d2):
                probe_y = y + 0.3
                pa = _probe(a, probe_y)
                pb = [b.logpdf(probe_y), b.cdf(probe_y), b.mean, b.std,
                      b.quantile(0.05), b.quantile(0.5), b.quantile(0.95)]
                for x, z in zip(pa, pb):
                    if math.isfinite(x) or math.isfinite(z):
                        assert math.isfinite(x) and math.isfinite(z), (x, z)
                        worst = max(worst, abs(x - z))
    assert worst < TOL, worst


class _Corrupted(LearnedLaplace):
    """The learned expert replaced by a badly mis-scaled, shifted forecast."""

    def _learned_dists(self, y, state):
        dists = super()._learned_dists(y, state)
        out = []
        for d in dists:
            body = getattr(d, "body", d)
            out.append(TorchDist.from_reference(body.to_reference()).shift(3.0).scale(6.0))
        return out


@pytest.mark.parametrize("k", [1, 2])
@pytest.mark.parametrize("pi", [0.5, 0.1])
def test_aggregating_bound_holds_at_every_prefix_against_a_corrupted_expert(k, pi):
    ys = _series(200, 11, "jumps")
    f = _Corrupted(k=k, pi_lap=pi)
    g = ref_laplace(k)
    s1 = s2 = None
    pend_mix, pend_lap = [], []
    cum_mix = [0.0] * k
    cum_lap = [0.0] * k
    with torch.no_grad():
        for t, y in enumerate(ys):
            # score matured forecasts for y_t, unfloored (the statement is about raw log loss)
            for h in range(1, k + 1):
                if len(pend_mix) >= h:
                    dm = pend_mix[-h][h - 1]
                    dl = pend_lap[-h][h - 1]
                    lm = float(dm.logpdf(y))
                    ll = float(dl.logpdf(y))
                    assert math.isfinite(lm) and math.isfinite(ll), (t, h, lm, ll)
                    cum_mix[h - 1] += -lm
                    cum_lap[h - 1] += -ll
                    rent = -h * math.log(pi)          # h interleaved phases, one prior each
                    assert cum_mix[h - 1] <= cum_lap[h - 1] + rent + 1e-6, (t, h, cum_mix[h - 1], cum_lap[h - 1])
            d1, s1 = f(y, s1)
            d2, s2 = g(y, s2)
            pend_mix.append(d1)
            pend_lap.append(d2)
    # and the corrupted expert really was worse, so the bound was doing work
    assert cum_mix[0] > 0


def test_mutating_the_past_changes_the_future_but_not_the_issued_forecast():
    ys = _series(100, 9)
    f = learned(1)
    with torch.no_grad():
        s = None
        for y in ys[:60]:
            d, s = f(y, s)
        snapshot = copy.deepcopy(s)
        issued = _probe(d[0], 0.2)           # forecast for y_60, issued after y_59
        d_a, _ = f(ys[60], copy.deepcopy(snapshot))
        d_b, _ = f(ys[60] + 10.0, copy.deepcopy(snapshot))
    assert issued == _probe(d[0], 0.2)
    assert _probe(d_a[0], 0.2) != _probe(d_b[0], 0.2)       # the NEXT forecast does respond


def test_gradients_reach_gate_and_transforms_and_projection_holds():
    ys = _series(90, 3)
    f = learned(1)
    s = None
    loss = torch.zeros((), dtype=torch.float64)
    pend = None
    for y in ys:
        if pend is not None:
            loss = loss - pend[0].logpdf(y)
        d, s = f(y, s)
        pend = d
    loss.backward()
    gate_grads = [p.grad for p in f.gates.parameters() if p.grad is not None]
    assert gate_grads and any(float(g.abs().sum()) > 0 for g in gate_grads)
    tr_grads = [p.grad for n, p in f.learned.named_parameters() if p.grad is not None and "candidate_modules" in n]
    assert tr_grads and any(float(g.abs().sum()) > 0 for g in tr_grads)
    # an aggressive step past the boundaries, then projection
    with torch.no_grad():
        for n, p in f.learned.named_parameters():
            leaf = n.rsplit(".", 1)[-1]
            if leaf in BOUNDS:
                p.add_(5.0)
    f.project_()
    for n, p in f.learned.named_parameters():
        leaf = n.rsplit(".", 1)[-1]
        if leaf in BOUNDS:
            lo, hi = BOUNDS[leaf]
            v = float(p)
            assert (lo is None or v >= lo - 1e-12) and (hi is None or v <= hi + 1e-12), (n, v)


def test_mixture_dist_is_exact_on_gaussians():
    a = TorchDist.gaussian(0.0, 1.0)
    b = TorchDist.gaussian(2.0, 0.5)
    m = MixtureDist([a, b], [math.log(0.3), math.log(0.7)])
    ref = TorchDist.combine([a, b], [0.3, 0.7])
    for x in (-1.0, 0.0, 1.5, 2.5):
        assert abs(float(m.logpdf(x)) - float(ref.logpdf(x))) < 1e-12
        assert abs(float(m.cdf(x)) - float(ref.cdf(x))) < 1e-12
    assert abs(float(m.mean) - float(ref.mean)) < 1e-12
    assert abs(float(m.var) - float(ref.var)) < 1e-12
    for p in (0.05, 0.5, 0.95):
        assert abs(float(m.quantile(p)) - float(ref.quantile(p))) < 1e-7
    assert abs(float(m.crps(0.7)) - float(ref.crps(0.7))) < 2e-2    # grid estimator vs closed form


def test_checkpoint_restore_across_a_window_boundary():
    """A deepcopy of the state at a window boundary continues bit for bit."""
    ys = _series(110, 17, "seasonal")
    f = learned(2)
    with torch.no_grad():
        s = None
        for y in ys[:64]:
            d, s = f(y, s)
        snap = copy.deepcopy(s)
        a, b = [], []
        sa, sb = s, snap
        for y in ys[64:]:
            da, sa = f(y, sa)
            db, sb = f(y, sb)
            a.append([_probe(x, y + 0.1) for x in da])
            b.append([_probe(x, y + 0.1) for x in db])
    assert a == b
