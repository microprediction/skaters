# laplace vs. ADAM

**Opponent.** `smooth::adam` (Svetunkov) — Augmented Dynamic Adaptive Model, a
unified state-space engine (ETS + ARIMA + regression) estimated by **maximum
likelihood under an explicitly assumed distribution** (Normal, Laplace, S,
Generalised Normal, …). `ADAM-R@{5,25,100}`, scored on its **real predictive
quantiles**, not a Gaussian band.

**Why it matters.** ADAM is the strongest classical *distributional* forecaster
in R and the closest philosophical cousin to `laplace` — likelihood-native,
possibly heavy-tailed. This is the most informative single matchup: two
principled distributional forecasters, one online and dependency-free, one a full
state-space MLE. If `laplace` wins here on log-likelihood, that's the headline.

**Reproduce.**
```bash
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-adam R@5 R@25 R@100
# (R@* runs the whole R stack; ADAM-R@* is the row that matters here)
```

**Result** _(N=120 R-covered, 167 continuous; still growing overnight. R@25.)_

laplace **win-rate**:

| method | CRPS all/cont | LL all/cont | N |
|---|---|---|---|
| ADAM-R@25 | 82/81% | **96/95%** | 120 |

Scored on ADAM's **real predictive quantiles**, not a Gaussian band. laplace wins ~96%
on log-likelihood and ~82% on CRPS. ADAM is the strongest classical distributional
forecaster in the field, so this is the most meaningful of the R matchups.
