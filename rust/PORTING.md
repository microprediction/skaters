# Porting map: Python skaters -> Rust

Python is the authority (`src/skaters/` in microprediction/skaters). The gate
is `cargo test --release` against `parity/vectors.json` at 1e-6.

| module | Python source | status |
|---|---|---|
| mathx (fsum, gaussian helpers) | dist.py internals | DONE |
| dist (mixture type, ulp-tolerant prune) | dist.py | DONE |
| runstats (Welford) | runstats.py | DONE |
| leaf, scale_mixture_leaf, crps_leaf, garch_leaf | leaf.py | DONE |
| transforms (diff, frac, standardize, ema, ou, theta, drift, holt, garch, seasonal, power, yeo-johnson, ar, grouped_ar) | transform.py | DONE |
| conjugate | conjugate.py | DONE |
| ema skater | ema.py | DONE |
| precision-weighted ensemble | ensemble.py | DONE |
| bayesian ensemble | bayesian.py | DONE |
| multiscale | multiscale.py | DONE |
| sticky (lattice projection) | sticky.py | DONE |
| terminal-leaf ensemble | terminal.py | DONE |
| tails (Acklam phi_inv, censored-ML GPD, SplicedDist, gpdtails) | tails.py | DONE |
| parade (PIT/z state, finite-input gate) | parade.py | DONE |
| laplace composition, candidate population | api.py | DONE |
| adaptive search (dantzig) | search.py | open |
| spec build path | spec.py | open |
| periodicity detector | periodicity.py | DONE |
| covariance estimators | cov/ | DONE |

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

Parity vectors provenance: `parity/vectors.json` is copied from
microprediction/skaters (`parity/vectors.json` there); refresh by rerunning
`parity/gen_vectors.py` in that repository and copying the output here.
