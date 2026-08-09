"""Tests for the pure z-space homogenized cell model
(benchmarks/homogenization/cell_model.py, synthetic.py).

Not a skaters library module (see the module docstring for why -- this is
deliberately decoupled from Dist/skaters until the synthetic gate passes),
so it isn't on the normal PYTHONPATH=src import path; add its folder here.
"""
import math
import os
import sys

_HOMOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "benchmarks", "homogenization")
sys.path.insert(0, os.path.normpath(_HOMOG))

import cell_model as cm  # noqa: E402
import synthetic as syn  # noqa: E402


def test_identity_dominates_on_iid_null():
    """Spec 13.A: on iid N(0,1) data the pool must not pay a meaningful
    log-score tax, and identity should be the clear leading candidate."""
    zs, _ = syn.gen_iid_gaussian(6000, seed=1)
    r = syn.run_experiment(zs, [1.0] * len(zs))
    assert r["identity_weight"] > 0.3, r["identity_weight"]
    assert r["mean_delta_logL"] > -0.005, r["mean_delta_logL"]


def test_recovers_two_regime_volatility():
    """Spec 13.C: on two-state stochastic volatility, identity must be
    abandoned in favor of an actively-tracking candidate, the gain must be
    reliably positive, and the pool's inferred variance must track the true
    regime (and H2 autocorrelation must fall)."""
    zs, true_var = syn.gen_two_state_sv(6000, seed=3)
    r = syn.run_experiment(zs, true_var)
    assert r["identity_weight"] < 0.05, r["identity_weight"]
    assert r["top_weight"] > 0.3 and not r["top_candidate"]["is_identity"]
    assert r["mean_delta_logL"] > 0.05, r["mean_delta_logL"]
    assert r["corr_vpool_true_regime"] > 0.5, r["corr_vpool_true_regime"]
    assert r["h2_autocorr_after"] < 0.5 * r["h2_autocorr_before"]


def test_exact_pooling_identity():
    """The correction cell_step returns must equal the direct weighted union
    of each candidate's own (scale, weight) pairs -- spec section 5's exact-
    pooling identity, no approximation."""
    candidates = cm.make_candidates(rho_grid=(0.9,), gain_grid=(0.1,), delta_grid=(0.0, 0.3))
    state = None
    zs = [0.4, -1.1, 2.0, 0.05, -0.7, 1.3, -2.4, 0.9]
    correction = None
    for z in zs:
        correction, state = cm.cell_step(z, state, candidates)

    omega = cm.candidate_weights(state)
    for z in (-3.0, -0.5, 0.0, 0.5, 1.7, 3.2):
        direct = 0.0
        for cfg, d, w in zip(candidates, state["dynamic"], omega):
            v = cm._clip(1.0 + d["q"], cm._V_MIN, cm._V_MAX)
            for s, cw in zip(cm._cand_scales(v, cfg["delta"]), cm._cand_weights(cfg["delta"])):
                direct += w * cw * (math.exp(cm.phi_logpdf(z / s)) / s)
        assert abs(cm.g(z, correction) - direct) < 1e-12, (z, cm.g(z, correction), direct)


def test_causal_no_lookahead():
    """Truncating the z-stream must not change earlier issued corrections."""
    import random
    rng = random.Random(11)
    zs = [rng.gauss(0.0, 1.0) for _ in range(150)]
    cut = 90

    def run(stream):
        candidates = cm.make_candidates()
        state = None
        out = []
        for z in stream:
            correction, state = cm.cell_step(z, state, candidates)
            out.append((list(correction["weights"]), list(correction["scales"])))
        return out

    full = run(zs)
    prefix = run(zs[:cut])
    assert len(prefix) == cut
    assert full[:cut] == prefix


def test_scale_mixture_is_valid_density():
    """Every issued correction is a legitimate density: positive weights
    summing to 1, positive scales, integrates to ~1."""
    import random
    rng = random.Random(5)
    candidates = cm.make_candidates()
    state = None
    correction = None
    for _ in range(500):
        z = rng.gauss(0.0, 1.0)
        correction, state = cm.cell_step(z, state, candidates)

    assert all(w > 0 for w in correction["weights"])
    assert all(s > 0 for s in correction["scales"])
    assert abs(sum(correction["weights"]) - 1.0) < 1e-9

    grid = [-15.0 + 0.02 * i for i in range(1501)]
    total = sum(cm.g(z, correction) for z in grid) * 0.02
    assert abs(total - 1.0) < 1e-2


def test_huber_changepoint_escape():
    """A persistent run of capped innovations must escape the cap after
    _ADAPT_AFTER consecutive ticks, rather than staying capped forever
    (mirrors the guard-and-escape idiom in skaters.anomaly.mahalanobis)."""
    cfg = {"rho": 0.0, "gain": 1.0, "delta": 0.0}
    d = {"q": 0.0, "guard_run": 0}
    big_x = 20.0
    assert big_x - 0.0 > cm._INNOVATION_CAP

    for _ in range(cm._ADAPT_AFTER):
        cm._update_q(d, cfg, big_x)
        assert abs(d["q"] - cfg["gain"] * cm._INNOVATION_CAP) < 1e-12, d["q"]

    cm._update_q(d, cfg, big_x)   # the (_ADAPT_AFTER + 1)-th consecutive capped tick
    assert abs(d["q"] - cfg["gain"] * big_x) < 1e-12, d["q"]   # escaped: uncapped now
