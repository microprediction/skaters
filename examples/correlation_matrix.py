"""Correlation matrix of policy performance across synthetic series.

Generates diverse synthetic time series, runs all policies on each,
and computes the correlation matrix of logpdf scores across series.

High correlation between two policies means they succeed and fail
on the same series types — they're redundant. Low or negative
correlation means they complement each other.

Usage:
    uv run python examples/correlation_matrix.py
"""

import math
import random
import sys


def generate_series(n: int = 2000) -> dict[str, list[float]]:
    """Generate a suite of synthetic series with different properties."""
    series = {}

    # --- Stationary ---
    random.seed(1)
    series["white_noise"] = [random.gauss(0, 1) for _ in range(n)]

    random.seed(2)
    series["ar1_mild"] = _ar1(n, phi=0.5, sigma=1.0, seed=2)

    random.seed(3)
    series["ar1_strong"] = _ar1(n, phi=0.95, sigma=1.0, seed=3)

    random.seed(4)
    series["ar1_negative"] = _ar1(n, phi=-0.5, sigma=1.0, seed=4)

    random.seed(5)
    series["ar2_oscillating"] = _ar2(n, phi1=0.5, phi2=-0.3, sigma=1.0, seed=5)

    # --- Random walk variants ---
    random.seed(6)
    series["random_walk"] = _random_walk(n, sigma=1.0, seed=6)

    random.seed(7)
    series["rw_small_sigma"] = _random_walk(n, sigma=0.1, seed=7)

    random.seed(8)
    series["rw_large_sigma"] = _random_walk(n, sigma=5.0, seed=8)

    # --- Drift ---
    random.seed(9)
    series["rw_drift_small"] = _random_walk(n, drift=0.05, sigma=1.0, seed=9)

    random.seed(10)
    series["rw_drift_large"] = _random_walk(n, drift=0.5, sigma=1.0, seed=10)

    random.seed(11)
    series["rw_drift_negative"] = _random_walk(n, drift=-0.3, sigma=1.0, seed=11)

    # --- Trend ---
    random.seed(12)
    series["linear_trend"] = [0.1 * t + random.gauss(0, 1) for t in range(n)]

    random.seed(13)
    series["quadratic_trend"] = [0.001 * t * t + random.gauss(0, 1) for t in range(n)]

    # --- Volatility ---
    random.seed(14)
    series["garch_like"] = _garch_series(n, seed=14)

    random.seed(15)
    series["regime_vol"] = _regime_volatility(n, seed=15)

    # --- Periodic ---
    random.seed(16)
    series["seasonal_7"] = [10 * math.sin(2 * math.pi * t / 7) + random.gauss(0, 1) for t in range(n)]

    random.seed(17)
    series["seasonal_12"] = [5 * math.sin(2 * math.pi * t / 12) + random.gauss(0, 2) for t in range(n)]

    # --- Regime change ---
    random.seed(18)
    series["level_shift"] = _level_shift(n, seed=18)

    random.seed(19)
    series["multiple_regimes"] = _multiple_regimes(n, seed=19)

    # --- Correlated noise ---
    random.seed(20)
    series["const_ar_noise"] = _const_plus_ar_noise(n, rho=0.8, seed=20)

    random.seed(21)
    series["rw_ar_noise"] = _rw_plus_ar_noise(n, rho=0.7, seed=21)

    # --- Mixed ---
    random.seed(22)
    series["trend_plus_seasonal"] = [
        0.05 * t + 3 * math.sin(2 * math.pi * t / 7) + random.gauss(0, 0.5)
        for t in range(n)
    ]

    random.seed(23)
    series["mean_revert_garch"] = _mean_revert_garch(n, seed=23)

    # --- Constant (pathological) ---
    series["constant"] = [42.0] * n

    return series


def _ar1(n, phi, sigma, seed):
    random.seed(seed)
    y = [0.0]
    for _ in range(n - 1):
        y.append(phi * y[-1] + random.gauss(0, sigma))
    return y


def _ar2(n, phi1, phi2, sigma, seed):
    random.seed(seed)
    y = [0.0, 0.0]
    for _ in range(n - 2):
        y.append(phi1 * y[-1] + phi2 * y[-2] + random.gauss(0, sigma))
    return y


def _random_walk(n, drift=0.0, sigma=1.0, seed=42):
    random.seed(seed)
    y = [0.0]
    for _ in range(n - 1):
        y.append(y[-1] + drift + random.gauss(0, sigma))
    return y


def _garch_series(n, seed):
    random.seed(seed)
    y = [0.0]
    var = 1.0
    for _ in range(n - 1):
        var = 0.05 + 0.1 * y[-1] ** 2 + 0.85 * var
        y.append(random.gauss(0, math.sqrt(max(var, 0.01))))
    return y


def _regime_volatility(n, seed):
    random.seed(seed)
    y = []
    for t in range(n):
        sigma = 0.5 if t < n // 2 else 5.0
        y.append(random.gauss(0, sigma))
    return y


def _level_shift(n, seed):
    random.seed(seed)
    y = []
    for t in range(n):
        level = 0.0 if t < n // 2 else 10.0
        y.append(level + random.gauss(0, 1))
    return y


def _multiple_regimes(n, seed):
    random.seed(seed)
    y = []
    for t in range(n):
        quarter = (t * 4) // n
        levels = [0, 20, -10, 5]
        y.append(levels[quarter] + random.gauss(0, 2))
    return y


def _const_plus_ar_noise(n, rho, seed):
    random.seed(seed)
    e = [0.0]
    for _ in range(n - 1):
        e.append(rho * e[-1] + random.gauss(0, 1))
    return [10.0 + ei for ei in e]


