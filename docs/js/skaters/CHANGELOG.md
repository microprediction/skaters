# Changelog

All notable changes to the `skaters` npm package (the JavaScript port). The port
tracks the Python [`skaters`](https://pypi.org/project/skaters/) package and is
kept numerically identical to it within `1e-6`, enforced by the parity checker on
every release.

## 0.11.2

Fix: RLS covariance windup in the `ar` and `grouped_ar` transforms. Under
low-excitation input the RLS `P` matrix inflated by `1/lam` each step and
eventually overflowed to `Inf` (~74k steps), giving `NaN` coefficients and a
non-finite forecast. `P` is now reset if it grows implausibly large or turns
non-finite (keeping the coefficients); it never triggers on well-excited data, so
results and Python↔JS parity are unchanged.

## 0.11.1

Fix: the CRPS leaf's exponentiated-gradient weight update could overflow `exp()`
to `Inf` on some streams, normalizing to `NaN` weights and throwing in the `Dist`
constructor. The step is now stabilized by subtracting the max exponent
(mathematically invariant, so results and Python↔JS parity are unchanged), with a
guard that keeps the current weights on any degenerate update.

## 0.11.0

Initial npm release of the JavaScript port. Zero-dependency ES modules for Node
and the browser. Exports `laplace` and `buildCandidates`, the `Dist` object,
transforms (`difference`, `standardize`, `garch`, `ar`, `holtLinear`,
`powerTransform`, …), ensembles, leaves (`scaleMixtureLeaf`, `crpsLeaf`,
`garchLeaf`), `multiscale`, `sticky`, periodicity and covariance helpers, and the
spec (de)serialisers. Version chosen to align with the Python package.
