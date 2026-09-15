"""Exact two-state Markov-filter recalibration, per Section 12 ("The
corresponding skaters transform") of Cotton (2026), "One Poisson Equation
for Conformal Coverage under Dependence."

homogenize.py hedges over a heuristic pool of (rho, gain, delta) scale-
filter candidates because the true state-transition dynamics aren't known.
The paper's Section 12 construction is the *exact* object that pool was
approximating: a genuine two-state (Low/High) Markov chain on the
Gaussianized PIT stream Z_t, with an exact Bayes filter

    omega_{t+1|t} = pi_H + lam * (omega_t - pi_H)                  (predict)
    omega_{t+1}   = omega_{t+1|t} k_H(Z) / [omega_{t+1|t} k_H(Z)
                    + (1 - omega_{t+1|t}) k_L(Z)]                   (update)

and a predictive density for the next Z that is the exact two-component
mixture K_{t+1|t}(z) = (1-omega_{t+1|t}) K_L(z) + omega_{t+1|t} K_H(z).
K_L, K_H are modelled as zero-mean Gaussians (scales s_L, s_H), learned
online via responsibility-weighted EWMA sufficient statistics (a streaming
EM, the same "no batch refitting" discipline as the rest of this codebase).

lam (persistence) and pi_H (stationary high-state probability) are the two
hyperparameters this exact filter needs and doesn't learn on its own. The
session's own repeated lesson (residual_transform, cell_model, the Kalman-
grid) is: don't point-estimate a single hyperparameter online from a noisy
ratio -- hedge a small fixed grid of them, combined by Bayesian likelihood
weighting. Applied here: a small grid of (lam, pi_H) candidates, each
running its own exact filter and online (s_L, s_H) estimate, pooled exactly
the way homogenize.py pools its candidates (every candidate's predictive is
already a Gaussian mixture sharing a common zero-mean reference, so the
pool is the plain union of (weight, scale) pairs -- reuses homogenize.g/logg
directly, no new pooling math needed).
"""
from __future__ import annotations
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import laplace_on_scale as los  # noqa: E402 -- _phi_inv, _clamp01, moments, generators

sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "..", "src"))
from skaters.homogenize import logg, g  # noqa: E402

_EPS = 1e-12


