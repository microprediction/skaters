# laplace vs. CSP (Conformal Seasonal Pools)

**Opponent.** CSP — Conformal Seasonal Pools (Manokhin, arXiv:2605.03789), a
training-free sampler that mixes same-season empirical draws with signed residual
draws around a seasonal-naive forecast. `CSP` and `CSP-adaptive`. Pure numpy, zero
deps. We KDE-smooth its sample pool into a `Dist` and score it on **both**
log-likelihood and CRPS — a CRPS-tuned method doesn't get to duck the density
test here.

**Why it matters.** CSP is pitched on strongly-seasonal multi-series data
(electricity, traffic) and on **CRPS**. On daily FRED *change*-series the weekly
seasonal signal is weak, so this is partly off CSP's home turf — frame it fairly:
report where it's competitive on CRPS and where the empirical/thin tails cost it
on log-likelihood. Season period defaults to weekly (`BENCH_CSP_M=7`).

**Reproduce.**
```bash
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-csp CSP
```

**Result** _(N=194, 167 continuous; still growing overnight; weekly season.)_

laplace **win-rate**:

| method | CRPS all/cont | LL all/cont | N |
|---|---|---|---|
| CSP | 100/100% | 99/99% | 194 |
| CSP-adaptive | 100/100% | 99/99% | 194 |

A clean sweep on both metrics — but read it fairly: daily FRED *change*-series has only a
weak weekly signal, so CSP is off the strongly-seasonal turf (electricity/traffic) it was
built for. The honest claim is narrow: **on non-seasonal economic change-series, seasonal
pooling has nothing to add**, and its empirical/thin tails cost it badly on log-likelihood.
A seasonal-heavy universe would be the fair home-turf rematch.
