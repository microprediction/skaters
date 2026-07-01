# laplace vs. AutoARIMA

**Opponent.** Hyndman's `auto.arima` — the default automatic ARIMA. Two forms:
the **real R** `forecast::auto.arima` (`auto.arima-R@{5,25,100}`) and Nixtla's
**Python port** `statsforecast.AutoARIMA` (`AutoARIMA@{5,25,100}`). Both emit an
exactly-Gaussian one-step predictive, so both are scored on log-likelihood.

**Why it matters.** ARIMA is *the* classical baseline and the thing most papers
compare against. If `laplace` doesn't beat auto.arima on held-out likelihood, it
has no story. The `@cadence` sweep also shows the accuracy/speed tradeoff:
auto.arima reuses the fitted orders between refits, so `@100` is far cheaper than
`@5` — plot both against `laplace`'s online O(1)/step.

**Reproduce.**
```bash
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-autoarima R@5 R@25 R@100 statsforecast@5 statsforecast@25 statsforecast@100
```

**Result** _(provisional — N=44, 39 continuous; the first-scored cached slice, which
is rates/FX/credit-heavy and not yet representative; R@25 cadence)._

laplace **win-rate** (fraction of series where laplace scores better):

| method | CRPS all/cont | LL all/cont | N |
|---|---|---|---|
| auto.arima-R@25 | 55/51% | **82/79%** | 44 |

laplace beats the *real R* auto.arima on **log-likelihood** (82%) while it's a near-tie
on **CRPS** (55%) — the CRPS-vs-likelihood distinction in a single row: a method can
match the density's spread yet lose on the density itself. Full-universe run and the
Python `AutoARIMA@*` port (same refit axis) still pending.