def _rw_plus_ar_noise(n, rho, seed):
    random.seed(seed)
    rw = [0.0]
    for _ in range(n - 1):
        rw.append(rw[-1] + random.gauss(0, 0.5))
    random.seed(seed + 1000)
    e = [0.0]
    for _ in range(n - 1):
        e.append(rho * e[-1] + random.gauss(0, 1))
    return [r + ei for r, ei in zip(rw, e)]


def _mean_revert_garch(n, seed):
    random.seed(seed)
    y = [0.0]
    var = 1.0
    for _ in range(n - 1):
        var = 0.05 + 0.1 * y[-1] ** 2 + 0.85 * var
        y.append(0.9 * y[-1] + random.gauss(0, math.sqrt(max(var, 0.01))))
    return y


def run_policy(factory, series, burn=300):
    """Run a policy on a series, return mean logpdf after burn-in."""
    from skaters.dist import Dist
    f = factory(k=1)
    state = None
    prev_mean = prev_std = None
    logpdfs = []
    for i, y in enumerate(series):
        dists, state = f(y, state)
        if i > burn and prev_mean is not None and prev_std and prev_std > 0:
            lp = Dist.gaussian(prev_mean, prev_std).logpdf(y)
            if math.isfinite(lp):
                logpdfs.append(lp)
        prev_mean = dists[0].mean
        prev_std = dists[0].std
    return sum(logpdfs) / len(logpdfs) if logpdfs else float("-inf")


def main():
    from skaters.api import (
        bachelier, samuelson, yule, brown, holt,
        hosking, laplace, wald, dantzig, skater,
    )

    policies = {
        "bachelier": bachelier,
        "samuelson": samuelson,
        "yule": yule,
        "brown": brown,
        "holt": holt,
        "hosking": hosking,
        "laplace": laplace,
        "wald": wald,
        "dantzig": dantzig,
    }

    all_series = generate_series(n=2000)
    series_names = sorted(all_series.keys())
    policy_names = list(policies.keys())

    print(f"Running {len(policy_names)} policies on {len(series_names)} series...\n")

    # scores[policy][series] = mean logpdf
    scores = {p: {} for p in policy_names}
    for si, sname in enumerate(series_names):
        sys.stdout.write(f"\r  Series {si+1}/{len(series_names)}: {sname:<30}")
        sys.stdout.flush()
        for pname in policy_names:
            scores[pname][sname] = run_policy(policies[pname], all_series[sname])

    print("\n")

    # --- Print score table ---
    print("=" * 90)
    print("  MEAN LOGPDF BY POLICY AND SERIES")
    print("=" * 90)
    header = f"{'Series':<25}" + "".join(f"{p:>9}" for p in policy_names)
    print(header)
    print("-" * len(header))
    for sname in series_names:
        row = f"{sname:<25}"
        vals = [scores[p][sname] for p in policy_names]
        best = max(vals)
        for p in policy_names:
            v = scores[p][sname]
            marker = " *" if abs(v - best) < 0.001 else "  "
            row += f"{v:7.3f}{marker}"
        print(row)

    # --- Rank table ---
    print("\n")
    print("=" * 90)
    print("  RANK BY POLICY (1=best)")
    print("=" * 90)
    header = f"{'Series':<25}" + "".join(f"{p:>9}" for p in policy_names)
    print(header)
    print("-" * len(header))
    rank_sums = {p: 0 for p in policy_names}
    for sname in series_names:
        vals = [(scores[p][sname], p) for p in policy_names]
        vals.sort(reverse=True)
        ranks = {p: r + 1 for r, (_, p) in enumerate(vals)}
        row = f"{sname:<25}"
        for p in policy_names:
            row += f"{ranks[p]:9d}"
            rank_sums[p] += ranks[p]
        print(row)
    print("-" * len(header))
    row = f"{'MEAN RANK':<25}"
    for p in policy_names:
        row += f"{rank_sums[p]/len(series_names):9.1f}"
    print(row)

    # --- Correlation matrix ---
    print("\n")
    print("=" * 90)
    print("  CORRELATION MATRIX (logpdf across series)")
    print("=" * 90)

    # Build vectors (exclude series where any policy got -inf)
    valid_series = [s for s in series_names
                    if all(math.isfinite(scores[p][s]) for p in policy_names)]
    print(f"  (Using {len(valid_series)}/{len(series_names)} series with all-finite scores)\n")
    vectors = {}
    for p in policy_names:
        vectors[p] = [scores[p][s] for s in valid_series]

    def pearson(a, b):
        n = len(a)
        ma = sum(a) / n
        mb = sum(b) / n
        cov = sum((ai - ma) * (bi - mb) for ai, bi in zip(a, b)) / n
        sa = math.sqrt(sum((ai - ma) ** 2 for ai in a) / n)
        sb = math.sqrt(sum((bi - mb) ** 2 for bi in b) / n)
        if sa < 1e-12 or sb < 1e-12:
            return 0.0
        return cov / (sa * sb)

    header = f"{'':>12}" + "".join(f"{p:>10}" for p in policy_names)
    print(header)
    for p1 in policy_names:
        row = f"{p1:>12}"
        for p2 in policy_names:
            r = pearson(vectors[p1], vectors[p2])
            row += f"{r:10.3f}"
        print(row)

    # --- Summary ---
    print("\n")
    print("=" * 90)
    print("  INTERPRETATION")
    print("=" * 90)
    print("  High correlation (>0.95): policies are redundant")
    print("  Moderate correlation (0.7-0.95): similar but not identical")
    print("  Low correlation (<0.7): complementary")
    print("  Negative correlation: inversely specialized")


if __name__ == "__main__":
    main()
