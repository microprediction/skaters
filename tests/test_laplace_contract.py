"""The laplace contract: what deployed users may rely on, frozen.

People run `laplace` in production. This file locks the public contract so
that breaking it is a deliberate act (edit this file, bump the version,
write the changelog entry) and never an accident:

  1. the call signature and its defaults;
  2. the state surface (pit/z diagnostics, purity/picklability);
  3. the emitted Dist interface;
  4. determinism (same series -> bit-identical outputs);
  5. checkpoint-restore equivalence: pickle the state mid-stream, resume,
     and the continuation is bit-identical to the uninterrupted run — the
     deployment guarantee behind "skater state is pure data".
"""
import inspect
import math
import pickle
import random

from skaters import laplace

# One benign stream and one nasty stream; the contract holds on both.
def _streams():
    rng = random.Random(1234)
    benign = []
    lvl = 0.0
    for t in range(900):
        lvl += rng.gauss(0, 0.2)
        benign.append(lvl + 2.0 * math.sin(2 * math.pi * t / 7)
                      + rng.gauss(0, 1.0))
    nasty = []
    for t in range(900):
        vol = 8.0 if (t // 150) % 2 else 1.0
        nasty.append(rng.gauss(0, vol))
    nasty[449] = 1e6                       # a monster mid-stream
    return {"benign": benign, "nasty": nasty}


def _probe(d, y):
    return (d.mean, d.std, d.logpdf(y), d.cdf(y),
            d.quantile(0.1), d.quantile(0.9), d.crps(y))


def test_signature_is_frozen():
    """Changing laplace's signature must be deliberate: update this test,
    the changelog, and the version together."""
    sig = inspect.signature(laplace)
    assert list(sig.parameters) == [
        "k", "objective", "sticky", "leaf", "scales", "scale_alpha", "tails"]
    d = {n: p.default for n, p in sig.parameters.items()}
    assert d["k"] == 1
    assert d["objective"] == "crps"
    assert d["sticky"] is True
    assert d["leaf"] is None
    assert d["scales"] is None
    assert d["scale_alpha"] == 0.03
    assert d["tails"] == "gpd"


def test_state_surface_and_dist_interface():
    for k in (1, 3):
        f = laplace(k)
        state = None
        for y in _streams()["benign"]:
            dists, state = f(y, state)
        assert len(dists) == k
        assert len(state["pit"]) == k and len(state["z"]) == k
        for m in range(k):
            u, z = state["pit"][m], state["z"][m]
            assert u is None or 0.0 <= u <= 1.0
            assert z is None or abs(z) <= 7.04
        for d in dists:
            vals = _probe(d, 0.3)
            assert all(v == v for v in vals)          # no NaN
            assert 0.0 <= vals[3] <= 1.0
            assert vals[4] <= vals[5]                 # quantiles ordered


def test_determinism():
    for name, ys in _streams().items():
        outs = []
        for _ in range(2):
            f = laplace(1)
            state = None
            probes = []
            for t, y in enumerate(ys):
                dists, state = f(y, state)
                if t % 97 == 0:
                    probes.append(_probe(dists[0], y))
            outs.append(probes)
        assert outs[0] == outs[1], f"nondeterminism on {name} stream"


def test_checkpoint_restore_equivalence():
    """Pickle mid-stream, resume, and match the uninterrupted run exactly —
    on the benign stream AND through a monster spike."""
    for name, ys in _streams().items():
        f = laplace(1)
        state = None
        straight = []
        for t, y in enumerate(ys):
            dists, state = f(y, state)
            if t % 89 == 0:
                straight.append(_probe(dists[0], y))

        f2 = laplace(1)
        state2 = None
        resumed = []
        for t, y in enumerate(ys):
            if t == len(ys) // 2:
                state2 = pickle.loads(pickle.dumps(state2))   # checkpoint
                f2 = laplace(1)                               # fresh wrapper
            dists, state2 = f2(y, state2)
            if t % 89 == 0:
                resumed.append(_probe(dists[0], y))
        assert straight == resumed, f"resume mismatch on {name} stream"
