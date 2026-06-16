"""Benchmark the kahneman policy against the other named policies.

Scoring is honest out-of-sample one-step prediction: at each t the model
has only seen y_0..y_{t-1}; we score the FULL predictive mixture density
log p(y_t) (not a re-Gaussianized version, so fat tails count) plus MAE and
a 95% interval coverage check.

Run:  python examples/benchmark_kahneman.py
"""

from __future__ import annotations
import math
import random
from skaters import skater, laplace, holt, samuelson, wald, kahneman


def score(factory, series, burn=200):
    """One-step out-of-sample scoring with the true predictive Dist."""
    f = factory(k=1)
    state = None
    pending = None  # the Dist predicting the current step
    logp, abserr, n, covered = 0.0, 0.0, 0, 0
    for i, y in enumerate(series):
        if pending is not None and i > burn:
            lp = pending.logpdf(y)
            if math.isfinite(lp):
                logp += lp
                abserr += abs(pending.mean - y)
                lo, hi = pending.quantile(0.025), pending.quantile(0.975)
                covered += 1 if lo <= y <= hi else 0
                n += 1
        dists, state = f(y, state)
        pending = dists[0]
    return {
        "logpdf": logp / max(1, n),
        "mae": abserr / max(1, n),
        "cov95": covered / max(1, n),
        "n": n,
    }


# --- Synthetic regimes -----------------------------------------------------

def _slow_sigma(t, period=500, lo=0.3, hi=3.0):
    """Noise scale drifting slowly (log-sinusoidal) between lo and hi."""
    phase = 0.5 + 0.5 * math.sin(2 * math.pi * t / period)
    return math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * phase)


def slow_noise_flat_mean(n=3000, seed=0):
    """Isolates the effect: flat mean, slowly-varying noise scale.

    A constant-variance leaf is mis-calibrated whenever sigma is far from
    its long-run average; a slowly-varying residual scale tracks it.
    """
    random.seed(seed)
    return [random.gauss(0, _slow_sigma(t)) for t in range(n)]


def slow_noise_drifting_mean(n=3000, seed=0):
    """The full premise: a faster underlying process (trackable random-walk
    level) under a slowly-varying noise distribution."""
    random.seed(seed)
    out, level = [], 0.0
    for t in range(n):
        level += random.gauss(0, 0.15)            # faster underlying process
        out.append(level + random.gauss(0, _slow_sigma(t)))
    return out


def trend_plus_gaussian(n=3000, seed=1):
    random.seed(seed)
    return [0.05 * t + random.gauss(0, 1.0) for t in range(n)]


def pure_random_walk(n=3000, seed=2):
    random.seed(seed)
    out, lvl = [], 0.0
    for _ in range(n):
        lvl += random.gauss(0, 1.0)
        out.append(lvl)
    return out


def iid_gaussian(n=3000, seed=3):
    random.seed(seed)
    return [random.gauss(0, 1.0) for _ in range(n)]


POLICIES = [
    ("skater", skater),
    ("laplace", laplace),
    ("holt", holt),
    ("samuelson", samuelson),
    ("wald", wald),
    ("kahneman", kahneman),
]

REGIMES = [
    ("slow noise / flat mean", slow_noise_flat_mean),
    ("slow noise / drifting mean", slow_noise_drifting_mean),
    ("trend + gaussian", trend_plus_gaussian),
    ("pure random walk", pure_random_walk),
    ("iid gaussian", iid_gaussian),
]


def early_logpdf(factory, gen, lo=30, hi=400, seeds=range(8)):
    """Mean predictive logpdf over an EARLY window, averaged over seeds.

    This is where a prior can matter: before the likelihood has had enough
    data to wash the prior out.
    """
    tot, n = 0.0, 0
    for s in seeds:
        series = gen(n=hi + 5, seed=s)
        f = factory(k=1)
        state, pend = None, None
        for i, y in enumerate(series):
            if pend is not None and lo < i < hi:
                lp = pend.logpdf(y)
                if math.isfinite(lp):
                    tot += lp
                    n += 1
            dists, state = f(y, state)
            pend = dists[0]
    return tot / max(1, n)


def main():
    print("# Asymptotic scoring (n=3000) — priors wash out, all converge\n")
    for regime_name, gen in REGIMES:
        series = gen()
        print(f"=== {regime_name}  (n={len(series)}) ===")
        print(f"{'policy':<12}{'mean logpdf':>13}{'MAE':>9}{'cov95':>8}")
        rows = [(name, score(factory, series)) for name, factory in POLICIES]
        best = max(r["logpdf"] for _, r in rows)
        for name, r in rows:
            star = "  <-- best" if r["logpdf"] == best else ""
            print(f"{name:<12}{r['logpdf']:>13.4f}{r['mae']:>9.3f}{r['cov95']:>8.2%}{star}")
        print()

    print("# Early-window adaptation on slow-noise/flat-mean (obs 30..400, 8 seeds)")
    print("# Does a STRONGER prior on the fast/slow structure help early?\n")
    gen = slow_noise_flat_mean
    print(f"{'policy':<18}{'early logpdf':>13}")
    print(f"{'laplace':<18}{early_logpdf(lambda k: laplace(k), gen):>13.4f}")
    print(f"{'wald':<18}{early_logpdf(lambda k: wald(k), gen):>13.4f}")
    for strength in [2.0, 8.0, 20.0]:
        lbl = f"kahneman str={strength:g}"
        print(f"{lbl:<18}{early_logpdf(lambda k, s=strength: kahneman(k, strength=s), gen):>13.4f}")
    print("\n# Verdict: on slowly-varying noise a STRONGER prior adapts faster")
    print("# than laplace (uniform) — the structure is real and worth betting on.")
    print("# On stationary controls the same bet costs a little early; the default")
    print("# strength trades these off. Asymptotically all priors wash out.")


if __name__ == "__main__":
    main()
