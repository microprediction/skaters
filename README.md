# skaters

Home of **Laplace**, a light, fast, automatic **distributional** univariate time-series prediction algorithm. It also improves other time-series models, including Prophet. Recommended for non-price economic time series.

One call, zero dependencies, every prediction a full probability *distribution* computed online in O(1).

<p align="center">
  <a href="https://skaters.microprediction.org/"><img src="https://img.shields.io/badge/docs%20%26%20live%20demos-skaters.microprediction.org-4a3aff?style=for-the-badge" alt="Documentation and live demos"></a>
  <a href="https://skaters.microprediction.org/languages.html"><img src="https://img.shields.io/badge/implementations-Python%20%7C%20JS%20%7C%20R%20%7C%20Julia%20%7C%20Rust-1a8c4a?style=for-the-badge" alt="Python, JavaScript, R, Julia and Rust"></a>
</p>

## Quick start

```bash
pip install skaters
```

```python
from skaters import laplace

f = laplace(k=3)
state = None
forecast = None            # the fan issued LAST tick, aimed at this y
for y in observations:
    if forecast is not None:
        forecast[0].logpdf(y)          # one-step-ahead log score
        forecast[0].cdf(y)             # one-step-ahead PIT
    forecast, state = f(y, state)
    forecast[0].mean                   # point forecast for the NEXT tick
    forecast[0].std                    # uncertainty
    forecast[0].quantile(0.975)        # upper edge of the central 95% band
```

- Each call takes one observation and returns a predictive distribution (`Dist`) per horizon, `h = 1, ..., k`.
- A `Dist` carries the mean, spread, quantiles and density at once.
- Score a forecast only against values that arrive after it was issued.
- `state["pit"]` and `state["z"]` give a calibrated surprise for every point.

The release on PyPI is 0.16.0. `granger`, `flesaker` and `log_transform` arrive in the next release; until then, `pip install git+https://github.com/microprediction/skaters`.

## Demonstrations

Live in your browser:

