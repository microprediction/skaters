---
title: 'skaters: online distributional time-series forecasting by conjugation'
tags:
  - Python
  - JavaScript
  - Rust
  - R
  - Julia
  - time series
  - probabilistic forecasting
  - online learning
  - proper scoring rules
  - calibration
  - extreme value theory
authors:
  - name: Peter Cotton
    orcid: 0000-0003-1832-2924
    affiliation: 1
affiliations:
  - name: Independent researcher, United States
    index: 1
date: 11 November 2026
bibliography: paper.bib
---

# Summary

A forecast is more useful when it says how uncertain it is. `skaters` takes
a stream of numbers, such as an interest rate, an unemployment figure or a
sensor reading, one value at a time, and after each value states the whole
range of what the next value might be and how likely each part of that
range is. It needs no training, no settings and no other software, and it
runs in Python, in a web browser and in four other languages.

Technically, `skaters` is an online, univariate time-series forecaster whose every
prediction is a full probability distribution. It is built by *conjugation*:
an invertible transform wraps an inner forecaster, pushing each observation
forward, forecasting in the transformed space, and pulling the predictive
distribution back through the inverse. Because the inner forecaster can
itself be a conjugation, models nest onto a single distributional leaf, and
an ensemble is just another forecaster.

The default factory, `laplace`, has no tuning
parameters. Each call consumes one observation and returns k predictive
distributions plus a calibration state: the probability integral transform
and normalized surprise of the arriving point under the forecasts
previously issued for it. Since v0.13.0 every predictive carries
generalized-Pareto tails fitted online by censored maximum likelihood
[@diks2011likelihood], so stated tail probabilities match measured
frequencies: on 142 economic series the nominal 99.9% central interval
covers 99.85% empirically, where a Gaussian read covers 99.13%.

The reference is pure Python with no dependencies (`pip install skaters`),
with independent ports in JavaScript (`npm install skaters`), Rust (an
optional compiled backend), R and Julia. A parity suite checks about
100,000 probe values to $10^{-6}$ agreement in continuous integration, so a
model trained on a server continues in a browser via Pyodide
[@pyodide2021] or in another language mid-stream. A second forecaster,
`granger`, mixes `laplace` with a copy of itself whose
parameters were trained on large panels of economic and hourly series; the
mixture is the Aggregating Algorithm under log loss, so on any series its
total log score is never more than $\log 4$ behind `laplace`'s.

# Statement of need

Density forecasts are reusable objects: the same predictive supports
pricing, risk limits, threshold alarms, and simulation. Most accessible
forecasting software returns point forecasts or intervals, refits in
batch, or requires a scientific-computing stack. Practitioners who need a
predictive *distribution* per tick, updated online at microsecond-to-second
cadence, on a server or in a browser, have had to assemble one from parts.
`skaters` supplies one as a single dependency-free function. Scored one
step ahead on FRED change series, it beats AutoARIMA, AutoETS, AutoTheta
and GARCH-t on held-out log score at every frequency and every zero-shot
foundation model on daily series; the newest foundation models are ahead
on monthly and weekly series at hundreds to thousands of times its cost
per forecast, and on asset prices `laplace`, GARCH-t and the foundation
models are level. These splits are reported rather than averaged away
[@cotton2026stronger]. The calibration state doubles as an anomaly detector with stated
false-alarm rates.

# State of the field

Established open-source forecasters occupy different corners: `statsmodels`
[@seabold2010statsmodels] and `darts` [@herzen2022darts] are batch-refit and
largely point- or interval-oriented, Prophet [@taylor2018forecasting] targets
batch seasonal decomposition, `GluonTS` [@alexandrov2020gluonts] is
distributional but assumes a deep-learning stack and offline training, and
`river` [@montiel2021river] is natively online but centred on point
prediction. None provides an online predictive density as a single
dependency-free function, and none runs unchanged in a browser. The design
distills ideas from the author's earlier `timemachines` package
[@cotton2021timemachines] and from live distributional-prediction contests
on the microprediction platform [@cotton2022microprediction], where
multi-level prediction of residual streams anticipated the conjugation
recursion. Contributing these ideas to an existing package was considered and
rejected: each of those libraries is built around batch refitting, point
forecasts or a numerical stack, and the requirements here (a predictive
distribution at every step, state that is plain data, no dependencies, and
identical results across languages) would have meant replacing their core
abstractions rather than extending them.

