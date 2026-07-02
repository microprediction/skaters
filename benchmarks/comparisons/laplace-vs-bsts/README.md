# laplace vs. BSTS

**Opponent.** `bsts` (Scott / Google) — Bayesian structural time series. A
local-level state-space model fit by MCMC each step; the one-step **posterior
predictive draws** become sample quantiles, scored on their real (non-Gaussian)
shape (`bsts-R@25`). No online update — a fresh short MCMC per step — so it's the
most expensive opponent per series and runs at a tiny budget.

**Why it matters.** The Bayesian gold standard for *honest* uncertainty: the
predictive is a genuine posterior, not a plug-in Gaussian. If laplace beats a full
posterior-predictive on held-out log-likelihood, that's a strong statement about
calibration, not just point accuracy.

**Result** _(N=119 R-covered, 167 continuous; R@25; scored before `bsts-R` was
skipped for the throughput sweep)._

laplace **win-rate**:

| method | CRPS all/cont | LL all/cont | N |
|---|---|---|---|
| bsts-R@25 | 80/79% | **97/97%** | 119 |

laplace wins ~97% on log-likelihood against the full Bayesian posterior-predictive —
at O(1)/step and zero dependencies versus per-step MCMC.

**Reproduce.** bsts is slow (fresh MCMC every step). Run it at a small budget and do
*not* skip it:
```bash
BENCH_R_MAX=30 BENCH_BSTS_NITER=300 PYTHONPATH=src \
    python benchmarks/comparisons/run_comparison.py laplace-vs-bsts R@25
```
(The overnight throughput sweep sets `BENCH_R_SKIP=bsts-R`, so bsts only accrues in
dedicated small-N runs like this one.)
