"""A skater is a fold: Python state must survive a pickle round trip exactly.

The JS twin's contract is JSON (parity/roundtrip.mjs); Python's is pickle,
which carries the deques and float-keyed dicts the reference uses. For every
parity scenario the state is checkpointed every 50 steps, restored through
pickle.loads(pickle.dumps(state)), and the restored copy is stepped beside
the original for the next 25 steps: every predictive and both states must
be equal under gen_vectors.state_snapshot, which is float-exact, strict on
container types, and reads Dist through to_dict. (Pickled bytes are not a
usable equality: pickle memoises tuples and strings by identity.)

search is exempt: its pool holds recipe-built closures, which pickle cannot
carry. The JS port rebuilds them from the recipe; the Python mirror of that
is separate work.
"""

import os
import pickle
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "parity"))

import gen_vectors  # noqa: E402

EVERY = 50
CONTINUE = 25


def _scenarios():
    series = gen_vectors.make_series(n=400, seed=12345)
    repeat = gen_vectors.make_repeat_series(n=400, seed=99)
    for name, _k, sk in gen_vectors.build_scenarios():
        if name in gen_vectors.ROUNDTRIP_EXEMPT:
            continue
        yield name, sk, series
    from skaters import laplace
    from skaters.conjugate import conjugate
    from skaters.leaf import leaf
    from skaters.sticky import sticky
    from skaters.transform import ema_transform
    yield "sticky_ema_repeat", sticky(conjugate(leaf(k=1), ema_transform(0.1), k=1), k=1), repeat
    yield "laplace_repeat", laplace(k=1), repeat


snap = gen_vectors.state_snapshot


@pytest.mark.parametrize("name,skater,series", list(_scenarios()), ids=lambda v: v if isinstance(v, str) else "")
def test_pickle_roundtrip_is_exact(name, skater, series):
    state = None
    i = 0
    n = len(series)
    while i < n:
        _dists, state = skater(series[i], state)
        if (i + 1) % EVERY == 0 and i + CONTINUE < n:
            twin = pickle.loads(pickle.dumps(state))
            assert snap(twin) == snap(state), f"{name} t={i}: restore differs: {gen_vectors.state_diff(snap(state), snap(twin))}"
            for m in range(1, CONTINUE + 1):
                y = series[i + m]
                da, state = skater(y, state)
                db, twin = skater(y, twin)
                assert snap(da) == snap(db), f"{name} t={i} +{m}: predictive differs after restore"
                sa, sb = snap(state), snap(twin)
                assert sa == sb, f"{name} t={i} +{m}: state differs after restore: {gen_vectors.state_diff(sa, sb)}"
            i += CONTINUE
        i += 1
