# Online residual transform: does M2 beat M1?

Phase-1 ablation of `skaters.residual_transform` (see the module docstring
for the full mechanism): wrap a base skater's own one-step PIT residual
stream `z_t = Phi^-1(F_{t-1}(y_t))` with a small online model of the *next*
residual's distribution, and correct the forecast accordingly.

    M0  identity        H_t = N(0, 1)                              -- no learning
    M1  dynamic scale    H_t = N(0, exp(ell_t)),  ell_{t+1} = a*ell_t + c*(z_t^2-1)
    M2  + leverage       ell_{t+1} = a*ell_t + b*z_t + c*(z_t^2-1)

`a, b, c` are learned online (RTRL-lite SGD on -log h_t(z_{t+1}), see the
module docstring). Per the research spec, the decisive question for this
phase is narrow: **does the leverage term (M2 vs M1) earn its keep over
ordinary volatility clustering (M1 vs M0)?**

Stamped: skaters 0.12.1 @ 0c2ae68.

## Setup

Two base skaters:

  * `laplace(k=1, tails="gaussian")` -- the real, shipped forecaster (its
    terminal leaf already does its own EWMA volatility tracking, so this is
    the test of whether the residual transform adds anything *on top* of
    that).
  * `leaf(k=1)` -- a plain Gaussian leaf with no volatility tracking of its
    own (a positive control: if the pipeline works at all, M1 must win here).

Two data arms, 50 series each (fixed seed, `benchmarks/residual-transform/run_study.py`):

  * `fred` -- a random sample of the local `benchmarks/data/*.csv` FRED
    change-series (macro/financial, no price/non-price filtering -- see
    caveats).
  * `waveform` -- the M4-hourly competition set (the README's "hard
    waveforms" arm: near-deterministic, strongly 24-periodic cycles, the one
    regime where `laplace` is known to cede ground to CSP because it isn't
    handed the period).

Per series: log-score at every tick (exact, closed-form via `CorrectedDist`),
CRPS every 5th tick (32-node quantile-grid quadrature), first 100 ticks
skipped as warm-up, Newey-West HAC mean/SE of the paired score difference.
Full per-series numbers in `results.csv`. A third arm, `price` (actual
equity/fx/commodity series, against `garch_leaf` and `laplace`), is added
below and detailed in `results_price.csv`.

## Hypothesis 1: does dynamic scale (M1) beat identity (M0)?

Mean and median are the per-series HAC point estimate, averaged/medianed
across the 50 series; `frac>0` is the share of series where it improved;
`sig+`/`sig-` are the shares individually significant at the 5% level
(`|mean/HAC-se| > 1.96`) in each direction.

| data | base | mean | median | frac>0 | sig+ | sig- |
|---|---|---:|---:|---:|---:|---:|
| fred | laplace | -0.025 | +0.002 | 0.60 | 0.16 | 0.06 |
| fred | leaf | **+0.161** | +0.069 | 0.96 | 0.68 | 0.00 |
| waveform | laplace | **+0.029** | +0.011 | 0.72 | 0.34 | 0.00 |
| waveform | leaf | **+0.055** | +0.063 | 0.86 | 0.74 | 0.02 |

(log-score, nats/tick; CRPS moves the same direction and is small in
absolute units since these are already-differenced change-series -- see
`results.csv` columns `crps_m1v0_*`.)

The `leaf` column is the sanity check: with **no** volatility tracking on
the base side, M1's own EWMA-style scale correction picks up the obvious win
everywhere (68-74% of series individually significant, essentially none
significantly worse) -- the pipeline works.

Against the currently-shipped `laplace`, the picture is regime-dependent,
and it matches the suspicion that `laplace` runs a bit baggy specifically on
near-deterministic, cyclic data: on `waveform`, M1 improves 72% of series
with a clean, one-sided significance split (34% significantly better, *zero*
significantly worse) -- a real, if modest, effect. On generic `fred` series,
`laplace`'s own terminal-leaf EWMA already tracks ordinary volatility
clustering, and M1's marginal contribution on top of that is a wash: the
mean is dragged negative by a handful of noisy series whose own HAC SE is
nearly as large as the point estimate (e.g. `IHLIDXUSTPBAFI`: -0.68 +/-
0.67), while the median sits at +0.002 and only 16% of series move
significantly either way.

