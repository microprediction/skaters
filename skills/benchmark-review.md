# benchmark-review skill

A skill for **reviewers** (and authors) of papers that claim univariate
*distributional* time-series prediction and ship code. It gives the exact steps
to benchmark any such method fairly, through one identical scoring harness,
against the strongest opponents — and flags the traps that make published
comparisons misleading.

Use it when a paper provides a model with a `predict`-style API and claims to
forecast a full predictive distribution (density, quantiles, samples, or a CDF)
for a single series, one step (or a few steps) ahead.

## The one rule

**Every method — theirs, yours, and the baselines — must be turned into the same
predictive object and scored by the same code on the same held-out points.** If
the comparison isn't symmetric, it isn't a benchmark. In practice: wrap every
method so it emits a density object you can call `logpdf(y)` and `crps(y)` on, and
loop all of them through one scoring function.

## Step 1 — Classify the output (it decides what you can score)

| The method emits | log-likelihood? | CRPS? | How to score |
|---|---|---|---|
| A parametric density (Gaussian, Student-t, mixture) | **yes** | yes | evaluate the density directly |
| Samples (DeepAR, Chronos-T5, Lag-Llama) | approx (KDE) | yes (sample estimator) | KDE for logpdf; flag it as a reconstruction |
| Quantiles only (TimesFM, Chronos-Bolt, MAPIE) | approx (reconstruct) | yes | smoothed-mixture from quantiles; flag tail-limited |
| A CDF / conformal predictive system (crepes) | **no** (structurally) | yes | CRPS only — cannot be logpdf-scored at all |

The single most common error in this literature is comparing a density method to a
quantile/CDF method **only on CRPS or coverage**, where the density gets no credit
for its tails. Report log-likelihood whenever every method admits it; note exactly
which methods are reconstructions.

## Step 2 — Fix the prediction target

Decide once and apply to all: forecast the **one-step change** (first difference,
or log-difference for positive levels) or the **level**. Changes keep
log-likelihood comparable across series of different scale and isolate the
heavy-tailed innovation stream. Whatever you pick, *every* method forecasts the
same target and is scored on the same realized value.

## Step 3 — Pick the protocol, and don't mix them

- **Rolling one-step-ahead with periodic refit** for fittable models (ARIMA, ETS,
  GARCH, neural). Expanding or capped window; refit every N steps; score each step.
- **Zero-shot, fixed context, no refit** for pretrained foundation models — a
  *different* protocol. Slide a context window; never fine-tune per series (it
  catastrophically overfits one short stream). Report it separately and say so.

## Step 4 — Choose a bias-free universe

Don't hand-pick series. Use a fixed rule (e.g. top-N FRED series by popularity),
keep a minimum length, and **split continuous vs repeat-heavy** (fraction of
exactly-repeating changes). Grid/administrative series (policy rates, posted
prices) reward exact-value mass and can dominate an aggregate; report the
continuous subset separately.

## Step 5 — The harness

```
for each series:
    for each method:
        for each test step t:
            D = method.predict_distribution(history up to t)   # a Dist
            logpdf[method] += D.logpdf(y_t)
            crps[method]   += D.crps(y_t)
```

Represent parametric Student-t / sample / quantile outputs as a finite Gaussian
**scale mixture** so a single `Dist` (and a single `logpdf`/`crps`) scores
everyone identically. Verify the representation matches the analytic density to
~1e-3 before trusting it.

## Step 6 — Aggregate honestly

- Report **per-series win-rate** (fraction of series where the method wins), not
  family-clustered rates — clustering can inflate a number by spreading wins
  across many singleton families while collapsing losses into a few large ones.
- Report **both** log-likelihood and CRPS, **and** the continuous subset.
- Report a runtime / dependency-weight axis too: accuracy at 100× the compute is
  not the same win.
- Quote mean continuous log-likelihood, not just win-rates — a 51% win-rate with a
  large mean gap is different from 51% with a tiny one.

## Step 7 — Adversarial checklist (what reviewers should demand)

- Did they score the density on **log-likelihood**, or only CRPS/coverage? If a
  competitor only emits a CDF, that competitor *cannot* take the likelihood field —
  state it; don't quietly drop the metric.
- Are the baselines the **toughest** available (GARCH-t for heavy tails, conformal
  for CRPS, a real neural/foundation model), or **straw men** (a naive mean with a
  conformal wrapper)?
- Is the mean model held **constant** across the wrapped comparison, or does a
  strong method get a strong mean and a weak one a weak mean?
- Are sample/quantile densities **reconstructions**? Then their logpdf is
  approximate — say so and lean on CRPS for them.
- Is the protocol **consistent** (no zero-shot vs refit mixing in one table)?
- Is the universe **fixed in advance**, or selected after seeing results?
- Is the whole thing **reproducible** from one script?

## Reference implementation

`skaters` ships exactly this harness: `benchmarks/study.py` (one scorer, one
opponent registry). The `sota` preset runs the rolling baselines (AutoARIMA,
AutoETS, statsmodels SARIMAX/ETS, GARCH-t, NeuralForecast-t, conformal+ACI,
Prophet); the `conformal-scale` preset runs naive-mean conformal across the whole
daily universe; and `benchmarks/foundation_study.py` is the zero-shot protocol
(Chronos, TimesFM, Moirai, Lag-Llama). Every method becomes a `Dist`; everything
is scored on held-out log-likelihood and CRPS; results are per-series. Add a new
method to the registry and you have a fair comparison in an afternoon.
