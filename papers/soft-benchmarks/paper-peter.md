# Foundational Time-Series Models Use Soft Benchmarks

Peter Cotton

## Abstract

Foundation models for time-series forecasting are announced with
state-of-the-art claims against public leaderboards. The language used
("zero-shot," "outperforms," "state of the art") does not distinguish point
accuracy from probabilistic accuracy, and the claims are rarely checked
against the pretraining corpus of the model making them. A 136 KB,
zero-dependency, online distributional forecaster with no pretraining, no
GPU, and one parameter-free API call beats the current generation of these
models (TimesFM 2.5 and 3.0, evaluated head to head under an identical
protocol) on one-step-ahead log-likelihood across every economic and price
stratum tested. The leaderboard these models are commonly ranked on,
GIFT-Eval, is not a clean held-out test for them: 67% of its instances by
count overlap with a documented pretraining corpus, and splitting the
standard comparison by that overlap flips its sign; one rival lab's own
announcement names two others for sharing this problem. A second, independent
mechanism compounds it: holding the model and the test data fixed and varying
only how a quantile-only forecast is turned into a scoreable density moves
the mean log-likelihood by up to 2.4 nats, more than the entire measured gap
between TimesFM3 and the 136 KB baseline in any stratum. The apparent
competitiveness of these models is, to a measurable extent, a property of
the benchmark and the scoring pipeline around it, not of one-step
probabilistic forecasting skill.

## 1. Introduction

Announcements for time-series foundation models converge on a small set of
claims: state-of-the-art accuracy, zero-shot generalization, outright
superiority to models purpose-built for the task. Google Research's original
TimesFM announcement reports that the model "displays impressive zero-shot
performance on a variety of public benchmarks" and "performs better than most
statistical methods like ARIMA, ETS" and can "match or outperform powerful DL
models" [@timesfm-blog-2024]. The accompanying paper states that "our
out-of-the-box zero-shot performance on a variety of public datasets comes
close to the accuracy of state-of-the-art supervised forecasting models for
each individual dataset" [@das2024timesfm]. Amazon Science's Chronos
announcement reports the model "significantly outperformed classical
statistical methods, as well as specialized deep-learning models"
[@chronos-blog-2024]. NX-AI's announcement for TiRex quotes its inventor:
"we're no longer talking about marginal improvements. TiRex delivers a
substantial leap in quality" [@tirex-blog-2025]. None of these four sentences
names a metric. A reader cannot tell from them whether the claim concerns
mean absolute scaled error on a point forecast or a proper scoring rule on a
full predictive distribution. The two are not substitutable: a model can win
one and lose the other on the identical data.

The claims are made against a benchmark whose own "zero-shot" label is
narrower than it appears. GIFT-Eval, the leaderboard these models are most
commonly ranked against, defines zero-shot as not trained on GIFT-Eval's own
train/test split. It does not, and by its own account cannot, certify that a
pretrained model never saw a related or overlapping series during
pretraining [@gift-eval-blog-2024]. This is not a hypothetical gap. Salesforce
AI Research's own announcement for a later model, Moirai-MoE, states that it
achieves "the best zero-shot performance, even outperforming TimesFM and
Chronos, which include partial evaluation data in their pretraining corpora"
[@moirai-moe-blog-2024]. One benchmark-leading lab names two others, in an
official announcement, for the exact failure mode Section 3 measures the
consequences of. Amazon's own comparison table for Chronos-Bolt flags the
same problem from the other direction, marking rival "zero-shot" models with
a "+" to indicate "these models were pretrained on certain datasets in our
benchmark and are not entirely zero-shot" [@chronos-bolt-blog-2024]. Three
labs, describing each other's models, agree that the label does not mean
what it says.

Foundation models for time series are a genuine accomplishment. They
internalize the select/estimate/fit/predict cycle a classical forecasting
pipeline performs explicitly into a single pretrained forward pass, and
nothing here disputes that this is hard or that it is progress. The aim of
this paper is narrower, and complementary to that accomplishment: to measure
it accurately. That measurement will only add to the accomplishment when
these models really do unequivocally match strong univariate baselines while
simultaneously performing well in the multivariate and panel settings a
single pretrained model is uniquely positioned to exploit. This paper does
not make that comparison; Section 6 returns to it.

The rest of this paper makes three checkable claims. Section 2 distinguishes
the task these models are ranked on from the task this paper scores. Section
3 quantifies the contamination problem the quotes above describe
qualitatively, on the specific benchmark and models named. Section 4 scores
the current TimesFM generation against a 136 KB pure-Python online method
under one fixed protocol, live and reproducible from this project's own
store. Section 5 names the mechanisms. Section 6 states what none of this
settles.

## 2. Two tasks, not one

