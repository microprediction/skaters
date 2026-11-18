# Long-memory conditional centering

This experiment adds an ordinary causal transform whose center is learned
from earlier visits to similar states. A state contains the current level,
the last movement, and the movement over four ticks. A bounded archive of
512 labeled transitions supplies the expected next movement. The transform
has no seasonal-period parameter and emits one scalar residual per tick.

At origin t, let s[t] contain only observations through t and let m(s[t])
be the predicted next level. Then

    z[t+1] = y[t+1] - m(s[t])
    y[t+1] = z[t+1] + m(s[t]).

Only after emitting z[t+1] does the transform learn the transition from
s[t] to y[t+1]. The first center is zero, so the first observation is retained.
The archive is bounded and its weights decay with age; feature scales use
the existing EWMA covariance estimator. Feature distances select the eight
nearest states, whose observed next movements receive inverse-distance and
recency weights. These are fixed research settings, not fitted benchmark
hyperparameters.

Position alone cannot distinguish opposite directions around an orbit. The
delayed slopes let the same level have a positive center adjustment on one
visit and a negative adjustment on another. Memory determines how far back
the transform can find comparable states. It does not specify a period.

## Plumbing

`OrbitTransform` unpacks as the existing `(forward, inverse_k)` pair. There
is no new conjugation interface or horizon-specific training stream.

```python
from skaters.conjugate import conjugate
from skaters.leaf import scale_mixture_leaf
from skaters.parade import parade
from research.orbit import orbit_transform

k = 3
transform = orbit_transform()
f = parade(conjugate(scale_mixture_leaf(k=k), transform, k=k), k=k)
state = None
for y in [3.0, 3.5, 4.0, 3.5, 3.0, 2.5, 2.0, 2.5]:
    predictives, state = f(y, state)
```

`benchmark.orbit_extras(k)` builds one ordinary depth-one candidate using
the same residual leaf as Laplace's existing candidates. The established
`laplace_extra_periods(..., periods=(), extra=orbit_extras)` research hook
appends it to the candidate pool. Laplace scores its issued one-step
predictive, weights its horizon means alongside the existing candidates,
and learns the final residual distribution through its terminal leaves.
The registry exposes this as `laplace(+orbit)`. `orbit-leaf` evaluates the
candidate alone. Default Laplace and its signature are unchanged.

The new transform also composes with the existing EMA and exact logarithmic
transforms. One-step translation preserves the inner predictive's CDF,
quantiles, density, and shape, including a nonlinear pushforward predictive.

## What the inverse means

For any fixed starting state and complete residual path,
`transform.inverse_path(residuals, state)` reconstructs the original path.
It advances a private copy of the same state, including the archive updates
implied by the reconstructed observations. It never learns these simulated
transitions in the live state. This is an invertible causal triangular
series map, with unit conditional Jacobian. The usual one-step conditional
CDF/Rosenblatt construction still applies.

At one step, `inverse_k` adds a known center to the entire distribution,
exactly. For multiple steps, future centers depend on future observations.
Marginal residual predictives alone do not specify their joint law. This
prototype assumes independent residual marginals at the current origin,
draws 64 antithetic sample paths, applies the exact path inverse, and
moment-matches each recovered marginal after the first to a Gaussian.
Nonzero residual means and earlier uncertainty both propagate through the
state. This is a working distributional approximation, not an exact inverse
of an unspecified joint forecast. Callers with joint residual samples can
instead send their actual paths directly to `inverse_path`.

Simulation is deterministic and uses the same path prefixes when k changes.
The transform state is pure picklable data; rebuilding the transform with
the same configuration resumes it. The one-step update costs O(memory *
number_of_features), plus nearest-neighbor selection. A multi-step inverse
costs O(paths * k * memory * number_of_features). This Python prototype has
not been optimized or ported to Rust, JavaScript, R, or Julia.

Finite observations on a regular clock are required by the raw transform.
`parade` supplies the existing missing-value handling when wrapping a
standalone chain; the pooled Laplace adapter already includes it. As in the
existing pipeline, the base learner freezes across gaps, so this does not
infer physical phase through unobserved intervals.

## Mechanism checks

Run from the repository root with Python 3.10 or later:

```bash
PYTHONPATH=.:src python research/orbit/synthetic.py
PYTHONPATH=.:src:benchmarks pytest research/orbit -q
```