def _clip(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def _phi_pdf(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


# ---------------------------------------------------------------------------
# A single exact two-state candidate: fixed (lam, pi_H), online (sL, sH).
# ---------------------------------------------------------------------------

_S_MIN, _S_MAX = 0.25, 4.0
_VAR_FLOOR = 1e-6


def _init_candidate_state(pi_H: float) -> dict:
    # sL/sH start asymmetric (0.7/1.4, not 1.0/1.0) so "H" consistently means
    # "the higher-variance state" from tick one. With a symmetric start and a
    # symmetric responsibility-weighted EM update there is nothing to break
    # the H/L labeling tie, so independently-run candidates can each settle
    # on an opposite labeling by chance -- individually harmless (each
    # candidate's own predictive density is unaffected by which label it
    # picks), but it destroys the *pooled* omega as a regime diagnostic,
    # since candidates with swapped labels partially cancel when averaged.
    return {
        "omega_pred": pi_H,          # P(H) used to build the *issued* correction
        "sL": 0.7, "sH": 1.4,
        "wL_mass": 1.0, "wL_m2": 0.49,
        "wH_mass": 1.0, "wH_m2": 1.96,
        "n": 0,
    }


def candidate_correction(cfg: dict, d: dict) -> dict:
    """The two-component mixture {"weights", "scales"} this candidate has
    already issued for the current tick -- built from (omega_pred, sL, sH)
    as of the end of the previous update. The identity candidate is frozen
    at a single N(0,1) component forever: it is the "no real regime split
    here" hypothesis, competing on equal footing against the genuine
    two-state candidates rather than something the two-state filter is
    expected to discover by degenerating sL toward sH on its own (a
    persistent-state filter's self-reinforcing feedback loop can hallucinate
    a persistent-looking split out of pure noise -- the classic "spurious
    regime detection" failure of Markov-switching models fit online -- so
    the collapse-to-homogeneous case is handled by honest competition, the
    same NFL-safe hedging idiom as everywhere else in this codebase, not by
    hoping the filter notices on its own)."""
    if cfg.get("is_identity"):
        return {"weights": [1.0], "scales": [1.0]}
    return {"weights": [1.0 - d["omega_pred"], d["omega_pred"]], "scales": [d["sL"], d["sH"]]}


def update_candidate(cfg: dict, d: dict, z: float, halflife: float = 200.0) -> None:
    """Score is done by the caller (via candidate_correction + logg) before
    this runs, matching the score-before-update ordering used everywhere
    else in this codebase. This performs: Bayes filter update given z, then
    responsibility-weighted EWMA update of (sL, sH), then the predict step
    for the *next* tick's omega_pred. The identity candidate has nothing to
    update -- it is frozen by construction."""
    if cfg.get("is_identity"):
        return
    lam, pi_H = cfg["lam"], cfg["pi_H"]
    omega_pred = d["omega_pred"]

    like_H = _phi_pdf(z / d["sH"]) / d["sH"]
    like_L = _phi_pdf(z / d["sL"]) / d["sL"]
    denom = omega_pred * like_H + (1.0 - omega_pred) * like_L
    omega_filt = (omega_pred * like_H / denom) if denom > _EPS else omega_pred

    d["n"] += 1
    a = max(1.0 - 0.5 ** (1.0 / halflife), 1.0 / d["n"])
    z2 = z * z
    d["wH_mass"] = (1.0 - a) * d["wH_mass"] + a * omega_filt
    d["wH_m2"] = (1.0 - a) * d["wH_m2"] + a * omega_filt * z2
    d["wL_mass"] = (1.0 - a) * d["wL_mass"] + a * (1.0 - omega_filt)
    d["wL_m2"] = (1.0 - a) * d["wL_m2"] + a * (1.0 - omega_filt) * z2

    sH2 = _clip(d["wH_m2"] / max(d["wH_mass"], _VAR_FLOOR), _S_MIN * _S_MIN, _S_MAX * _S_MAX)
    sL2 = _clip(d["wL_m2"] / max(d["wL_mass"], _VAR_FLOOR), _S_MIN * _S_MIN, _S_MAX * _S_MAX)

    if sL2 > sH2:
        # Identifiability constraint: "H" always means the currently-larger-
        # variance state. Nothing in the symmetric EM update enforces this on
        # its own -- swap both the variance estimates and their accumulator
        # stats (and correspondingly omega_filt, its complement under a label
        # swap) whenever the raw update would otherwise put sL above sH.
        sL2, sH2 = sH2, sL2
        d["wL_mass"], d["wH_mass"] = d["wH_mass"], d["wL_mass"]
        d["wL_m2"], d["wH_m2"] = d["wH_m2"], d["wL_m2"]
        omega_filt = 1.0 - omega_filt

    d["sH"], d["sL"] = math.sqrt(sH2), math.sqrt(sL2)
    d["omega_pred"] = _clip(pi_H + lam * (omega_filt - pi_H), 0.0, 1.0)


# ---------------------------------------------------------------------------
# Hedged grid: several (lam, pi_H) candidates, pooled by Bayesian weight.
# ---------------------------------------------------------------------------

_GRID = [(lam, pi_H) for lam in (0.0, 0.8, 0.95, 0.99) for pi_H in (0.1, 0.3, 0.5)]
_WEIGHT_DECAY = 0.9999
_LEARNING_RATE = 0.1
_SCORE_CAP = 20.0


def make_candidates(grid=None):
    grid = grid or _GRID
    candidates = [{"lam": 0.0, "pi_H": 0.0, "is_identity": True}]
    candidates += [{"lam": lam, "pi_H": pi_H, "is_identity": False} for lam, pi_H in grid]
    return tuple(candidates)


def _init_state(candidates) -> dict:
    n_other = max(sum(1 for c in candidates if not c["is_identity"]), 1)
    dynamic = []
    for c in candidates:
        log_weight = math.log(n_other) if c["is_identity"] else 0.0
        dynamic.append(dict(_init_candidate_state(c["pi_H"]), log_weight=log_weight))
    return {"dynamic": dynamic, "n": 0}


def hmm_step(z: float, state: dict | None, candidates: tuple) -> tuple[dict, dict]:
    """Score each candidate's already-issued correction against z, update
    its Bayesian weight, update its own (omega, sL, sH) state, then pool
    into the correction issued for the next tick."""
    if state is None:
        state = _init_state(candidates)
    dynamic = state["dynamic"]

    for cfg, d in zip(candidates, dynamic):
        corr = candidate_correction(cfg, d)
        r = logg(z, corr) - los._phi_logpdf(z)
        d["log_weight"] = _WEIGHT_DECAY * d["log_weight"] + _LEARNING_RATE * _clip(r, -_SCORE_CAP, _SCORE_CAP)

    for cfg, d in zip(candidates, dynamic):
        update_candidate(cfg, d, z)

    log_weights = [d["log_weight"] for d in dynamic]
    m = max(log_weights)
    raw = [math.exp(lw - m) for lw in log_weights]
    total = sum(raw)
    omega = [r / total for r in raw]

    weights, scales = [], []
    for cfg, d, w in zip(candidates, dynamic, omega):
        corr = candidate_correction(cfg, d)
        for cw, s in zip(corr["weights"], corr["scales"]):
            weights.append(w * cw)
            scales.append(s)
    state["n"] += 1
    return {"weights": weights, "scales": scales}, state


# ---------------------------------------------------------------------------
# Composition onto a real base skater (z-space mixture, reuses homogenize's
# g/logg for evaluation and the same ZSpaceCorrectedDist-style wrapper).
# ---------------------------------------------------------------------------

class TwoStateHMMDist:
    __slots__ = ("base", "correction", "_qgrid")

    def __init__(self, base, correction: dict):
        self.base = base
        self.correction = correction
        self._qgrid = None

    def _z(self, y: float) -> float:
        return los._phi_inv(los._clamp01(self.base.cdf(y)))

    def _z_cdf(self, z: float) -> float:
        total = 0.0
        for w, s in zip(self.correction["weights"], self.correction["scales"]):
            total += w * los._STD_NORMAL.cdf(z / s)
        return los._clamp01(total)

    def _z_quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        lo, hi = -40.0, 40.0
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            if self._z_cdf(mid) < p:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)

    def cdf(self, y: float) -> float:
        return self._z_cdf(self._z(y))

    def logpdf(self, y: float) -> float:
        z = self._z(y)
        return self.base.logpdf(y) + logg(z, self.correction) - los._phi_logpdf(z)

    def pdf(self, y: float) -> float:
        lp = self.logpdf(y)
        return math.exp(lp) if lp > -700 else 0.0

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        z = self._z_quantile(p, tol=tol, max_iter=max_iter)
        u = los._clamp01(los._STD_NORMAL.cdf(z))
        return self.base.quantile(u, tol=tol, max_iter=max_iter)

    def _qg(self):
        if self._qgrid is None:
            self._qgrid = [self.quantile(p) for p in los._QGRID_P]
        return self._qgrid

    @property
    def mean(self) -> float:
        return sum(self._qg()) / los._QGRID_N

    @property
    def var(self) -> float:
        q = self._qg()
        mu = self.mean
        return sum((x - mu) ** 2 for x in q) / los._QGRID_N

    def crps(self, x: float) -> float:
        q = self._qg()
        total = 0.0
        for p, qi in zip(los._QGRID_P, q):
            ind = 1.0 if x <= qi else 0.0
            total += (qi - x) * (ind - p)
        return 2.0 * total / los._QGRID_N


def laplace_two_state_hmm(base_factory=None, candidates=None):
    from skaters import laplace
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    candidates = candidates or make_candidates()

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "hmm_state": None, "raw": None, "correction": None}
        s = state
        if s["raw"] is not None:
            u = los._clamp01(s["raw"].cdf(y))
            z = los._phi_inv(u)
            s["correction"], s["hmm_state"] = hmm_step(z, s["hmm_state"], candidates)

        base_dists, s["base_state"] = base(y, s["base_state"])
        f_t = base_dists[0]
        s["raw"] = f_t

        corrected = f_t if s["correction"] is None else TwoStateHMMDist(f_t, s["correction"])
        return [corrected], s

    return _skater


