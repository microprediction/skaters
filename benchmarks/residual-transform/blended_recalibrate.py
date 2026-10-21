"""One Bayesian pool combining homogenize's continuous H2-filter candidates
and two_state_recalibrate's exact two-state HMM candidates.

Both families produce the identical kind of object: a zero-mean Gaussian
mixture {"weights": [...], "scales": [...]} sharing a common N(0,1)
reference density. That's exactly what makes homogenize's exact-pooling
identity work in the first place, and it means the two families can be
scored and pooled in one shared competition with no new math -- just
concatenate both candidate sets (each still running its own per-candidate
filter/EM update) and let the online evidence decide which family wins,
per series, rather than choosing by hand per arm.

Motivation from the two designs' own real-data results: the two-state HMM
wins decisively wherever there's genuine two-regime structure (FRED,
waveform) because it fits the exact model the data has; homogenize wins on
the price/garch_leaf arm, where the truth is closer to smoothly-varying
than genuinely bimodal, and its continuous filter is a softer, more
forgiving model class for that case than a hard two-state commitment (even
one hedged against a dedicated identity candidate -- adding that closed
most but not all of the gap, see run_two_state_hmm.py's before/after). A
shared pool doesn't require knowing which regime a given series is in
ahead of time.

Only one identity candidate is kept (both designs' own dedicated ones would
otherwise double up); it takes the same "half the total real candidates"
prior weight convention used everywhere else in this codebase.
"""
from __future__ import annotations
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import laplace_on_scale as los          # noqa: E402
import two_state_recalibrate as tsr     # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "..", "src"))
from skaters.homogenize import (        # noqa: E402
    logg, g, _cand_scales, _cand_weights, _update_q as _homog_update_q,
    _clip as _homog_clip, _V_MIN, _V_MAX, make_candidates as _homog_make_candidates,
)

_WEIGHT_DECAY = 0.9999
_LEARNING_RATE = 0.1
_SCORE_CAP = 20.0


def make_candidates(homog_grid=None, two_state_grid=None):
    homog_raw = _homog_make_candidates(*(homog_grid or ()))
    ts_raw = tsr.make_candidates(two_state_grid)

    candidates = [{"family": "identity"}]
    for c in homog_raw:
        if not c["is_identity"]:
            candidates.append({"family": "homog", "rho": c["rho"], "gain": c["gain"], "delta": c["delta"]})
    for c in ts_raw:
        if not c["is_identity"]:
            candidates.append({"family": "two_state", "lam": c["lam"], "pi_H": c["pi_H"]})
    return tuple(candidates)


def _init_dynamic(cfg: dict) -> dict:
    if cfg["family"] == "identity":
        return {}
    if cfg["family"] == "homog":
        return {"q": 0.0, "guard_run": 0}
    return tsr._init_candidate_state(cfg["pi_H"])


def _init_state(candidates) -> dict:
    n_other = max(sum(1 for c in candidates if c["family"] != "identity"), 1)
    dynamic = []
    for c in candidates:
        log_weight = math.log(n_other) if c["family"] == "identity" else 0.0
        dynamic.append(dict(_init_dynamic(c), log_weight=log_weight))
    return {"dynamic": dynamic, "n": 0}


def _correction_for(cfg: dict, d: dict) -> dict:
    fam = cfg["family"]
    if fam == "identity":
        return {"weights": [1.0], "scales": [1.0]}
    if fam == "homog":
        v = _homog_clip(1.0 + d["q"], _V_MIN, _V_MAX)
        return {"weights": list(_cand_weights(cfg["delta"])), "scales": list(_cand_scales(v, cfg["delta"]))}
    return tsr.candidate_correction(cfg, d)


def _update_for(cfg: dict, d: dict, z: float) -> None:
    fam = cfg["family"]
    if fam == "identity":
        return
    if fam == "homog":
        _homog_update_q(d, cfg, z * z - 1.0)
        return
    tsr.update_candidate(cfg, d, z)