Public leaderboards such as GIFT-Eval rank multi-horizon point-forecast
accuracy on a curated collection of datasets, most evaluated zero-shot from a
fixed context window. This paper scores a different task: one-step-ahead
*probabilistic* forecasting, the full predictive density rather than a point,
online rather than fixed-window (the context grows every step), on a live
economic panel (FRED) rather than a static leaderboard file. A model can lead
one task and trail the other. A paper or announcement that reports only the
first without naming it as such licenses a broader "this model forecasts
well" claim than its evidence supports.

## 3. Contamination: GIFT-Eval is not a clean test for a pretrained model

This project's own leakage rule keeps its fitted arms off GIFT-Eval and
treats GIFT as clean for every arm. That is correct for arms trained only on
FRED, and silent about arms whose training data cannot be inspected. Chronos,
TiRex, and TimesFM are pretrained. TimesFM's corpus is documented to include
M4. M4 is 67% of GIFT-Eval by instance count.

Splitting GIFT-Eval into pretrain-suspect (M4, electricity, traffic, ETT) and
plausibly-clean (hospital, restaurant, covid_deaths, hierarchical_sales,
bizitobs, us_births) strata and re-running the identical laplace-vs-rival
comparison on each stratum separately gives:

| rival | stratum | h | mean Δnats (+ favors laplace) | 95% CI |
|---|---|---|---|---|
| Chronos-Bolt | pretrain-suspect | 1 | −0.153\* | [−0.294, −0.021] |
| Chronos-Bolt | plausibly clean | 1 | +0.357\* | [+0.067, +0.619] |
| TiRex | pretrain-suspect | 1 | −0.241\* | [−0.387, −0.102] |
| TiRex | plausibly clean | 1 | +0.257 | [−0.061, +0.561] |
| TimesFM 2.5 | pretrain-suspect | 1 | −0.181\* | [−0.320, −0.053] |
| TimesFM 2.5 | plausibly clean | 6 | +0.373\* | [+0.144, +0.589] |

(\* CI excludes zero. Full table, all three horizons, in the source page.)

The sign flips between strata for every rival at every horizon tested. This
is not proof of contamination. The suspect group is dominated by M4, short
and seasonal and heavily curated; the clean group is counts data, so dataset
character is confounded with suspicion. The two strata also differ in typical
series length, which matters for an online method (Section 5). But the shape
is exactly what contamination would produce, and it means a single pooled
GIFT-Eval number is not reporting one thing. It averages two populations
whose answers disagree in sign.

GIFT-Eval's own announcement makes a second admission. It reports that
"foundation models generally outperform both statistical and deep learning
models across most domains," and in the same post reports that
"PatchTST stands out as the top-performing model across all metrics"
[@gift-eval-blog-2024]. PatchTST is not a foundation model; it is trained
from scratch per dataset. The benchmark whose framing is "foundation models
generally outperform" reports, in its own results, that the top performer on
it was not one. That result did not become the headline it was measured to
support. Press coverage widens the gap further: one trade outlet's headline
reads "Google's new forecasting model beats everyone"
[@newstack-timesfm3-2026], a claim no primary source in this paper makes.

## 4. Case study: TimesFM 2.5 to 3.0

TimesFM 3.0, the current generation, is scored zero-shot under the identical
protocol used for every other arm in this study: fixed 128-length context,
rolling one-step-ahead test window, no fitting, scored on held-out
log-likelihood against the same series and windows as `laplace`, a 136 KB
pure-Python online distributional forecaster with no pretraining and no
tunable hyperparameters.

| stratum | n series | TimesFM3 win/draw/loss vs laplace | median ΔLL (nats) |
|---|---|---|---|
| daily, economic | 2,179 | 66 / 923 / 1,190 | −0.854 |
| daily, price/returns | 7,633 | 15 / 4,593 / 3,025 | −0.616 |
| weekly, economic | 3,013 | 517 / 1,481 / 1,015 | −0.520 |
| monthly, economic | 5,576 | 193 / 3,592 / 1,791 | −0.647 |
| M4-hourly, seasonal | 414 | 8 / 241 / 165 | −0.543 |

Raw TimesFM3 loses to laplace on the majority of series in every stratum, by
a median of roughly half a nat: a large gap in log-likelihood terms. Wrapping
it in a simple post-hoc, never-worse portfolio with laplace closes nearly all
of that gap. The wrap requires no retraining and no access to model
internals; it only sees TimesFM3's own issued predictive.

