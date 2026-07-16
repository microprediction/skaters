# laplace vs. TBATS

These bouts exist to find the corners: the types of series where another
method outperforms `laplace`, stated plainly when found. TBATS finds one.

**Opponent.** TBATS (De Livera, Hyndman & Snyder 2011; `forecast` package):
exponential-smoothing state space with Box-Cox, ARMA errors, trend, and
trigonometric seasonal components — the classical answer to long and multiple
seasonal periods. Two configurations: `TBATS-R` with the arm's single period
(`ts(frequency=m)`), and `TBATS-R-ms` with `seasonal.periods = c(24, 168)`
(hour-of-day and hour-of-week) on the hourly arm, since multiple periods are
the method's design point.

**Protocol notes.** Refit every 25 steps with the fitted model reused between
refits. `forecast::tbats`'s `model=` reuse path intermittently emits corrupt
filtered states on shifting windows (forecast means hundreds of sigma out), so
every reused forecast is sanity-checked against the window scale; an insane
one forces a fresh fit, and the step is skipped only if the fresh fit is
insane too. Quantile fan (`level=LEVELS`) so any asymmetric intervals are
scored as shaped; Box-Cox is a documented no-op on signed change-series.
`use.parallel=FALSE` (the harness already parallelises across series). Rows
live in the shared arm CSVs under `../laplace-vs-csp/`.

**Versions.** `skaters` 0.13.0, `laplace` rows at commit `f960009` (the
population including `seasonal_anchor`); `forecast` package TBATS. July 16,
2026.

## Result

`laplace` **win-rate** (CRPS / LL):

| arm | vs TBATS-R |
|---|---|
| daily (N=500) | 89 / 96% |
| monthly (N=244) | 62 / 96% |
| M4-Hourly (N=414) | 63 / 77% |

Third-party rounds on the same series: on monthly, TBATS beats CSP's defaults
78 / 69 % (median CRPS −10.7 %) and NNS 69 / 59 % — the strongest third-party
method on the yearly cycle. On M4-Hourly the hour-of-week variant does not
help: paired against single-period TBATS, `TBATS-R-ms` wins 41 % of series
(median +1.5 % CRPS; N=414) — 750-step windows hold barely four weekly
cycles, too few for the 168-period harmonics.

## The two regimes of M4-Hourly

The M4 aggregate hides a split. The first ~180 series have **soft cycles**
(median phase-profile R² 0.76, shorter histories); the rest have **nearly
deterministic cycles** (R² 0.97). `laplace` win-rates by regime:

| opponent | soft cycles (N=180) | hard cycles (N=234) |
|---|---|---|
| TBATS-R | **22 / 51%** | 95 / 97% |
| CSP defaults | **19 / 54%** | **24 / 37%** |
| NNS-R | 62 / 86% | 58 / 67% |

- **Soft cycles are TBATS's corner.** Where the daily cycle is real but noisy,
  the smooth trigonometric basis plus ARMA errors beats `laplace` on 78 % of
  series by CRPS (and CSP does similarly, by a different route). This is the
  regime TBATS was built for, and the numbers agree.
- **Hard cycles punish the truncated Fourier basis.** When the 24-point phase
  profile explains 97 % of variance, pool- and anchor-style methods represent
  it exactly and TBATS's harmonics systematically underfit: `laplace` wins
  95 / 97 %.
- CSP is the one opponent that holds its CRPS edge in **both** regimes on this
  arm — its remaining advantage (phase-conditional width and shape) is not
  regime-dependent; see `../laplace-vs-csp/`.

The corners found so far, across all bouts: strongly-seasonal hourly data
(CSP on CRPS, both regimes; TBATS additionally on soft cycles), and the
price/return universe (GARCH-t, `../laplace-vs-garch/`). Where a corner is
someone else's, the pages say so.