`results_transform.csv` records fixed-stream diagnostics after 640 warm-up
observations, over 256 subsequent observations. These measure the conditional
center, not calibrated forecast distributions. The ideal orbit has period
64, amplitude 3, and level 10; that period is supplied only to the data
generator. The 512-transition archive removes its next movement to floating
precision and reconstructs another 128 values from zero residuals. The
16-transition archive has one-step center RMSE 0.0226 and its long path drifts.

With observation noise of standard deviation 0.15, the long-memory center's
RMSE is 0.2198, versus 0.2970 for the last-value center. On white noise it
overfits relative to the zero center; on the random walk it overfits relative
to the last value. This is a candidate for the pool, not a universally useful
replacement center.

Tests cover score-before-update labeling, exact path round trips including
bootstrap and archive eviction, checkpoint restoration, bounded memory,
directional conditioning, a 128-step orbit, one-step density and quantile
transport, prefix consistency, independent linear-Gaussian moment oracles,
both orders of composition, missing ticks through `parade`, and the
canonical adapter's forecast-origin alignment.
They also check a nonsinusoidal orbit at a different, unconfigured period,
and conditional motion in a chaotic logistic-map stream without a seasonal
clock. The latter is a one-step mechanism check, not a claim of accurate
long-range chaotic trajectories.

## M4 Hourly protocol

```bash
PYTHONPATH=.:src:benchmarks python research/orbit/run_m4.py --horizon 1 --workers 8
```

This uses `benchmarks/run_arm.py`, `predictions.py`, and
`summarize_canonical.py`. It scores the last 64 changes of all 414 M4 Hourly
series after at most 1,000 historical changes, using the canonical corpus's
log changes when levels are positive. The forecast target is one hourly
change. This is not the official M4 load-level forecast-window task.

CSP uses `csp-forecaster==0.2.0`, pinned source revision
`529d91865b2c8c6c0c08192c1a2ea35cfb94877c`, period 24, a trailing 750-value
fit window, and 256 predictive samples. The existing adapter seeds each
forecast deterministically from the input series and forecast origin. The
input `Hourly-train.csv` has SHA-256
`ea59b7783573c49077a835ab6465c7d66f1474783360f310988a9a737fbca62f`.

The first run reuses the unchanged CSP and default-Laplace canonical rows
from commit `0095d6a1170e2d38d823e65e6ae94e97e943c18b`, under precisely
this one-step protocol. `--baseline-cache DIRECTORY` is an optional shortcut
for this identical-protocol cache; omit it to refit the baselines. The script
checks that all four methods cover the same 64 target values for each series.
The two orbit arms were evaluated afresh with settings fixed before that run.

Small canonical score and coverage summaries are committed here. Per-step
tapes and logs remain outside the source repository. Distributional
performance beyond one step has not yet been benchmarked on M4 Hourly.

| Model | Reference | Median log-score difference | Median CRPS ratio | Log-score win/draw/loss |
| --- | --- | ---: | ---: | ---: |
| Laplace + orbit candidate | Default Laplace | +0.0002 | 1.0000 | 68 / 304 / 42 |
| Laplace + orbit candidate | CSP | -0.0564 | 1.0223 | 28 / 241 / 145 |
| Orbit candidate alone | CSP | -0.4328 | 1.4397 | 22 / 114 / 278 |

Positive log-score differences and CRPS ratios below one favor the model.
The pooled improvement over default Laplace is tiny on the median series.
This initial candidate does not close the gap to CSP. The mechanism tests
establish an invertible long-memory transform; they do not establish a broad
forecasting improvement.

The complete 105,984-row tape, shard logs, configuration, input checksum,
and source-file checksums are supplied as `m4-hourly-orbit-evidence.zip`,
SHA-256 `1abae77f42320eef583309c7459e04822305af6ce90de6c6164da471db2fb270`.
A maintainer can host that archive as a release asset in
`microprediction/skaters-benchmarking-data`; it is available in the originating
conversation until then.

## Validation

With Python 3.12.14, the full regression run (`pytest tests research/orbit`)
completed with 1,709 passed, 33 skipped, and 18 expected failures. The final
research suite, including additional mechanism and benchmark-hook checks,
passes all 44 tests. The focused existing conjugation, transform, multi-step
inverse, and Laplace-contract checks also pass. The README example executes,
and every research source file parses with the Python 3.10 grammar.

No production source, port, or parity vector changes in this experiment.
The pool hook with no extra candidate reproduces default Laplace exactly
at k=1 and k=3 in the integration checks.
