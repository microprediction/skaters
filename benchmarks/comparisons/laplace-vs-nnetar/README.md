# laplace vs. NNETAR

**Opponent.** `forecast::nnetar` — a feed-forward neural-network autoregression
with **simulated** prediction intervals, so its one-step predictive is genuinely
non-Gaussian; scored on its real quantiles (`nnetar-R@{5,25,100}`).

**Why it matters.** A nonlinear, "small neural net" opponent with no clean Python
equivalent in the existing harness — a different failure mode from the linear
ARIMA/ETS family. Tests whether `laplace`'s transform-ensemble captures
nonlinearity that a black-box net would otherwise claim.

**Reproduce.**
```bash
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-nnetar R@5 R@25 R@100
```

**Result** _(provisional — N=44, 39 continuous; first-scored cached slice; R@25)._

laplace **win-rate**:

| method | CRPS all/cont | LL all/cont | N |
|---|---|---|---|
| nnetar-R@25 | 82/82% | **98/97%** | 44 |

Scored on nnetar's **simulated (non-Gaussian) quantiles**. laplace wins ~98% on
log-likelihood — the transform-ensemble captures the structure the neural AR reaches for,
at O(1)/step and zero dependencies rather than a per-step 400-path simulation.
