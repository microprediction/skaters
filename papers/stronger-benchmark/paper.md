# A Stronger Univariate Benchmark for Foundational Time-Series Model Evaluation

Peter Cotton

## Abstract

Foundation models for time series are evaluated carefully, on proper scoring
rules, against automated statistical baselines, with leakage acknowledged. They
are also evaluated in one narrow configuration: horizons of six steps and
longer, a quantile loss on nine deciles, and baselines that refit from scratch
on a truncated window. We change three dials and report what happens. Under
one-step-ahead log density against a stateful online reference, a 136 KB
pure-Python forecaster with no pretraining beats TimesFM 3.0 on the median
series in every stratum tested. The frozen data vintage is published.

## 1. What these benchmarks already do well

It is worth being accurate about the state of practice, because the loose
version of this critique is wrong and easy to refute.

Foundation-model evaluation is probabilistic. GIFT-Eval reports a quantile-loss
CRPS and a scaled interval score, and its paper ranks models by the former.
Chronos reports weighted quantile loss beside MASE, TiRex reports CRPS, Moirai
reports CRPS and MSIS. A claim that these leaderboards measure only point
accuracy is false on the record.

The baselines are not absent either. Chronos scores naive, seasonal naive,
automated ETS, ARIMA and Theta, and a statistical ensemble, on the probabilistic
metric as well as the point one. Moirai tunes its deep baselines by random
search on validation CRPS across five seeds.

Contamination is named rather than hidden. The GIFT-Eval paper identifies
TimesFM, Chronos and Moirai as exhibiting partial leakage and quantifies the
effect in an appendix by comparing a cleanly pretrained model against a leaked
one. TiRex removes the sixteen of ninety-seven evaluation settings that overlap
its own pretraining corpus and makes the remainder its headline result. Moirai
excludes at source level, dropping a dataset because a related source sits in
its corpus.

This paper takes all of that as given. The argument is narrower.

## 2. Three dials

Every suite above is configured the same way along three axes, and a cheap
online method cannot compete anywhere in that configuration.

**The horizon never reaches one step.** GIFT-Eval's shortest prediction length
is six, for yearly M4. fev-bench uses domain horizons such as thirty and one
hundred sixty-eight. One-step-ahead forecasting is the default object of study
in econometrics and the thing most operational systems actually issue, and no
major foundation-model suite reports it.

**The scoring rule is a nine-point grid.** What the GIFT-Eval leaderboard calls
CRPS is a mean of nine weighted quantile losses at the deciles, renamed in the
display code. Nothing outside the tenth and ninetieth percentile enters any
published score. No suite reports a log density, a probability integral
transform histogram, or a coverage table. Amazon's own Chronos-2 report calls
the nine-quantile grid a defect and moves to twenty-one levels including the
first and ninety-ninth percentiles.

**No baseline carries state.** The entire standard set is five statsforecast
calls, and the predict path fits and forecasts from scratch on the array handed
in. Nothing survives between windows. Chronos and the Monash-derived tables do
not refit at all, using a single forecast origin per series.

None of these three is an oversight to be scolded. Each is a reasonable choice
for the task those suites set themselves. Together they define a regime, and the
regime excludes a class of method.

## 3. The baselines are configured to lose

The third dial deserves its own treatment, because the standard set is weaker
than its names suggest.

Statistical baselines have their context truncated to one thousand observations
in both GIFT-Eval and fev-bench. fev-bench sets the seasonal period to one
whenever it exceeds two hundred, so automated ARIMA and ETS run without
seasonality on five-minute data. GIFT-Eval replaces any statistical model that
exceeds its time limit with seasonal naive. Chronos used library defaults with
no tuning for its statistical arms while the deep arms received fifteen
hyperparameter trials per configuration.

The symptoms are visible in published tables. Automated ETS records a skill
score of minus 648.9% on one Chronos benchmark. Automated ARIMA lands nearly
five times worse than seasonal naive on hourly electricity CRPS in Moirai's
table. Neither number is a property of exponential smoothing or of ARIMA.

Their predictive distributions are thin by construction. Quantiles come from a
Gaussian residual-variance interval formula, so they are symmetric with no skew
and no tail shape. An ensemble's quantiles are a per-level median across
members, which is not a distribution.

One candidate reference is free and absent. NPTS is training-free, fully
distributional, and ships inside both GluonTS and AutoGluon, which these
harnesses already depend on. It appears in none of the benchmarks surveyed and
on no leaderboard.