- [Playground](https://skaters.microprediction.org/demos/playground.html): pick a regime and watch the forecast adapt
- [Race](https://skaters.microprediction.org/demos/race.html): against classical baselines on FRED series
- [Whitening](https://skaters.microprediction.org/demos/normalization.html): against a rolling z-score
- [Rosenblatt bijection](https://skaters.microprediction.org/demos/rosenblatt.html): the series and its N(0,1) image
- [Pyodide](https://skaters.microprediction.org/demos/pyodide.html): the Python package itself, in the browser

## Have a conversation about skaters

Paste the [primer](https://skaters.microprediction.org/#conversation) into ChatGPT, Claude or any chat assistant, then describe your series and what you need.

## How Laplace complements foundational models

Laplace was written to monitor hundreds of thousands of private and public economic series, because we couldn't find anything better. Some foundational models are slightly better, but far less usable at present. Your mileage may vary.

- **Tiny and dependency-free**, in five languages ([ports](https://skaters.microprediction.org/languages.html)).
- **Fast:** microseconds per update on one CPU thread, against milliseconds or more for a pretrained model ([speed](https://foundationalprediction.com/speed.html), [performance](https://skaters.microprediction.org/performance.html)).
- **A reference point:** its secondary use is to mark the advances in foundational time-series models ([leaderboards](https://foundationalprediction.com/)).

## Where foundational models are better

On monthly, weekly and hourly series. The best foundational model on each wins far more series than it loses (paired per series on log score):

| Series | Best model | Wins / draws / losses | Median gain (nats) | CRPS ratio |
|---|---|--:|--:|--:|
| Monthly | Timestral-209M | 2,037 / 3,182 / 381 | +0.11 | 0.88 |
| Weekly | TimeH2O | 1,383 / 1,324 / 306 | +0.11 | 0.82 |
| Hourly (M4) | TimeH2O | 186 / 228 / 0 | +0.18 | 0.83 |

- **Daily economic series:** every foundational and classical model loses more series than it wins.
- **Daily prices:** the foundational models are level with `laplace`; a fitted GARCH-t is ahead (743 wins, 216 losses).

Wins and losses are per-series Diebold–Mariano verdicts. A CRPS ratio below 1 favours the compared model.

<p align="center">
  <img src="https://skaters.microprediction.org/assets/radar-canonical.png" alt="Radar chart of strength against laplace on log score, by stratum, for Timestral-209M, TimeH2O, TimesFM 3.0, t0-gamma and GARCH-t; laplace is the dashed ring." width="520">
</p>

<p align="center">
  <img src="https://skaters.microprediction.org/assets/laplace-foundational-models.gif" alt="A cyclist pops a wheelie on a mountain bike alongside a professional peloton; the peloton is labelled Foundational Models and the wheelie rider Laplace." width="420"><br>
  How each foundational model compares, series by series: <a href="https://foundationalprediction.com/">foundationalprediction.com →</a>
</p>

## One general forecaster?

skaters exposes one general forecaster, `laplace`, and one trained one, `granger`. Everything else is a building block you can compose.

| | what it is |
|---|---|
| `laplace(k)` | the general forecaster: a likelihood-weighted ensemble of transform chains with a distributional leaf; multi-step to `k=12` |
| `granger(frequency=...)` | `laplace` with hyperparameters trained per frequency (monthly, weekly, hourly), mixed with `laplace` so its total log score is never more than log 4 behind |
| `flesaker(lower=0)` | experimental: `laplace` on `log(y - lower)`, mapped back exactly, for series with a known bound |

`laplace` is fully autonomous: no training, no tuning. So it will not beat a tuned model, a tuned version of itself (`granger`), or a construction built for what you know about a series, such as a positive one.

It does not use covariates; for those see [ice-skaters](https://ice-skaters.microprediction.org) and the [exogenous-variables skill](https://skaters.microprediction.org/skills.html#exogenous-variables).

## The toolkit

Every forecaster is built from transforms, leaves and ensembles that you can recombine. A transform changes the coordinates, a skater forecasts in them, and `conjugate` maps the forecast back:

```python
from skaters import conjugate, leaf, ou_transform, laplace, log_transform

spread = conjugate(leaf(k=10), ou_transform(kappa=0.1), k=10)     # mean reversion
positive = conjugate(laplace(), log_transform(lower=0.0))          # a positive series
```

The transforms and ensembles are in the [methodology guide](https://skaters.microprediction.org/guide.html); runnable recipes are on the [examples page](https://skaters.microprediction.org/examples.html).

## A bijection, not just a forecaster

Each arriving point maps through its own predictive cdf, z_t = Φ⁻¹(F_t(y_t)). This is a causal bijection on paths (Rosenblatt 1952), and under calibration its image is iid N(0,1).

Run any forecaster in those coordinates, then score it back in the original ones by an exact change of variables. [See it live →](https://skaters.microprediction.org/demos/rosenblatt.html)

## Documentation

- [Examples](https://skaters.microprediction.org/examples.html): runnable recipes
- [FAQ](https://skaters.microprediction.org/faq.html): why it exists, what it does and does not do, how not to use it
- [Methodology](https://skaters.microprediction.org/guide.html): how `laplace` and `granger` are built
- [Scope](https://skaters.microprediction.org/scope.html): prior knowledge, horizons, units
- [Metrics](https://skaters.microprediction.org/metrics.html): why log likelihood is the default score
- [Claude skills](https://skaters.microprediction.org/skills.html): copyable instructions for common tasks
- Ports, parity-checked to 1e-6: [Python](https://skaters.microprediction.org/ports/python.html), [torch](https://skaters.microprediction.org/ports/torch.html), [Rust](https://skaters.microprediction.org/ports/rust.html), [JavaScript](https://skaters.microprediction.org/ports/javascript.html), [R](https://skaters.microprediction.org/ports/r.html), [Julia](https://skaters.microprediction.org/ports/julia.html)
- [REFERENCE.md](REFERENCE.md): the detailed reference (architecture, `Dist`, transforms, ensembles, spec system, `skaters.torch`, theory)

## Papers

- Transforms all the way down, the methods paper: [PDF](papers/skaters-jss.pdf), [SSRN](https://papers.ssrn.com/abstract=7220478)
- A stronger univariate benchmark for foundational time-series model evaluation: [PDF](papers/stronger-benchmark/stronger-benchmark.pdf), [SSRN](https://papers.ssrn.com/abstract=7583618), [reproduce](papers/stronger-benchmark/REPRODUCE.md)
- On the importance of evaluating foundational time-series models one step ahead in an investment context: [PDF](https://foundationalprediction.com/horizon-note.pdf)

## Cite

Please cite the first paper listed, *Transforms all the way down* ([SSRN 7220478](https://papers.ssrn.com/abstract=7220478)), as it explains the methodology.

```bibtex
@misc{cotton2026skaters,
  title  = {Transforms All the Way Down --- Automatic Online Distributional
            Forecasting by Conjugation},
  author = {Cotton, Peter},
  year   = {2026},
  note   = {SSRN 7220478, https://skaters.microprediction.org}
}
```

## Heritage

skaters distils ideas from [timemachines](https://github.com/microprediction/timemachines), which gave dozens of time-series packages a common interface. It is a from-scratch rewrite for speed, distributional prediction and the browser.
