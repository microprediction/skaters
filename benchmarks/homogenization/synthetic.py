"""Synthetic z-stream experiments for the homogenized cell model.

Generators A-D produce z-streams (and, where meaningful, the true latent
regime) and a shared prequential runner scores skaters.homogenization's
cell_model against each. This is the phase-1 go/no-go gate: sections 7+
(the Dist-compatible wrapper, the generic skater primitive, the moving
fence-post) only get built if the pool beats identity on regime-switching
variance (C, D) without losing on iid data (A, B).

Experiments E (mean misspecification) and F (leverage/asymmetry) are
stubbed but not required for this gate -- they scope *later* extensions
(an H_1 candidate, an asymmetric correction), not this one.

Usage: PYTHONPATH=src python benchmarks/homogenization/synthetic.py
"""
from __future__ import annotations
import math
import os
import random
import statistics as st

import cell_model as cm

_HERE = os.path.dirname(os.path.abspath(__file__))
WARMUP_FRAC = 0.3   # fraction of each stream treated as learner warm-up


# ---------------------------------------------------------------------------
# Standard normal cdf/quantile, needed only for the W-coordinate diagnostics
# (cell_model itself never needs these -- it operates purely in z-space).
# ---------------------------------------------------------------------------

def _Phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _Phi_inv(p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
    assert 0.0 < p < 1.0
    lo, hi = -10.0, 10.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if _Phi(mid) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Generators: each returns (zs, regimes) -- regimes is a same-length list of
# floats giving the "true" per-tick variance multiplier where meaningful
# (1.0 throughout for streams with no regime structure).
# ---------------------------------------------------------------------------

def gen_iid_gaussian(T: int, seed: int):
    """Experiment A: the no-regret null. z_t ~iid N(0,1)."""
    rng = random.Random(seed)
    zs = [rng.gauss(0.0, 1.0) for _ in range(T)]
    return zs, [1.0] * T


def gen_static_heavy_tailed(T: int, seed: int, df: float = 4.0):
    """Experiment B: iid Student-t (df), rescaled to unit variance -- static
    heavy tails, no serial dependence. Separates "H_4 can help" from "there
    is H_2 autocorrelation to remove"."""
    rng = random.Random(seed)
    scale = math.sqrt(df / (df - 2.0))
    zs = []
    for _ in range(T):
        g = rng.gauss(0.0, 1.0)
        chi2 = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(int(df)))
        zs.append((g / math.sqrt(chi2 / df)) / scale)
    return zs, [1.0] * T


def gen_two_state_sv(T: int, seed: int, sigma_lo: float = 0.6, sigma_hi: float = 1.8,
                      p_switch: float = 0.02):
    """Experiment C: two-state Markov-switching volatility. z_t = sigma_{y_t}
    * eps_t, y_t a persistent two-state chain (switch probability p_switch
    per tick, so mean regime duration is 1/p_switch ticks)."""
    rng = random.Random(seed)
    y = 0
    sig = {0: sigma_lo, 1: sigma_hi}
    zs, regimes = [], []
    for _ in range(T):
        if rng.random() < p_switch:
            y = 1 - y
        eps = rng.gauss(0.0, 1.0)
        zs.append(sig[y] * eps)
        regimes.append(sig[y] ** 2)
    return zs, regimes