# ---------------------------------------------------------------------------
# Synthetic validation
# ---------------------------------------------------------------------------

def _gen_two_state_sv(T, seed, sigma_lo=0.6, sigma_hi=1.8, p_switch=0.02):
    import random
    rng = random.Random(seed)
    regime = 0
    sig = {0: sigma_lo, 1: sigma_hi}
    zs, regimes = [], []
    for _ in range(T):
        if rng.random() < p_switch:
            regime = 1 - regime
        zs.append(sig[regime] * rng.gauss(0.0, 1.0))
        regimes.append(regime)
    return zs, regimes


def _run_zspace(zs, candidates):
    state = None
    scores = []
    for z in zs:
        if state is not None:
            corr = None
        correction, state = hmm_step(z, state, candidates)
    return state


def _pooled_correction(candidates, dynamic):
    log_weights = [d["log_weight"] for d in dynamic]
    m = max(log_weights)
    raw = [math.exp(lw - m) for lw in log_weights]
    total = sum(raw)
    omega_by_cand = [r / total for r in raw]
    weights, scales = [], []
    for cfg, d, w in zip(candidates, dynamic, omega_by_cand):
        corr = candidate_correction(cfg, d)
        for cw, s in zip(corr["weights"], corr["scales"]):
            weights.append(w * cw)
            scales.append(s)
    return {"weights": weights, "scales": scales}, omega_by_cand


