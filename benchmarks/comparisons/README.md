# comparisons — laplace vs. one opponent at a time

Head-to-head slices of the *same* `sota` study (one FRED loader, one `Dist`
scorer, one rolling one-step protocol — see `../README.md`), each isolated to
**laplace vs. a single opponent** so the story is legible: what is X, why does it
matter, and does `laplace` beat it on held-out **log-likelihood** and **CRPS**.

Each subfolder is one matchup:

| folder | opponent(s) | what it tests |
|---|---|---|
| `laplace-vs-autoarima/` | `auto.arima-R@*`, `AutoARIMA@*` (statsforecast) | the real Hyndman R auto.arima *and* its Python port, across refit cadences |
| `laplace-vs-adam/` | `ADAM-R@*` | Svetunkov's ADAM — the strongest classical *distributional* forecaster |
| `laplace-vs-theta/` | `Theta-R@*` | the M3 winner; cheap, hard to beat |
| `laplace-vs-nnetar/` | `nnetar-R@*` | a nonlinear (neural AR) opponent with no clean Python twin |
| `laplace-vs-garch/` | `GARCH-t`, `GARCH-t-R@*` | heavy-tail volatility SOTA (its home turf is price/returns) |
| `laplace-vs-bsts/` | `bsts-R@*` | Bayesian structural time series — full posterior predictive |
| `laplace-vs-csp/` | `CSP`, `CSP-adaptive` | training-free Conformal Seasonal Pools (arXiv:2605.03789) |

## Reproduce a matchup

```bash
# laplace vs the real R auto.arima at three refit cadences
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-autoarima R@5 R@25 R@100
```

`run_comparison.py` restricts the `sota` opponent set to laplace + the names you
pass (`STUDY_ONLY`) and writes to `comparisons/<slug>/results.csv`
(`STUDY_RESULTS`). It scores nothing new — it's the one harness, one slice. Paste
the printed summary into that folder's `README.md` under **Result**.

R opponents need R installed (`install.packages(c("forecast","smooth","rugarch","bsts"))`);
if `Rscript` is absent they simply drop out. Budgets (`BENCH_R_MAX`, `BENCH_SF_MAX`,
…) and cadences (`BENCH_R_REFITS`, `BENCH_SF_REFITS`) are the same env vars as the
main study.

## The rule (unchanged)

Every method — ours and theirs — is turned into the same predictive `Dist` and
scored by the same code on the same held-out points. Gaussian predictives
(auto.arima, Theta) are scored exactly; genuinely non-Gaussian ones (ADAM,
nnetar, GARCH-t, BSTS, CSP) are scored on their **real quantiles**, not a
Gaussian-from-band flattening. CDF-only methods report CRPS and say so.
