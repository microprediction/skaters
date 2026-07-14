"""Pre-registered analysis for the PYMC-Forecast sandwich study.

Statement: benchmarks/preregistrations/2026-07-14-pymc-forecast-sandwich.md.
H1-H4: two-sided exact binomial sign tests, alpha 0.05, ties as half-wins;
family-weighted win rates alongside. The convergence measure of H3 (median
absolute gap of sand vs raw against laplace) is descriptive.

Usage: ~/.venvs/skaters-pymc/bin/python benchmarks/pymc_forecast_analysis.py
"""
import csv
import os

import numpy as np
from scipy import stats

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "results_pymc_forecast_sandwich.csv")
UNIVERSE = os.path.join(_HERE, "preregistrations", "tabfm_wide_universe.txt")


def load():
    by = {}
    for r in csv.DictReader(open(OUT)):
        by.setdefault(r["series"], {})[r["method"]] = float(r["logpdf"])
    fam = {}
    for line in open(UNIVERSE):
        if line.startswith("#"):
            continue
        p = line.split("\t")
        fam[p[0]] = p[2]
    return by, fam


def sign_test(diffs):
    """Two-sided exact binomial with ties as half-wins."""
    wins = sum(1 for d in diffs if d > 0) + 0.5 * sum(1 for d in diffs if d == 0)
    n = len(diffs)
    k = int(round(wins))
    p = stats.binomtest(k, n, 0.5).pvalue
    return wins, n, p


def family_rate(diffs_by_series, fam):
    """One vote per FRED family: a family's vote is its mean sign."""
    votes = {}
    for s, d in diffs_by_series.items():
        votes.setdefault(fam[s], []).append(np.sign(d))
    per = [np.mean(v) for v in votes.values()]
    wins = sum(1 for v in per if v > 0) + 0.5 * sum(1 for v in per if v == 0)
    return 100.0 * wins / len(per), len(per)


def main():
    by, fam = load()
    full = {s: d for s, d in by.items()
            if all(a in d for a in ("laplace", "raw", "sand", "solo", "hier"))}
    print(f"{len(full)} series with all five arms\n")
    tests = [
        ("H1 raw:      laplace > raw", "laplace", "raw"),
        ("H2 coords:   sand > raw", "sand", "raw"),
        ("H3 converge: laplace > sand", "laplace", "sand"),
        ("H4 pooling:  hier > solo", "hier", "solo"),
    ]
    for label, a, b in tests:
        diffs = {s: d[a] - d[b] for s, d in full.items()}
        wins, n, p = sign_test(list(diffs.values()))
        fr, nf = family_rate(diffs, fam)
        med = float(np.median(list(diffs.values())))
        print(f"{label:32s} wins {wins:5.1f}/{n} ({100 * wins / n:.0f}%), "
              f"median {med:+.4f}, p={p:.2e}; "
              f"family-weighted {fr:.0f}% of {nf}")
    lap_sand = [abs(d["sand"] - d["laplace"]) for d in full.values()]
    lap_raw = [abs(d["raw"] - d["laplace"]) for d in full.values()]
    print(f"\nH3 convergence measure (descriptive): median |sand-laplace| "
          f"{np.median(lap_sand):.4f} vs median |raw-laplace| "
          f"{np.median(lap_raw):.4f}")


if __name__ == "__main__":
    main()