## 4. The corpora contain almost no economic data

The regime argument has a corpus counterpart. These models are pretrained and
evaluated on data of a particular character.

| Corpus | Economic share |
|---|---|
| LOTSA, Moirai's pretraining set | 0.09% of observations |
| Chronos pretraining | zero economic datasets |
| GIFT-Eval | 6 of 97 configurations |

LOTSA is 92% energy, transport and climate by observation, and 97% of it is
hourly or finer. Chronos's corpus is roughly 94% a single weather reanalysis
dataset. GIFT-Eval's entire economics and finance domain is the M4 collection,
so the benchmark contains no price, no interest rate and no exchange rate series
anywhere.

This matters because the advantage pretraining confers is concentrated on
periodic data. Across fifty-one models and twenty-eight datasets, spectral
predictability and error correlate at Spearman −0.65. Zero-shot models lead
statistical and deep baselines by twenty to sixty percent on the predictable
half, and below a spectral predictability of 0.2 the model classes become
indistinguishable. Chronos's authors reach the same conclusion from the other
direction, attributing seasonal naive's competitiveness on their benchmark to
the energy and transport domains being highly seasonal.

A caution against over-reading this. Economic data is not uniformly harder. In
M4, within a fixed frequency, macro and finance sit in the easier half while
industry is worst, and a macro panel is the most improvable dataset in Chronos's
zero-shot suite. The defensible claim is about composition and about prices, not
about economics in general. The one price dataset these suites evaluate on,
Exchange Rate, is also the only zero-shot dataset where Chronos loses to
seasonal naive on both metrics.

## 5. Moving the dials

The reference method is `laplace`, a 136 KB pure-Python online distributional
forecaster with no pretraining, no GPU requirement, no fitting step and no
tunable hyperparameters. It is not offered as state of the art. It is offered as
a floor that a pretrained model should clear, cheap enough to include anywhere.

TimesFM 3.0 is scored zero-shot under one protocol: a 128-length context, a
rolling one-step-ahead test window, no fitting, held-out log density on the same
series and windows as the reference.

The context is fixed rather than growing, and that is deliberate. Several of
these models degrade beyond the window they were pretrained on, and most of them
silently truncate over-long input rather than raising. Feeding four thousand
points to a model whose configuration caps it at two thousand scores a
two-thousand-context model without saying so. Any protocol that lets context
grow therefore needs a declared per-model cap, set at the documented
architectural maximum or at the pretraining context, and recorded per arm.

Recording it matters for a second reason. Moirai's published benchmark numbers
come from a per-dataset search over context lengths from one thousand to five
thousand, jointly with patch size, which the arms it is compared against do not
receive.

| stratum | n series | win / draw / loss | median ΔLL | loss rate |
|---|---|---|---|---|
| daily, economic | 2,179 | 66 / 923 / 1,190 | −0.854 | 54.6% |
| daily, price/returns | 7,633 | 15 / 4,593 / 3,025 | −0.616 | 39.6% |
| weekly, economic | 3,013 | 517 / 1,481 / 1,015 | −0.520 | 33.7% |
| monthly, economic | 5,576 | 193 / 3,592 / 1,791 | −0.647 | 32.1% |
| M4-hourly, seasonal | 414 | 8 / 241 / 165 | −0.543 | 39.9% |

Negative favours the reference. The model loses on the majority of series in
every stratum by a median of roughly half a nat.

A post-hoc portfolio combining the model's own issued predictive with the
reference recovers most of the gap, with no retraining and no access to
internals.

| stratum | n series | win / draw / loss | median ΔLL | loss rate |
|---|---|---|---|---|
| daily, economic | 2,179 | 76 / 1,383 / 720 | −0.094 | 33.0% |
| daily, price/returns | 7,633 | 152 / 7,136 / 345 | −0.008 | 4.5% |
| weekly, economic | 3,011 | 467 / 2,045 / 499 | −0.049 | 16.6% |
| monthly, economic | 5,195 | 350 / 4,480 / 365 | −0.056 | 7.0% |
| M4-hourly, seasonal | 414 | 58 / 352 / 4 | −0.007 | 1.0% |

The wrapped model is safe to deploy, since its loss rate falls by as much as
thirty-nine points. It remains behind the reference, since the median stays
negative everywhere.

