---
title: 'skaters: online distributional time-series forecasting by conjugation, in Python and JavaScript'
tags:
  - Python
  - JavaScript
  - time series
  - probabilistic forecasting
  - online learning
  - proper scoring rules
  - calibration
  - extreme value theory
authors:
  - name: Peter Cotton
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Independent researcher, United States
    index: 1
date: 10 July 2026
bibliography: paper.bib
---

# Summary

`skaters` is an online, univariate time-series forecaster whose every
prediction is a full probability distribution. It is built by *conjugation*:
an invertible transform wraps an inner forecaster, pushing each observation
forward, forecasting in the transformed space, and pulling the predictive
distribution back through the inverse. Because the inner forecaster can
itself be a conjugation, models nest onto a single distributional leaf, and
an ensemble is just another forecaster.

The library exposes one factory, `laplace`, with no required tuning
parameters. Each call consumes one observation and returns k predictive
distributions plus a calibration state: the probability integral transform
and normalized surprise of the arriving point under the forecasts
previously issued for it. Since v0.13.0 every predictive carries
generalized-Pareto tails fitted online by censored maximum likelihood
[@diks2011likelihood], so stated tail probabilities match measured
frequencies: on 142 economic series the nominal 99.9% central interval
covers 99.85% empirically, where a Gaussian read covers 99.13%.

The package is written twice, in pure Python with no dependencies
(`pip install skaters`) and in zero-dependency JavaScript
(`npm install skaters`). A parity suite checks about 100,000 probe values
to $10^{-6}$ agreement on every run, so a model trained on a server
continues bit-compatibly in a browser via Pyodide [@pyodide2021].

# Statement of need

Density forecasts are reusable objects: the same predictive supports
pricing, risk limits, threshold alarms, and simulation. Most accessible
forecasting software returns point forecasts or intervals, refits in
batch, or requires a scientific-computing stack. Practitioners who need a
predictive *distribution* per tick, updated online at microsecond-to-second
cadence, on a server or in a browser, have had to assemble one from parts.

`skaters` fills that gap with a single dependency-free function. On 894
continuous non-price FRED series it leads classical, neural, and
foundation-model baselines on held-out log-likelihood under a rolling
one-step protocol; on asset prices a GARCH-t model remains preferable, a
split reported rather than averaged away. The calibration state turns the
forecaster into an anomaly detector with stated false-alarm rates: alarm
when $\mathrm{erfc}(|z|/\sqrt{2}) < \alpha$, with measured rates near
nominal on economic series. Methods, benchmarks, and the tail-calibration
studies are documented in a companion methods paper in the repository and
at https://skaters.microprediction.org.

The design distills ideas from the author's earlier `timemachines`
package [@cotton2021timemachines] and from live distributional-prediction
contests on the microprediction platform [@cotton2022microprediction],
where multi-level prediction of residual streams anticipated the
conjugation recursion.

# Acknowledgements

Benchmark data are drawn from the Federal Reserve Economic Data (FRED)
service. The UCR Anomaly Archive [@wu2023current] supports the
calibration studies.

# References
