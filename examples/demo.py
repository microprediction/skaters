"""Demo: compare skater configurations on synthetic series."""

import random
import math

from skaters.ema import ema
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize
from skaters.ensemble import precision_weighted_ensemble
from skaters.calibrated import calibrated_envelope
from skaters.api import ensemble


def mae(errors):
    return sum(abs(e) for e in errors) / len(errors)


def run_comparison(name, series, models, k=1, burn=50):
    """Run all models on a series, report MAE and coverage."""
    states = {n: None for n in models}
    errors = {n: [] for n in models}
    coverage = {n: [] for n in models}

    for i, y in enumerate(series):
        for n, f in models.items():
            out, states[n] = f(y, states[n])

            # Determine if this is an envelope (dict output) or raw skater (list)
            if isinstance(out, dict):
                pred = out["mean"][0]
                std = out["std"][0]
            else:
                pred = out[0]
                std = None

            if i > burn:
                errors[n].append(pred - y)
                if std is not None and math.isfinite(std) and std > 0:
                    coverage[n].append(1 if abs(pred - y) <= std else 0)

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  {len(series)} observations, k={k}, burn-in={burn}")
    print(f"{'='*60}")
    print(f"  {'Model':<40} {'MAE':>8} {'Coverage':>10}")
    print(f"  {'-'*40} {'-'*8} {'-'*10}")
    for n in models:
        m = mae(errors[n])
        if coverage[n]:
            cov = sum(coverage[n]) / len(coverage[n])
            print(f"  {n:<40} {m:8.4f} {cov:9.1%}")
        else:
            print(f"  {n:<40} {m:8.4f}       n/a")
    print()


def main():
    random.seed(42)

    # --- Series 1: Random walk with drift ---
    print("\n" + "#" * 60)
    print("  SERIES 1: Random walk with drift")
    print("#" * 60)
    rw = [0.0]
    for _ in range(999):
        rw.append(rw[-1] + 0.3 + random.gauss(0, 1))

    k = 1
    run_comparison("Random walk + drift", rw, {
        "plain EMA(0.1)": ema(alpha=0.1, k=k),
        "plain EMA(0.3)": ema(alpha=0.3, k=k),
        "diff + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), difference(), k=k),
        "diff + EMA(0.3)": conjugate(ema(alpha=0.3, k=k), difference(), k=k),
        "frac(0.3) + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.3), k=k),
        "std + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), standardize(), k=k),
        "diff + ensemble": conjugate(ensemble(k=k), difference(), k=k),
        "ensemble (no transform)": ensemble(k=k),
    }, k=k)

    # --- Series 2: Mean-reverting (Ornstein-Uhlenbeck) ---
    print("#" * 60)
    print("  SERIES 2: Mean-reverting (OU process)")
    print("#" * 60)
    ou = [0.0]
    for _ in range(999):
        ou.append(ou[-1] * 0.95 + random.gauss(0, 1))

    run_comparison("Mean-reverting (OU)", ou, {
        "plain EMA(0.1)": ema(alpha=0.1, k=k),
        "plain EMA(0.3)": ema(alpha=0.3, k=k),
        "diff + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), difference(), k=k),
        "frac(0.4) + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.4), k=k),
        "ensemble (no transform)": ensemble(k=k),
        "diff + ensemble": conjugate(ensemble(k=k), difference(), k=k),
    }, k=k)

    # --- Series 3: Regime change ---
    print("#" * 60)
    print("  SERIES 3: Regime change (level shift at t=500)")
    print("#" * 60)
    regime = []
    for i in range(1000):
        level = 10.0 if i < 500 else 50.0
        regime.append(level + random.gauss(0, 2))

    run_comparison("Regime change", regime, {
        "plain EMA(0.1)": ema(alpha=0.1, k=k),
        "plain EMA(0.3)": ema(alpha=0.3, k=k),
        "diff + EMA(0.3)": conjugate(ema(alpha=0.3, k=k), difference(), k=k),
        "std + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), standardize(), k=k),
        "ensemble (no transform)": ensemble(k=k),
    }, k=k)

    # --- Series 4: Composing transforms (chain) ---
    print("#" * 60)
    print("  SERIES 4: Trending + heteroskedastic noise")
    print("#" * 60)
    hetero = []
    level = 0.0
    for i in range(1000):
        level += 0.1
        noise_scale = 1.0 + 0.01 * i  # growing volatility
        hetero.append(level + random.gauss(0, noise_scale))

    run_comparison("Trending + heteroskedastic", hetero, {
        "plain EMA(0.1)": ema(alpha=0.1, k=k),
        "diff + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), difference(), k=k),
        "std + diff + EMA(0.1)": conjugate(
            conjugate(ema(alpha=0.1, k=k), difference(), k=k),
            standardize(alpha=0.01),
            k=k,
        ),
        "ensemble": ensemble(k=k),
        "diff + ensemble": conjugate(ensemble(k=k), difference(), k=k),
    }, k=k)

    # --- Series 5: Multi-step prediction ---
    print("#" * 60)
    print("  SERIES 5: Multi-step (k=5) on random walk + drift")
    print("#" * 60)
    k = 5
    run_comparison("Random walk + drift (k=5)", rw, {
        "plain EMA(0.1)": ema(alpha=0.1, k=k),
        "diff + EMA(0.1)": conjugate(ema(alpha=0.1, k=k), difference(), k=k),
        "diff + ensemble": conjugate(ensemble(k=k), difference(), k=k),
        "frac(0.3) + ensemble": conjugate(ensemble(k=k), fractional_difference(d=0.3), k=k),
    }, k=k)

    # --- Calibrated envelope demo ---
    print("#" * 60)
    print("  CALIBRATED ENVELOPE: coverage check on OU process")
    print("#" * 60)
    k = 1
    run_comparison("OU with calibrated envelope", ou, {
        "calibrated(ensemble)": calibrated_envelope(ensemble(k=k), k=k),
        "calibrated(diff+ens)": calibrated_envelope(
            conjugate(ensemble(k=k), difference(), k=k), k=k
        ),
    }, k=k)

    # --- Meta-ensemble: let transforms compete ---
    print("#" * 60)
    print("  META-ENSEMBLE: transforms compete via precision weighting")
    print("#" * 60)
    meta = precision_weighted_ensemble([
        ema(alpha=0.1, k=1),
        conjugate(ema(alpha=0.1, k=1), difference(), k=1),
        conjugate(ema(alpha=0.1, k=1), fractional_difference(d=0.3), k=1),
        conjugate(ema(alpha=0.1, k=1), standardize(), k=1),
        ensemble(k=1),
        conjugate(ensemble(k=1), difference(), k=1),
    ], k=1)

    run_comparison("Random walk + drift (meta-ensemble)", rw, {
        "plain EMA(0.1)": ema(alpha=0.1, k=1),
        "ensemble": ensemble(k=1),
        "diff + ensemble": conjugate(ensemble(k=1), difference(), k=1),
        "META-ENSEMBLE (6 models)": meta,
    }, k=1)


if __name__ == "__main__":
    main()
