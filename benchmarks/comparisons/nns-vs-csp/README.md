# NNS.ARMA vs. CSP — a third-party bout

Two seasonal forecasters built on the same object, the **same-phase history**:
[NNS.ARMA](https://cran.r-project.org/web/packages/NNS/index.html) (Viole)
regresses each phase's component series and combines across periods (the
construction's prior art, on CRAN since ≤2017); CSP, Conformal Seasonal Pools
([csp-forecaster](https://github.com/valeman/csp-forecaster), Manokhin,
arXiv:2605.03789) draws recency-weighted samples from the same-phase pool and
adds a conformal residual band. We referee only: same corpus arms, same
one-step change protocol, same `Dist` scorer, both told the arm's season
period. `laplace` is not in this ring.

**Protocol notes, stated plainly.** CSP is a native sampler; its 256 samples
become a KDE-smoothed quantile grid. NNS.ARMA emits a point forecast; it gets
this harness's standard treatment for point forecasters, a split-conformal
band from a rolling pool of its own one-step errors (warmed before the scored
window, no leakage). `method="lin"` for NNS (its `nonlin` default is 2.7×
worse point-MAE on change-series); package defaults for CSP, with the
paper-exact and pool-weight-0.7 variants shown. Rows live in the shared arm
CSVs under `../laplace-vs-csp/`.

## Result

**NNS-R win-rate** over CSP (CRPS / LL; positive median = CSP's median CRPS
excess over NNS):

| arm | vs CSP defaults | vs paper-exact | vs pool-weight 0.7 | median ΔCRPS |
|---|---|---|---|---|
| daily (N=490) | **87 / 78%** | **86 / 78%** | **76 / 77%** | CSP +9.7% |
| weekly (N=248) | 29 / **58%** | 8 / 34% | 21 / **71%** | CSP −13.4% |
| monthly (N=248) | **75 / 73%** | **69 / 59%** | 45 / **79%** | CSP +5.7% |
| M4-Hourly (N=414) | 32 / 38% | 34 / 26% | 19 / 49% | CSP −5.7% |

Auto-detected periods change everything: `NNS-R-auto` loses to CSP defaults
1–6 % on CRPS on every arm. Both methods' results are conditional on being
handed the cycle.

## Reading

- **The card splits 2–2 by arm.** NNS takes daily FRED (87/78, CSP paying a
  9.7 % median CRPS premium — the conformal band around a same-phase
  regression degrades more gracefully where the cycle is weak) and monthly,
  the annual cycle (75/73 against CSP's defaults). CSP takes weekly (13.4 %
  median CRPS edge) and its hourly home turf (5.7 %), where its
  phase-conditional widths and skew do work a point-plus-band predictive
  cannot.
- **Configuration moves individual rounds, not the card.** CSP's
  pool-weight-0.7 is its best weapon against NNS on CRPS everywhere, at the
  cost of the density side; the paper-exact construction is strictly weaker
  than the package defaults against NNS on hourly data, consistent with the
  package's own benchmarking.
- **Neither survives its own period detector.** NNS-R-auto loses to CSP
  nearly everywhere, and CSP ships no detector at all (`m` is a required
  input). Whatever these methods win, they win after being told the answer to
  the hardest question.