## Hypothesis 2/3: does leverage (M2) beat dynamic scale alone (M1)?

| data | base | mean | median | frac>0 | sig+ | sig- |
|---|---|---:|---:|---:|---:|---:|
| fred | laplace | +0.016 | -0.002 | 0.42 | 0.00 | 0.04 |
| fred | leaf | -0.041 | -0.006 | 0.30 | 0.00 | 0.08 |
| waveform | laplace | -0.000 | -0.003 | 0.30 | 0.00 | 0.04 |
| waveform | leaf | -0.004 | -0.003 | 0.26 | 0.10 | **0.42** |

M2 does not earn its keep in any of the four (data, base) combinations: it
improves a *minority* of series everywhere (26-42%), CRPS deltas are
essentially zero (largest magnitude 0.0004 nats), and where a significance
split exists it leans *against* M2 (waveform/leaf: 42% significantly worse
vs. 10% significantly better). The learned leverage coefficient `b` is
centered near zero and slightly negative on average in every group
(`results.csv` column `m2_b`, means -0.05 to -0.000, medians -0.06 to
-0.02) -- consistent with "no reliably exploitable leverage signal", not a
learner-convergence failure (the `test_recovers_planted_leverage` /
`test_no_spurious_leverage_when_absent` unit tests confirm the learner does
recover a planted effect of this size when one is actually present).

The raw diagnostic `L1 = E[z_t(z_{t+1}^2-1)]` (the leverage statistic proper,
independent of any learner) is small and slightly *negative* on average in
three of the four groups (-0.06 to -0.07) and modestly positive only for
`waveform/leaf` (+0.10) -- and even there M2 could not turn it into a
reliable score improvement, suggesting whatever raw correlation exists is
too noisy per-series, or too entangled with the scale term it's fit jointly
with, for this online estimator to exploit.

## Leverage on actual price data (garch_leaf)

Neither arm above is *returns* data, and the leverage effect is classically
an equity/FX-returns phenomenon -- so it's the sharpest test of Hypothesis 2
and deserves its own arm rather than resting on `fred`/`waveform`. `price`
(`--datasets price`) is 50 series classified `equity`/`fx`/`commodity` by a
live FRED title lookup through `fred_universe.asset_class` (the same rule
`benchmarks/study.py` uses for its own price/non-price split), narrowed from
local tickers by name first to keep the API calls to ~100 rather than all
701. Two bases: `garch_leaf` (`laplace(k=1, leaf=garch_leaf)` -- a genuine
GARCH(1,1) conditional variance with periodic QMLE refits, the leaf this
repo recommends specifically for price/return series) and plain `laplace`.
Results in `results_price.csv`.

One series (`NASDAQXOSX`, a low-liquidity sub-index with a >10x historical
level range) produced a single catastrophic-surprise tick that swings its
mean log-score by tens of nats under `laplace` -- exactly the heavy-tailed
pathology that makes log-score means unreliable for financial data, so
**median is the headline number** here (CRPS, unaffected, corroborates it).

| data | base | mean | median | frac>0 | sig+ | sig- |
|---|---|---:|---:|---:|---:|---:|
| price (M1-M0) | garch_leaf | -0.005 | -0.003 | 0.24 | 0.04 | **0.28** |
| price (M1-M0) | laplace | -1.20&nbsp;[outlier] | -0.007 | 0.34 | 0.02 | 0.10 |
| price (M2-M1) | garch_leaf | -0.003 | -0.002 | 0.20 | 0.00 | 0.14 |
| price (M2-M1) | laplace | +1.16&nbsp;[outlier] | -0.000 | 0.46 | 0.00 | 0.02 |