# Software design

Every forecaster satisfies one protocol: a pure function
`(y, state) -> (dists, state)` that consumes one observation and returns
$k$ predictive distributions plus its own next state. State is an explicit
dictionary, never hidden in an object, so a model can be checkpointed as
JSON, resumed elsewhere, or handed across a language boundary mid-stream.
Conjugation is function composition under this protocol: a transform wraps
an inner skater, and because the wrapped object satisfies the same
protocol, models nest to any depth and an ensemble is just another
skater. The public surface is two factories, `laplace`, whose defaults
require no tuning, and `granger`, whose trained parameters ship as data
in every port.

The main trade-offs were these. Online updating can cost accuracy on
series where a full refit would pick up structure late in the sample, in
exchange for constant cost per observation and a forecast that is always
current. A fixed, tuning-free population of transform chains, weighted by
their running log score, gives up the bespoke fit of per-series model
selection but cannot overfit a single series, and keeps every forecast
reproducible. Pure Python keeps installation trivial at a speed cost of
about twenty times, which the optional Rust core recovers. Keeping five
ports parity-locked to $10^{-6}$ makes every numerical change land
everywhere at once, a maintenance cost the parity suite turns into a
check rather than a hope. Finally, `granger` trades a little of
`laplace`'s simplicity for trained parameters, and the Aggregating
Algorithm bounds what that trade can cost.

# Research impact statement

The package is the measurement instrument in three research papers: the
methods paper [@cotton2026transforms]; a study of the conformal
information gap, which uses `laplace` and its transforms as a nested
ladder of representations [@cotton2026gap]; and a benchmark study of
foundation time-series models, which supplies the online distributional
reference that published suites omit and shows that the density
reconstruction of a quantile model can move a comparison by half a nat
[@cotton2026stronger]. Its benchmark harness also generates the public
leaderboards at https://foundationalprediction.com, which pair more than a
dozen foundation models (Chronos-2, TimesFM 3.0, Timestral, t0, TimeH2O,
Toto 2.0, TiRex-2, Moirai 2.0 and others) with classical baselines on
identical series, one horizon at a time, with training-data overlap
disclosed per model. Beyond the author's papers, `skaters` is the core dependency of
`timemachines` [@cotton2021timemachines], an established
anomaly-detection and sequential-decision package (445 stars and 54 forks
since 2021) whose current releases are built on the calibrated surprise
streams `skaters` produces, and of `prophet-laplace`, which wraps Prophet
[@taylor2018forecasting] in `laplace` to give it calibrated densities. In October and November 2026 it was downloaded
about 2,800 times a month from PyPI and 440 times a month from npm; the
repository has been forked by six other developers, and three outside
contributors have landed changes through public pull requests. The
browser build drives teaching demonstrations at
https://skaters.microprediction.org.

# AI usage disclosure

The author used Anthropic's Claude models through Claude Code throughout
development: Claude Opus 4.6, 4.7, 4.8, 5 and 5.5, Sonnet 5, and Fable 5
and 5.1. At least 525 of the 1,916 commits on the main branch name a
Claude model as co-author (squash merges drop the trailer, so this is a
floor). The assistance covered code generation and refactoring, the R,
Julia, Rust and JavaScript ports, test and parity scaffolding, benchmark
scripts, numerical debugging, and drafting and copy-editing of
documentation and this paper. The author framed the problem and made the
core design decisions: conjugation of a forecaster by an invertible
transform as the single abstraction, a predictive distribution as the only
output, state as plain data, a fixed-parameter default with no tuning,
Python as the reference with every port parity-locked to it, the
Aggregating-Algorithm construction of `granger` and its bound, and the
evaluation protocol of isolated horizons, paired per-series tests and
stated density reconstructions. The author reviewed and validated the
generated code and text and is responsible for their accuracy; every
benchmark number is regenerated from version-controlled results by the
scripts in `benchmarks/`, and the parity suite checks every port against
the reference in continuous integration.

# Acknowledgements

Intech Investments funded the now-defunct microprediction distributional
prediction platform whose multi-level residual-stream mechanism this
package distills. Benchmark data are drawn from the Federal Reserve
Economic Data (FRED) service. The UCR Anomaly Archive [@wu2023current]
supports the calibration studies.

# References