def _run_and_score(zs, candidates, warmup, true_regimes=None):
    state = None
    scores, omega_track = [], []
    for t, z in enumerate(zs):
        if state is not None:
            pooled, omega_by_cand = _pooled_correction(candidates, state["dynamic"])
            if t >= warmup:
                scores.append(logg(z, pooled) - los._phi_logpdf(z))
                if true_regimes is not None:
                    omega_H = sum(w * d["omega_pred"] for w, d in zip(omega_by_cand, state["dynamic"]))
                    omega_track.append((omega_H, true_regimes[t]))
        _, state = hmm_step(z, state, candidates)
    return scores, omega_track


def main():
    print("--- synthetic: single exact candidate, iid null ---")
    zs = [los.random.gauss(0.0, 1.0) for _ in range(6000)]
    candidates = make_candidates([(0.9, 0.3)])
    scores, _ = _run_and_score(zs, candidates, warmup=500)
    print(f"  mean delta logL vs phi: {sum(scores)/len(scores):+.4f}")

    print("--- synthetic: hedged grid, two-state SV ---")
    zs, regimes = _gen_two_state_sv(6000, seed=3)
    candidates = make_candidates()
    scores, omega_track = _run_and_score(zs, candidates, warmup=1000, true_regimes=regimes)
    print(f"  mean delta logL vs phi: {sum(scores)/len(scores):+.4f}")
    corr_check = sum(1 for w, r in omega_track if (w > 0.5) == (r == 1)) / len(omega_track)
    print(f"  frac ticks pooled-omega_H>0.5 matches true regime: {corr_check:.3f}")


if __name__ == "__main__":
    main()