Two findings, both clean:

  * **M1 itself is a net *negative* against `garch_leaf`** (24% of series
    improve, 28% are significantly *worse* vs. 4% significantly better).
    `garch_leaf` already runs a real fitted GARCH(1,1) recursion on exactly
    this data; layering a second, independently-online-fit scale correction
    on top mostly adds estimation noise rather than catching anything
    `garch_leaf` missed. This is the mirror image of the `fred`/`waveform`
    `leaf` columns above, where the base had *no* volatility model and M1
    won big -- the effect tracks how much room the base already used, not
    some property of price data specifically.
  * **M2 still does not beat M1** (20% and 46% of series improve against
    `garch_leaf` and `laplace` respectively -- a minority or a coin flip,
    never a majority), even here. There is a directionally interesting
    nuance, though: the raw leverage diagnostic `L1` is *negative* on
    average for both bases (garch_leaf median -0.044, laplace median
    -0.023) and the learned `b` is centered negative too (medians -0.023,
    -0.018) -- both exactly the sign classical leverage predicts (bad news
    raises future variance). It just isn't large or consistent enough
    across these 50 series for the online learner to turn into a reliable
    score improvement over M1 alone.

Caveat on this arm: the qualifying local price tickers skew toward secondary
FX crosses (Thai baht, Korean won, Saudi riyal, ...) and narrow NASDAQ
sub-indices rather than a liquid blue-chip universe (SPX, major pairs) --
the venue where the leverage effect is most robustly documented in the
literature. A correctly-signed-but-weak result here does not rule out a
cleaner one on that narrower, more classical universe.

## Recommendation

**M2 does not clear the M1 gate, on any of three regimes tested** (generic
macro, near-deterministic waveforms, or actual price/return data with a
dedicated GARCH base) -- including the one domain, price data, where
classical theory most expects a leverage effect, and where the raw
diagnostics are at least correctly signed. Per the spec's own decision rule
(section 16), that's grounds to reject the leverage-motivated branch rather
than build the richer M3/M4 (skew/tail, sinh-arcsinh) machinery on top of
it. The remaining live possibility -- a real but weak effect this online
learner and this sample size can't reliably extract -- is worth one narrower
follow-up (a liquid blue-chip universe, more series) before treating that as
settled, but does not justify further investment on the current evidence.

**M1 (plain dynamic scale) has a real, regime-dependent case for itself**,
though: a clean, one-sided win against `laplace` on the near-deterministic
waveform arm (the regime this study was specifically pointed at), and a wash
against `laplace` on generic FRED data (where the base's own adaptive leaf
already does the job) -- both are honestly modest relative to the huge,
unambiguous win against a non-adaptive base, which is the expected result
and not itself news.

**Follow-up, resolved: is M1's waveform win just "laplace's EWMA is too
slow"?** `scale_alpha_probe.py` tests this directly -- plain `laplace` at
faster fixed `scale_alpha` values (0.06, 0.10, 0.15, 0.20 vs. the default
0.03), no residual transform involved, same waveform/fred series. If a
uniformly faster EWMA alone recovered M1's gain, M1 wouldn't be adding
anything a hyperparameter tweak couldn't. It doesn't: on `waveform`, every
faster alpha is flat-to-negative and monotonically worsens (median delta
-0.0002, -0.0097, -0.0215, -0.0470 as alpha increases) -- the opposite of
what M1 achieved there. On `fred`, a slightly faster alpha (0.06) helps a
little (median +0.0017) but going further hurts, same monotonic pattern.
So the default is already close to right for a single *global* rate, and
M1's win on waveform is not reproducible by retuning that one knob -- it's
doing something a fixed rate structurally can't (adapting differently
within a series, not just running faster everywhere). Full numbers in
`scale_alpha_probe.csv`.

**Caveats / natural next steps, not done in this phase:**

  * `fred` here is an unfiltered random sample (no price/non-price split,
    unlike the rest of this repo's studies) -- a cleaner rerun would use the
    same asset-class filtering the other comparisons do.
  * GIFT-Eval (raised as a candidate regime alongside waveforms) has no
    local cache or loader in this repo and was out of scope for this pass.
  * M1's `laplace`-vs-`leaf` gap suggests the more actionable next
    experiment may not be M2's leverage term at all, but whether M1's scale
    correction still adds anything once compared against `laplace`'s
    *own* `scale_alpha` tuned to match -- i.e. is this catching a genuine
    serial-correlation structure, or partly just a faster/slower EWMA than
    the default `0.03`?