## 6. The reconstruction is a free parameter

A quantile-only model does not emit a density, so something must build one
before a density score exists. That choice belongs in a protocol.

Holding TimesFM 3.0 and 3,200 held-out test points fixed and varying only the
reconstruction across four registered methods moves the mean log density from
−0.373 to +2.104. The mean per-point spread is 3.13 nats, which exceeds the
entire measured gap between the model and the reference in every stratum above.
Two methods already in independent use elsewhere differ by 0.62 nats.

This is not only our problem. GIFT-Eval's submission interface requires a mean
plus nine deciles, so a model emitting a genuine density must reduce it before
scoring, and a model emitting samples must convert. The interval score asks for
the 2.5th and 97.5th percentiles and the sample forecast returns a nearest order
statistic without interpolation, so at the twenty samples the Chronos notebook
uses, those two quantiles are the minimum and maximum of twenty draws.

## 7. Why a strong reference makes leakage legible

Contamination stratification needs a reference near parity to show anything.
Against a baseline that loses everywhere, a model wins on both the suspect and
the clean split and the comparison is uninformative. Against a reference the
model does not dominate, the split becomes a measurement.

In our own store, splitting a foundation-model comparison into
pretraining-suspect and plausibly-clean strata flips the sign of the result in
eight of nine model-horizon cells. The exception is TimesFM 2.5 at one step,
where the reference loses on both strata and loses more on the clean one.

We state two limits plainly. The suspect stratum in that run is entirely M4, so
suspected contamination is perfectly confounded with M4's short, seasonal,
curated character, and the result cannot separate them. And two of the flips
rest on point estimates whose intervals cross zero.

The deeper problem is that leakage in this literature is controlled by dataset
name rather than by audit or by time. Chronos writes down the temporal standard,
that evaluation data should begin after the last pretraining observation, then
declines to meet it and judges the risk minimal. Name matching also fails when
one file carries two names. Meyer and colleagues report that TimesFM appears to
pretrain on the Monash traffic hourly data it then evaluates on, and Oreshkin
and colleagues make the same observation about the long-horizon suite. Both
predate this paper and the finding is theirs.

What we add is the documentation. The pretraining table lists Traffic at 862
series and 15,122,928 observations. The Monash archive's own data file holds 862
series of exactly 17,544 steps, whose product is that figure, and the Electricity
and Weather rows match their long-horizon-suite dimensions the same way. The
paper's single citation for all three points to the Informer benchmark.

The authors knew about the overlap, because they excluded those same series from the
Informer group and said so, while the evaluation on Monash retained them under a
blanket held-out claim. The row first appears in the fourth version and is
carried into the camera-ready, with no erratum.

## 8. What this does not settle

Everything here is univariate and one step ahead. A single pretrained model
amortized across many related series can exploit cross-series and panel
structure that no univariate method can reach, and that is where pretraining
should pay for itself most directly. This paper makes no such comparison, and it
is the more decisive one.

The protocol is not new. Proper scoring rules are the norm in this literature.
Prequential test-then-train evaluation is textbook and is the default in
streaming-machine-learning libraries. Paired per-series comparison was urged on
the forecasting field in 2005 and is already the headline aggregation in
fev-bench. Normalising against a cheap reference is universal.

What this paper contributes is the observation that the standard configuration excludes a class
of method, and the measurement of what changes when it does not.

A growing context also cuts both ways, which is why the protocol above fixes it
and section 5 states the cap policy. No published study takes cross-model
context sensitivity as its subject, so the cap has to be read off model cards
and configuration files rather than off measured optima.

Finally, a calibration framing would have to engage published evidence that
these models are better calibrated than automated ARIMA and N-BEATS on standard
datasets. Nothing here contradicts that. Calibration on a decile grid and
sharpness of a full density are different questions.

## 9. Reproducibility

Every number in sections 5 and 6 is produced by
`papers/stronger-benchmark/constants.py` from a version-controlled store, and
none is typed by hand. `REPRODUCE.md` gives three tiers: verify the published
figures in seconds from committed files, rebuild the summaries from per-step
records in minutes, or regenerate those records from raw data.

The data vintage is published as a release asset at
`microprediction/skaters-benchmarking-data`. FRED revises series, so a fresh
pull returns different vintages and will not reproduce these numbers. The
archive carries the 210,574 public-domain series; commercial index series are
excluded and listed, which costs the price stratum and nothing else.
