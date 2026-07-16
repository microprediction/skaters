# laplace vs. NNS.ARMA

**Opponent.** `NNS.ARMA` from Viole's
[NNS](https://cran.r-project.org/web/packages/NNS/index.html) package (CRAN,
v13.0 here): forecasts from **same-phase component series** — decompose by
phase of the seasonal cycle, model each phase's own history, combine across
detected periods weighted by seasonality strength. This construction is the
prior art for the seasonal-pool family (in NNS since at least 2017; see the
lineage note in `../laplace-vs-csp/`), so it belongs in the ring.

**Harness treatment.** `NNS.ARMA` emits a point forecast, so the predictive is
a split-conformal band: the shared quantile grid of a rolling pool (≤400) of
its own one-step errors, warmed for 120 steps before the scored window
(emitted before the realized error is appended — no leakage), scored through
`grid_dist` like every quantile-emitting baseline. `method="lin"` (the
`nonlin` default is 2.7× worse point-MAE on change-series), refit every step.
Two methods: **NNS-R** is given the arm's season period (`BENCH_CSP_M`, the
same knowledge the CSP opponent gets); **NNS-R-auto** uses the package's own
period detection. Rows live in the shared arm CSVs under
`../laplace-vs-csp/`.

**Reproduce.**
```bash
Rscript -e 'install.packages("NNS")'
STUDY_OPPS=NNS-R PYTHONPATH=src python benchmarks/comparisons/csp_arm_study.py m4-hourly
```

## Result

`laplace` **win-rate** (CRPS / LL):

| arm | vs NNS-R (given m) | vs NNS-R-auto | NNS-R beats CSP defaults |
|---|---|---|---|
| daily (N=493) | 89 / 98% | 99 / 99% | — |
| weekly (N=248) | 96 / 98% | 98 / 98% | 29 / 58% |
| monthly (N=250) | 79 / 97% | 99 / 100% | **75 / 73%** |
| M4-Hourly (N=414) | 60 / 75% | 96 / 97% | 32 / 38% |

## Reading

- **Given the right period, NNS.ARMA is a serious seasonal opponent.** On
  M4-Hourly it takes 40 % of series from `laplace` on CRPS, the best showing
  of any point-forecast baseline, and on the monthly FRED arm (the yearly
  cycle) it beats CSP's defaults outright on both metrics — same-phase
  regression handles the annual cycle better than recency-weighted pools do.
  CSP keeps the hourly turf, where its phase-conditional widths matter.
- **Period detection is its weak point.** `NNS-R-auto` loses 96–100 %
  everywhere, including the strongly seasonal arm. The method's power is
  conditional on being told the cycle.
- **`laplace` holds every arm.** The `seasonal_anchor` candidates carry the
  same same-phase location idea inside the ensemble, with likelihood
  weighting deciding per series whether it applies, and the density race
  (LL 75–98 %) is not close on any arm.

## Footnotes: two NNS-derived candidates that lose (skaters#113)

Both tried against current laplace across all four arms; tape in
`benchmarks/nns_ideas.py`, registered as `laplace-pm` / `laplace-pt`.

- **Partial-moment terminal leaf** (`pm_leaf`): lower/upper partial second
  moments fitted to a two-piece normal, replacing the CRPS leaf. Loses
  everywhere (CRPS win 1–2 %, median LL cost up to −0.39 nats on monthly):
  whatever the skew buys, displacing the CRPS-fitted scale-mixture leaf costs
  more — the same lesson the phase-aware leaf taught. If the idea has value
  it is as an asymmetric scale inside the champion leaf, not a replacement.
- **Per-phase Holt trend** (`phase_trend_anchor`): per-phase level + trend,
  hedged with the seasonal-naive. Net harmful (CRPS win 4–25 %, LL medians
  +0.0000): per-phase trend estimates are noise at these history depths, and
  the candidates leak enough weight to tax CRPS without a compensating win
  even on monthly NSA series.
