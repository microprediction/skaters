# Evidence base

Primary-source findings from the 2026-09-21 research pass. Every claim the paper
makes has to trace to a line here, and every line here traces to a paper
section, a source file or a released data file. Claims that failed verification
are kept, marked REFUTED, so they do not get re-proposed.

## REFUTED. Do not write these.

**"These leaderboards measure point accuracy, not distributions."** False.
GIFT-Eval reports a quantile-loss CRPS and MSIS, and its paper's headline rank
is computed from CRPS. Chronos reports weighted quantile loss, TiRex reports
CRPS, Moirai reports CRPS and MSIS. The repo's own comparison table lists
probabilistic forecasting as what GIFT-Eval has and Monash, TFB, LTSF and
BasicTS+ lack.

**"They compare against weak baselines."** Overstated as a blanket charge.
Chronos scores Naive, Seasonal Naive, AutoETS, AutoARIMA, AutoTheta and a
statistical ensemble on weighted quantile loss as well as MASE. Moirai tunes its
deep baselines over fifteen-run random search on validation CRPS across five
seeds. The narrow version survives; see "configured to lose" below.

**"Contamination is unnoticed."** False. The GIFT-Eval paper names TimesFM,
Chronos and Moirai for partial leakage and quantifies it in an appendix. TiRex
removes the sixteen of ninety-seven settings overlapping its own pretraining and
makes the remainder its headline. Moirai excludes at source level. Chronos-2
ships a per-model leakage column.

**"Economic series are harder."** False as stated. In M4 within a fixed
frequency, Macro and Finance sit in the easier half and Industry is worst.
Macro has the best median overall weighted average of the six domains. FRED-MD
is the most improvable dataset in Chronos's zero-shot benchmark. GIFT-Eval's own
entropy puts Econ/Fin below Energy and well below Transport.

**"The sign flips for every rival at every horizon."** False in our own store.
It flips in eight of nine cells. TimesFM 2.5 at one step does not flip.

## Established, with sources.

### The corpora carry almost no economic data

| Corpus | Economic share |
|---|---|
| LOTSA, Moirai's pretraining set | 0.09% of observations |
| Chronos pretraining | zero economic datasets |
| GIFT-Eval | 6 of 97 configs, 7 of 763 evaluation windows |

LOTSA is 92.04% energy, transport and climate by observation, and 97.3% hourly
or finer. Chronos's corpus is about 94% one weather reanalysis dataset by
observation count. GIFT-Eval's entire economics and finance domain is M4, so the
benchmark contains no price, no rate and no exchange-rate series at all.

### Periodicity is what pretraining buys

Across 51 models and 28 GIFT-Eval datasets, spectral predictability and error
correlate at Spearman −0.65 with p near 1.9e−21. Zero-shot models beat
statistical and deep baselines by 20 to 60% on the predictable half, and below a
spectral predictability of 0.2 the model classes are indistinguishable. Chronos's
authors attribute seasonal naive's competitiveness on their own benchmark to the
energy and transport domains being highly seasonal.

The one dataset where this cuts the other way is Exchange Rate, the only
zero-shot dataset in Chronos where the large model loses to seasonal naive on
both MASE and weighted quantile loss. PatchTST dropped that dataset from its
benchmark on efficient-markets grounds.

### The baselines are configured to lose

The whole standard set is five statsforecast calls. Of GIFT-Eval's 132
leaderboard entries, five are non-neural. None carries state: the predict path
fits and forecasts from scratch on the array handed in.

- Statistical baselines get context truncated to 1000 observations
- fev-bench sets seasonality to 1 above period 200, so AutoARIMA runs
  non-seasonal on five-minute data
- GIFT-Eval replaces any statistical model that times out with seasonal naive
- Chronos used defaults with no tuning for statistical baselines while the deep
  side got fifteen Optuna trials per configuration

Symptoms: AutoETS scores −648.9% skill on one Chronos benchmark, and AutoARIMA
lands nearly five times worse than seasonal naive on hourly electricity CRPS.

Their quantiles come off a Gaussian interval formula, so symmetric with no tail
shape. NPTS, which is training-free and fully distributional and ships in both
GluonTS and AutoGluon, appears in none of these benchmarks.

### Harness mechanics

- The leaderboard's CRPS column is a mean of nine quantile losses on a fixed
  decile grid, renamed in the display code. It cannot see past the tenth and
  ninetieth percentiles.
- The interval score asks for the 2.5th and 97.5th percentiles, and the sample
  forecast returns a nearest order statistic without interpolation. At twenty
  samples, which the Chronos notebook uses, those are the minimum and maximum of
  twenty draws.
- Context length is uncapped by the harness, chosen per submitter, and has no
  field in the submission schema, so it cannot be audited.
- Whether multivariate data expands to univariate is a per-submitter choice, so
  two models can be scored on different instance counts.
- Missing metric values are filled with the column mean before normalising.
- Model type, leakage and reproducibility are self-declared with no verification
  step anywhere in the repository, and there is no reference implementation.

### M4's weight depends on the denominator

Six percent of configurations, 27 to 31% of scored instances, 69% of series. The
leaderboard takes a geometric mean over configurations. Never quote one of these
without saying which.

### The TimesFM Traffic overlap

The ICML paper says the evaluation datasets were intentionally held out. Its
Table 1 lists Traffic Hourly at 862 series and 15,122,928 observations. Monash
traffic hourly is 862 Caltrans series at 17,544 hourly steps, and the product is
exactly 15,122,928. The paper acknowledges the analogous overlap for the Informer
group but not this one.

Check one is done. The Monash archive's own data file, from its Zenodo record,
holds 862 series each of exactly 17,544 steps, so the product matches Table 1 to
the digit. Two checks remain: that the Table 1 row denotes the Caltrans corpus
rather than the separately listed 15-minute traffic data, and that no later
version of the paper addresses the overlap. NOT PUBLISHABLE until both land.

## Novelty. What is actually ours.

Each component is prior art on its own. Proper scoring rules are the norm.
One-step evaluation of these models exists. Prequential test-then-train is
textbook and is the default in streaming libraries. Paired per-series comparison
was argued about M3 in 2005 and is fev-bench's headline metric today.
Normalising by a cheap reference is universal.

Two risks compound this. Our own site and two preprints already publish
per-series prequential log-loss against four zero-shot models on this universe.
And an ICLR 2026 paper finds these models better calibrated than AutoARIMA and
N-BEATS, so any calibration framing must engage it.

What remains is the conjunction and, more defensibly, the configuration
argument: the existing suites are set away from the regime where a cheap online
method competes. The shortest horizon in GIFT-Eval is six steps. fev-bench uses
horizons like thirty and one hundred sixty-eight. No suite scores a log density.
Those are checkable facts about configuration, not claims about intent.

One caveat to carry: unbounded context hurts several of these models, so a
growing context needs a declared per-model cap and an argument for it, or a
referee will say we evaluated them outside their trained regime.