def gen_two_regime_ou(T: int, seed: int, phi_y: float = 0.98,
                       sigma_lo: float = 0.6, sigma_hi: float = 1.8,
                       y0: float | None = None):
    """Experiment D: an OU-driven latent state Y_t (discrete-time AR(1),
    unit stationary variance) modulates volatility continuously through the
    sign/magnitude of Y_t, rather than switching discretely -- the "unresolved
    heterogeneity persists and decays" shape the derivation motivates H_4
    with. y0=None draws Y_0 from its stationary marginal (the "stationary"
    variant); a fixed extreme y0 (e.g. +3) starts deep in the high-vol
    regime (the "nonstationary/biased initial regime" variant), which should
    produce a transient that decays back to the stationary behavior.

    This is a qualitative, not a literal, reproduction of "the" two-regime
    OU derivation (its exact closed form was not specified here) -- it is
    built to have the same qualitative features the experiment asks for:
    persistent latent variance heterogeneity, plus a controllable initial
    transient.
    """
    rng = random.Random(seed)
    y = rng.gauss(0.0, 1.0) if y0 is None else float(y0)
    zs, regimes = [], []
    for _ in range(T):
        frac = 1.0 / (1.0 + math.exp(-y))   # squash Y_t in (0,1)
        sigma2 = sigma_lo ** 2 * (1 - frac) + sigma_hi ** 2 * frac
        eps = rng.gauss(0.0, 1.0)
        zs.append(math.sqrt(sigma2) * eps)
        regimes.append(sigma2)
        y = phi_y * y + math.sqrt(1.0 - phi_y ** 2) * rng.gauss(0.0, 1.0)
    return zs, regimes


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_experiment(zs, true_var, warmup_frac: float = WARMUP_FRAC):
    candidates = cm.make_candidates()
    state = None
    prev_correction = None
    delta_logL, h2_before, h2_after, v_pool = [], [], [], []
    warmup = int(warmup_frac * len(zs))

    for t, z in enumerate(zs):
        if prev_correction is not None:
            delta_logL.append(cm.logg(z, prev_correction) - cm.phi_logpdf(z))
            u = min(max(sum(w * _Phi(z / s) for w, s in
                             zip(prev_correction["weights"], prev_correction["scales"])),
                        1e-12), 1.0 - 1e-12)
            w_t = _Phi_inv(u)
            h2_after.append(w_t * w_t - 1.0)
            h2_before.append(z * z - 1.0)

        correction, state = cm.cell_step(z, state, candidates)
        prev_correction = correction
        if t >= warmup:
            v_pool.append(sum(w * s * s for w, s in zip(correction["weights"], correction["scales"])))

    weights = cm.candidate_weights(state)
    top_idx = max(range(len(candidates)), key=lambda i: weights[i])
    identity_idx = next(i for i, c in enumerate(candidates) if c["is_identity"])

    def _autocorr1(xs):
        if len(xs) < 3:
            return float("nan")
        m = sum(xs) / len(xs)
        num = sum((xs[i] - m) * (xs[i + 1] - m) for i in range(len(xs) - 1))
        den = sum((x - m) ** 2 for x in xs)
        return num / den if den > 0 else float("nan")

    result = {
        "n": len(zs),
        "mean_delta_logL": st.mean(delta_logL[warmup:]),
        "median_delta_logL": st.median(delta_logL[warmup:]),
        "frac_delta_logL_pos": sum(1 for x in delta_logL[warmup:] if x > 0) / len(delta_logL[warmup:]),
        "identity_weight": weights[identity_idx],
        "top_candidate": dict(candidates[top_idx]),
        "top_weight": weights[top_idx],
        "h2_autocorr_before": _autocorr1(h2_before[warmup:]),
        "h2_autocorr_after": _autocorr1(h2_after[warmup:]),
    }
    if any(v != 1.0 for v in true_var):
        # correlate this tick's pooled implied variance with the *next*
        # tick's realized true variance (v_pool[t] is built from data
        # through t, predicting tick t+1's variance -- align accordingly).
        tv_next = true_var[warmup + 1: warmup + 1 + len(v_pool)]
        vp = v_pool[: len(tv_next)]
        if len(vp) > 2 and st.pstdev(vp) > 0 and st.pstdev(tv_next) > 0:
            mv, mt = st.mean(vp), st.mean(tv_next)
            cov = sum((a - mv) * (b - mt) for a, b in zip(vp, tv_next)) / len(vp)
            result["corr_vpool_true_regime"] = cov / (st.pstdev(vp) * st.pstdev(tv_next))
        else:
            result["corr_vpool_true_regime"] = float("nan")
    return result


EXPERIMENTS = {
    "A_iid_gaussian_null": lambda: gen_iid_gaussian(6000, seed=1),
    "B_static_heavy_tailed": lambda: gen_static_heavy_tailed(6000, seed=2),
    "C_two_state_sv": lambda: gen_two_state_sv(6000, seed=3),
    "D_two_regime_ou_stationary": lambda: gen_two_regime_ou(6000, seed=4, y0=None),
    "D_two_regime_ou_biased_init": lambda: gen_two_regime_ou(6000, seed=5, y0=3.0),
}


def main():
    results = {}
    for name, gen in EXPERIMENTS.items():
        zs, true_var = gen()
        r = run_experiment(zs, true_var)
        results[name] = r
        print(f"\n=== {name} (n={r['n']}) ===")
        print(f"  mean dlogL={r['mean_delta_logL']:+.4f}  median={r['median_delta_logL']:+.4f}  "
              f"frac>0={r['frac_delta_logL_pos']:.2f}")
        print(f"  identity weight={r['identity_weight']:.3f}  "
              f"top candidate weight={r['top_weight']:.3f} {r['top_candidate']}")
        print(f"  H2 autocorr: before={r['h2_autocorr_before']:+.4f}  after={r['h2_autocorr_after']:+.4f}")
        if "corr_vpool_true_regime" in r:
            print(f"  corr(v_pool, true next-tick variance)={r['corr_vpool_true_regime']:+.4f}")

    _write_results_md(results)
    print(f"\n[homogenization] wrote {os.path.join(_HERE, 'RESULTS.md')}")


def _write_results_md(results):
    lines = ["# Homogenized cell model: synthetic experiments (phase 1)\n"]
    lines.append("Pure z-space replay, `benchmarks/homogenization/synthetic.py`. "
                  "See `cell_model.py` for the candidate model.\n")
    lines.append("| experiment | mean dlogL | median dlogL | frac>0 | identity wt | top candidate wt | "
                  "H2 autocorr before | after |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, r in results.items():
        lines.append(f"| {name} | {r['mean_delta_logL']:+.4f} | {r['median_delta_logL']:+.4f} | "
                      f"{r['frac_delta_logL_pos']:.2f} | {r['identity_weight']:.3f} | "
                      f"{r['top_weight']:.3f} | {r['h2_autocorr_before']:+.4f} | "
                      f"{r['h2_autocorr_after']:+.4f} |")
    lines.append("")
    for name, r in results.items():
        if "corr_vpool_true_regime" in r:
            lines.append(f"- `{name}`: corr(pooled implied variance, true next-tick variance) = "
                          f"{r['corr_vpool_true_regime']:+.4f}")
    with open(os.path.join(_HERE, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