| stratum | TimesFM3&lap win/draw/loss | median ΔLL | raw loss rate | wrapped loss rate |
|---|---|---|---|---|
| daily, economic | 76 / 1,383 / 720 | −0.094 | 54.6% | 33.0% |
| daily, price/returns | 152 / 7,136 / 345 | −0.008 | 39.6% | 4.5% |
| weekly, economic | 467 / 2,045 / 499 | −0.049 | 33.7% | 16.6% |
| monthly, economic | 350 / 4,480 / 365 | −0.056 | 32.1% | 7.0% |
| M4-hourly, seasonal | 58 / 352 / 4 | −0.007 | 39.9% | 1.0% |

Two things follow. The wrapped result still does not beat laplace: median
ΔLL is negative in every stratum. It is safe to include; it is not
competitive. Second, and more directly relevant to the
"newer is better" framing of successive model releases: TimesFM3&lap does not
consistently beat TimesFM-2.5&lap under the identical protocol. The
differences between generations, once both are wrapped, are within noise and
go either direction depending on stratum. A full generation of model
improvement, measured this way, changes nothing that matters for whether the
model is safe to deploy without the wrapper.

## 5. Three mechanisms

Three distinct mechanisms produce the gap between reported leaderboard
competitiveness and measured one-step probabilistic skill.

**Task mismatch.** Point-forecast accuracy on a fixed multi-horizon window is
not probabilistic accuracy on a growing online context. A model can lead one
and trail the other (Section 2).

**Contamination.** A leaderboard's held-out claim is only as good as the
auditability of every arm's training data. For a pretrained arm with a
documented or suspected training-corpus overlap, "held out" is an assertion,
not a property (Section 3).

**Reconstruction choice.** A quantile-only model does not emit a density. A
density must be reconstructed from its quantiles before it can be scored by a
proper scoring rule, and that reconstruction is a free modeling choice
independent of the model being evaluated. Holding TimesFM3 and 3,200
held-out FRED test points fixed and varying only the reconstruction
(`benchmarks/nozzles.py`, four named methods) moves the mean log-likelihood
by up to 2.4 nats and, between two methods already in independent use
elsewhere in this project's own scripts, by 0.62 nats. The mean per-point
spread across the four methods, 3.13 nats, exceeds the entire TimesFM3-vs-
laplace gap measured in every stratum in Section 4. A comparison that fixes
the model and the data and reports one number has silently fixed this choice
too, without saying so.

## 6. Discussion

A harder benchmark, by the standard this paper applies to itself, would score
a proper predictive distribution rather than a point, on an online rather
than fixed-size context, against an audited rather than assumed-clean
pretraining corpus, and would report the paired win/draw/loss distribution
rather than a single pooled mean. None of these is a novel requirement; each
is already a design choice in the harness that produced Sections 3 and 4,
which makes it a working counter-example rather than only a critique.

Everything measured here is univariate: one series, one target, scored
against one other univariate online method. A single pretrained model
amortized across many related series can exploit cross-series and panel
structure that no univariate method has access to by construction, and that
is the setting in which a foundation model's pretraining should pay for
itself most directly. This paper does not make that comparison. It is the
more decisive one: whether these models match strong univariate baselines
one-for-one and deliver a genuine multivariate or panel advantage on top,
rather than the reverse.

## 7. Conclusion

The claims made for time-series foundation models are usually true of some
metric, on some benchmark, under some definition of zero-shot, and the
announcements rarely say which. TimesFM 3.0, scored one step ahead on its own
predictive density against a 136 KB online method with no pretraining, loses
on the median series in every stratum tested, and a full model generation
does not close that gap. The benchmark these models are ranked on is not a
clean test for them by its own admitted definition, and splitting it by
pretraining overlap reverses the standard comparison. None of this argues
against the underlying architecture. It argues that the claim "state of the
art" needs the metric, the stratum, and the pretraining audit attached before
it means what it is read to mean.

## Limitations

A fourth mechanism, the sensitivity of an online method's advantage to
context length, was measured in prior internal work and is not reproduced
here: the tooling that produced those numbers is not present in this
repository on any branch, and they are not cited pending recovery or
re-derivation against the current harness.

## Reproducibility

Every number in Sections 3 to 5 is generated by a named script against a
version-controlled store, and no number in this paper is retyped from memory.

- Section 3: `benchmarks/contamination_page.py` produces
  `docs/contamination.html` (branch `study/one-flow-and-protocol-fixes`),
  task stamp `forecast:ctx256:0.16.0+77e5454/m4`.
- Section 4: `benchmarks/summarize_canonical.py` and
  `benchmarks/foundation_pages.py` produce
  `benchmarks/canonical_summary_vs_laplace.csv` and
  `docs/foundation/timesfm3.html` (branch `main`).
- Section 5 (reconstruction choice): `benchmarks/nozzles.py` (the four named
  methods) and `benchmarks/nozzle_study.py` (the comparison run: 100 series,
  32 test points each, TimesFM3, `main`), log at
  `benchmarks/_nozzle_study.log`.

## References

See `paper.bib`.