def blended_step(z: float, state: dict | None, candidates: tuple) -> tuple[dict, dict]:
    """Score each candidate's already-issued correction against z, update
    its Bayesian weight, update its own family-specific state, then pool
    into the correction issued for the next tick -- identical structure to
    cell_step/hmm_step, just dispatching per candidate on cfg["family"]."""
    if state is None:
        state = _init_state(candidates)
    dynamic = state["dynamic"]

    for cfg, d in zip(candidates, dynamic):
        corr = _correction_for(cfg, d)
        r = logg(z, corr) - los._phi_logpdf(z)
        d["log_weight"] = _WEIGHT_DECAY * d["log_weight"] + _LEARNING_RATE * _homog_clip(r, -_SCORE_CAP, _SCORE_CAP)

    for cfg, d in zip(candidates, dynamic):
        _update_for(cfg, d, z)

    log_weights = [d["log_weight"] for d in dynamic]
    m = max(log_weights)
    raw = [math.exp(lw - m) for lw in log_weights]
    total = sum(raw)
    omega = [r / total for r in raw]

    weights, scales = [], []
    for cfg, d, w in zip(candidates, dynamic, omega):
        corr = _correction_for(cfg, d)
        for cw, s in zip(corr["weights"], corr["scales"]):
            weights.append(w * cw)
            scales.append(s)
    state["n"] += 1
    return {"weights": weights, "scales": scales}, state


def laplace_blended(base_factory=None, candidates=None):
    from skaters import laplace
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    candidates = candidates or make_candidates()

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "blend_state": None, "raw": None, "correction": None}
        s = state
        if s["raw"] is not None:
            u = los._clamp01(s["raw"].cdf(y))
            z = los._phi_inv(u)
            s["correction"], s["blend_state"] = blended_step(z, s["blend_state"], candidates)

        base_dists, s["base_state"] = base(y, s["base_state"])
        f_t = base_dists[0]
        s["raw"] = f_t

        corrected = f_t if s["correction"] is None else tsr.TwoStateHMMDist(f_t, s["correction"])
        return [corrected], s

    return _skater


def _gen_two_state_sv(T, seed, sigma_lo=0.6, sigma_hi=1.8, p_switch=0.02):
    import random
    rng = random.Random(seed)
    regime = 0
    sig = {0: sigma_lo, 1: sigma_hi}
    zs = []
    for _ in range(T):
        if rng.random() < p_switch:
            regime = 1 - regime
        zs.append(sig[regime] * rng.gauss(0.0, 1.0))
    return zs


def main():
    candidates = make_candidates()
    print(f"--- blended pool: {len(candidates)} candidates "
          f"({sum(1 for c in candidates if c['family']=='homog')} homog + "
          f"{sum(1 for c in candidates if c['family']=='two_state')} two_state + 1 identity) ---")

    print("--- synthetic: iid null ---")
    zs = [los.random.gauss(0.0, 1.0) for _ in range(6000)]
    state = None
    scores = []
    for t, z in enumerate(zs):
        if state is not None:
            pooled, _ = None, None
            log_weights = [d["log_weight"] for d in state["dynamic"]]
            m = max(log_weights)
            raw = [math.exp(lw - m) for lw in log_weights]
            omega = [r / sum(raw) for r in raw]
            weights, scales = [], []
            for cfg, d, w in zip(candidates, state["dynamic"], omega):
                corr = _correction_for(cfg, d)
                for cw, s in zip(corr["weights"], corr["scales"]):
                    weights.append(w * cw)
                    scales.append(s)
            pooled = {"weights": weights, "scales": scales}
            if t > 500:
                scores.append(logg(z, pooled) - los._phi_logpdf(z))
        _, state = blended_step(z, state, candidates)
    print(f"  mean delta logL vs phi: {sum(scores)/len(scores):+.4f}")

    print("--- synthetic: two-state SV ---")
    zs = _gen_two_state_sv(6000, seed=3)
    state = None
    scores = []
    for t, z in enumerate(zs):
        if state is not None:
            log_weights = [d["log_weight"] for d in state["dynamic"]]
            m = max(log_weights)
            raw = [math.exp(lw - m) for lw in log_weights]
            omega = [r / sum(raw) for r in raw]
            weights, scales = [], []
            for cfg, d, w in zip(candidates, state["dynamic"], omega):
                corr = _correction_for(cfg, d)
                for cw, s in zip(corr["weights"], corr["scales"]):
                    weights.append(w * cw)
                    scales.append(s)
            pooled = {"weights": weights, "scales": scales}
            if t > 1000:
                scores.append(logg(z, pooled) - los._phi_logpdf(z))
        _, state = blended_step(z, state, candidates)
    print(f"  mean delta logL vs phi: {sum(scores)/len(scores):+.4f}")


if __name__ == "__main__":
    main()
