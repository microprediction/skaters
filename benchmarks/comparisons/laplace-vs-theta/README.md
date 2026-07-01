# laplace vs. Theta

**Opponent.** `forecast::thetaf` — the Theta method, winner of the M3
competition and still a notoriously hard-to-beat, near-free baseline. Gaussian
one-step predictive (`Theta-R@*`), scored on log-likelihood. (Theta refits every
step regardless, so its cadence line is near-flat — a single honest point.)

**Why it matters.** The "simple thing that just works." A distributional
forecaster that can't beat Theta on likelihood is over-engineered. This is the
sanity check every new method should pass first.

**Reproduce.**
```bash
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-theta R@25
```

**Result** _(provisional — N=44, 39 continuous; first-scored cached slice; R@25)._

laplace **win-rate**:

| method | CRPS all/cont | LL all/cont | N |
|---|---|---|---|
| Theta-R@25 | 68/67% | **91/90%** | 44 |

laplace clears the M3-winner sanity check — 91% on log-likelihood — while Theta stays
the most CRPS-competitive of the cheap baselines (68%). Passing this is the minimum bar
for a new distributional forecaster; laplace passes comfortably on the density metric.
