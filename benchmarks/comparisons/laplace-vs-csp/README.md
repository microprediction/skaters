# laplace vs. CSP (Conformal Seasonal Pools)

**Opponent.** CSP, Conformal Seasonal Pools (Manokhin, arXiv:2605.03789), a
training-free sampler that mixes same-season empirical draws with signed residual
draws around a seasonal-naive forecast. We run the **author's reference package**
([valeman/csp-forecaster](https://github.com/valeman/csp-forecaster), v0.1.4,
numpy-only; its own test suite passes in our env):

```bash
pip install git+https://github.com/valeman/csp-forecaster.git
```

Each step we fit `ConformalSeasonalPool` on the trailing window, draw 256
one-step samples (`BENCH_CSP_NSAMPLES`), and KDE-smooth their quantile grid into
a `Dist` via `grid_dist`, the same convention as the other sample-based
baselines, so CSP is scored on **both** log-likelihood and CRPS by the one
scorer.

**Configurations.** Twelve variants per arm form a star around the package's
recommended defaults (`adaptive=True`, `residual_mode="h_step"`,
`decay_unit="step"`, `exp_lambda=0.01`, `pool_weight=0.5`, `cal_fraction=0.5`):
the arm's own season period plus neighbours, the paper-exact pool construction
(`residual_mode="paper"`, `decay_unit="cycle"`), non-adaptive mixing, recency
decay off (`lam0`) and strong (`lam05`), pool weight 0.3/0.7, calibration
fraction 0.25/1.0, and the m=1 non-seasonal floor. At H=1 `residual_mode`
cannot differ between `h_step` and `paper` (the lag is m either way), so the
`paper` variant isolates `decay_unit="cycle"`. `orientation` changes reported
interval quantiles, never the samples, so it cannot affect these scores and is
not swept.

**Corpus.** Four arms from `benchmarks/corpus.py`, all one-step change-series:
daily FRED (m=5, business-day week), weekly FRED (m=52), monthly FRED (m=12,
the annual cycle), and M4-Hourly (m=24, the strongly seasonal
electricity/traffic-style data CSP was built for).

**Sample-budget convergence.** CRPS is converged well below any method gap by
B=256 (mean over the 8 canonical daily series, 3 seeds each: 0.1908 at B=64,
0.1877 at B=1024, seed spread ~0.0005). Log-likelihood of an empirical pool is
tail-fragile: seed spread swings up to ±4 nats at small B because a KDE of the
pool can miss the realized value entirely (the scorer floors logpdf at −20),
stabilising only by B≥1024. Full table: `csp-convergence.csv`. The LL win-rates
below are read with that caveat; the CRPS ones need none.

**Reproduce.**
```bash
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py laplace-vs-csp CSP
PYTHONPATH=src python benchmarks/comparisons/csp_arm_study.py monthly   # weekly, m4-hourly
PYTHONPATH=src python benchmarks/comparisons/csp_convergence.py
PYTHONPATH=src python benchmarks/comparisons/laplace_weight_probe.py
```

## Results

`laplace` **win-rate** per arm (CRPS / LL; N series). `laplace` here is the
current default, which includes the `seasonal_anchor` candidates this bout
produced (see Reading):

| variant | daily (N=497) | weekly (N=250) | monthly (N=248) | M4-Hourly (N=414) |
|---|---|---|---|---|
| defaults, arm's m | 99 / 99% | 82 / 91% | 85 / 98% | **21 / 44%** |
| paper construction | 99 / 98% | 80 / 90% | 84 / 98% | **40 / 46%** |
| fixed (non-adaptive) | 99 / 99% | 82 / 92% | 85 / 98% | **21 / 44%** |
| no recency decay (lam0) | 99 / 98% | 80 / 90% | 84 / 98% | **40 / 47%** |
| strong decay (lam05) | 99 / 99% | 88 / 98% | 92 / 100% | 67 / 99% |
| pool weight 0.3 | 99 / 99% | 84 / 90% | 91 / 99% | 62 / 53% |
| pool weight 0.7 | 98 / 99% | 81 / 95% | 77 / 98% | 13 / 57% |
| cal fraction 0.25 | 99 / 99% | 82 / 92% | 85 / 99% | **25 / 48%** |
| cal fraction 1.0 | 99 / 99% | 82 / 91% | 85 / 98% | **22 / 43%** |
| m=1 floor | 99 / 99% | 94 / 97% | 92 / 100% | 98 / 97% |

Daily also swept m ∈ {5, 7, 21}: all 98–100% both metrics. Bold marks cells
where CSP wins both metrics (laplace under 50% on each). Full per-arm grids:
`results.csv`, `results_weekly.csv`, `results_monthly.csv`,
`results_m4_hourly.csv`.

## Reading

- **Against a laplace with no seasonal-location machinery, CSP swept its home
  turf.** The pre-anchor laplace lost M4-Hourly to CSP's defaults on 91 % of
  series by CRPS and 76 % by log-likelihood (median 15 % extra CRPS per
  series), while sweeping CSP 98–99 % everywhere else. The bout's post-mortem
  decomposed that home-turf edge; the pieces are below, and the piece that
  mattered now ships in `laplace` itself.
- **Not detection.** The pre-anchor laplace already identified the hourly
  cycle essentially perfectly: on 36/40 probed M4 series more than half its
  ensemble weight sat on the period-24 candidates
  (`laplace_weight_probe.py`; on daily FRED the same probe puts ~zero weight
  there). `dantzig`, which discovers periods online, moved the CRPS win
  against CSP only from 9 % to 14 % and trails `laplace` on all four arms.
- **The same-phase idea is old.** Forecasting from same-phase component
  series — decompose by phase of the cycle, model each phase's own history,
  combine across detected periods weighted by seasonality strength — has been
  in Viole's [NNS](https://cran.r-project.org/web/packages/NNS/index.html)
  package (`NNS.ARMA`) since at least 2017. CSP's seasonal pool is a
  recency-weighted draw from that same decomposition.
- **Mostly location, and the winning anchor is a hedge.** `seasonal_difference`
  anchors on the SINGLE value one cycle ago (adapts instantly, one noisy
  draw); a per-phase EMA (recency-weighted same-phase mean) averages the
  noise but lags level shifts and loses to the naive on 5 of 6 probed series.
  Their 50/50 blend beats both on every probed series and both metrics — the
  `seasonal_anchor` transform, now in `laplace`'s default candidate
  population (Python, JS, and Rust ports). It is worth a median −8.3 % CRPS
  (−14 % at the quartile) and +0.08 nats on M4-Hourly. The cost on FRED, from
  a paired old-vs-new run over all 1,000 arm series: median CRPS change
  +0.0000 % on every arm, p95 at most +0.016 %, worst single series +4.7 %
  (weekly; daily worst +1.3 %), worst LL dip −0.17 nats on one daily series.
  The tail is asymmetric in laplace's favour: 6 series lose more than 0.5 %
  while 18 gain more, and the gains sit exactly where FRED has real cycles —
  NSA payrolls −20 % CRPS, unemployment −18 %, SOFRINDEX −12 %. The table above is against this
  current laplace: CSP's defaults still hold the M4 CRPS belt (79 %) but the
  log-likelihood is near even (56 %), and laplace now beats the strong-decay
  and pool-weight-0.3 configurations outright.
- **The width/shape remainder does not import cleanly.** Four attempts, all
  instructive: a phase-aware terminal scale (`laplace-ss`) flattens per-phase
  PIT but scores worse (the global leaf scale it displaces was also tracking
  regime drift, and a leaf has no ensemble to switch it off where there is no
  cycle); a per-phase empirical residual leaf is worse still; studentized and
  PIT-recalibrating terminals (`terminal_variants.py`) are neutral, because
  likelihood weighting settles on interior mixtures whose moments
  phase-average the width right back (mixture width ratio 1.23 vs the 3.7
  needed). A likelihood-weighted top-level mixture of laplace's and CSP's
  full predictives beats both parents on the probe, but it is a bypass, not a
  repair: it only spans the coordinates you enumerate as members, where
  candidates compose. The remaining M4 CRPS gap lives here.
- **The m=1 floor confirms the attribution.** Strip the seasonal pool and CSP
  loses everywhere, including 98 % on M4-Hourly. Whatever CSP wins, it wins
  through the cycle, not through the conformal residual band.
