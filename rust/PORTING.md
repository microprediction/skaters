# Porting map: Python skaters -> Rust

Python is the authority (`src/skaters/` in microprediction/skaters). The gate
is `cargo test --release` against `parity/vectors.json` at 1e-6.

| module | Python source | status |
|---|---|---|
| mathx (fsum, gaussian helpers) | dist.py internals | DONE |
| dist (mixture type, ulp-tolerant prune) | dist.py | DONE |
| runstats (Welford) | runstats.py | DONE |
| leaf, scale_mixture_leaf, crps_leaf, garch_leaf | leaf.py | DONE |
| transforms (diff, frac, standardize, ema, ou, theta, drift, holt, garch, seasonal, seasonal_anchor, seasonal_scale, power, yeo-johnson with `exact`, log_transform, gaussianize, ar, grouped_ar) | transform.py | DONE |
| PushforwardDist (maps as serde data, affine/shift/scale) | pushforward.py | DONE |
| conjugate | conjugate.py | DONE |
| ema skater | ema.py | DONE |
| precision-weighted ensemble | ensemble.py | DONE |
| bayesian ensemble | bayesian.py | DONE |
| multiscale | multiscale.py | DONE |
| sticky (lattice projection) | sticky.py | DONE |
| terminal-leaf ensemble | terminal.py | DONE |
| tails (Acklam phi_inv, censored-ML GPD, SplicedDist, gpdtails) | tails.py | DONE |
| parade (PIT/z state, finite-input gate) | parade.py | DONE |
| laplace composition, candidate population, flesaker | api.py | DONE |
| adaptive search (dantzig) | search.py | DONE |
| spec build path | spec.py | DONE |
| periodicity detector | periodicity.py | DONE |
| covariance estimators | cov/ | DONE |
| terminal ensemble adaptive temperature (`adapt`) | terminal.py | DONE |
| homogenize, make_candidates, HomogenizedDist (all couple modes) | homogenize.py | DONE |
| residual_transform (m0, m1, m2), CorrectedDist, ResidualDiagnostics | residual_transform.py | DONE |
| dantzig, laplace(leaf=...) | api.py | DONE |
| canonical state (state_to_json, load_state) | state.py, docs/STATE.md | DONE |
| mahalanobis, zbank | anomaly.py | not ported |

Porting notes specific to Rust:

Python creates skater state lazily on the first call, and several transforms
treat that first call specially (return 0.0, seed the level or anchor). Each
transform struct carries an `init` flag reproducing exactly that branch.
Structs whose lazy init is indistinguishable from default construction
(leaves, AR) are seeded at construction.

Python's built-in `sum()` on floats is Neumaier-compensated since 3.12. Every
site the reference spells as `sum(...)` uses `mathx::fsum`; every site
spelled as a `+=` loop stays a naive loop. Mixing these up passes most
probes and then diverges the prune tie-breaks.

The sticky wrapper's frequency table is a Python dict keyed by exact float
values, so insertion order is semantic (stable sort ties). It is a
`Vec<(f64, f64)>` here, updated in dict order: decay all, drop below the
floor, then bump or append the current value.

Python float `**` maps to `libm::pow`; integer exponents in the reference
(OU's `phi ** h`) still go through pow to match. Constants that Python
computes with `round()` at import time (the crps_leaf FINE scale grid) are
embedded as literals verified against CPython.

Multiscale keeps one sub-skater instance per phase per scale (Python keeps
one closure and swaps state dicts; same arithmetic, different plumbing).

The adaptive search stores each pool candidate as a live `Sk` value next to
its transform-name recipe, so the whole state stays plain serde data (the
same finding the R port reached). Tie-breaking mirrors Python exactly:
expansion order is the `(score, index)` tuple sort with `reverse=True`
(score descending, then pool index descending), the pool-cap prune removes
the first argmin, and the logpdf loss is clamped to [-20, 20] with the lower
clamp catching NaN. A detected seasonal period injects a second grammar
entry that can shadow a base `seas(p)` by name; recipe rebuilds resolve
names last-wins, as Python's dict comprehension does. The infinite default
cost budget round-trips JSON as null.

Canonical state lives in `src/state.rs`, one `State` impl per skater, kept
apart from the structs so the native serde layout is unchanged. A Rust
struct holds configuration and state together; the impl writes only the
state part, with Python's keys, integer fields as JSON integers and floats
as floats, and `null` for a fresh skater (Python's `None`). Loading `null`
resets to fresh. A search pool entry is rebuilt from its recipe with the
grammar in force (the base table plus `seas(p)` per detected period, in
detection order), then its `s` is loaded. `flesaker`'s state is the inner
laplace's state itself, as in Python (`FConj::bare`). theta writes `slope`
from its second observation on, as Python does. Rust's own state reached
from scratch matches Python's field by field to 1e-4 in `tests/resume.rs`:
running sums over hundreds of steps (homogenize's discounted log weights)
collect the ports' last-bit differences in erf, exp and log to a few 1e-6,
while every probe stays within 1e-6.

`homogenize` and `residual_transform` wrap any `Forecaster` and emit new
`PDist` kinds (`Homog`, `Corrected`). Like Python's duck-typed classes they
have no affine, shift or components; a transform that needs them panics
where Python raises.

Parity vectors provenance: `parity/vectors.json` is copied from
microprediction/skaters (`parity/vectors.json` there); refresh by rerunning
`parity/gen_vectors.py` in that repository and copying the output here.
