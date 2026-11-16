# Distribution quantile contracts

`Dist.quantile` retains the moment bracket and geometric expansion. The x
stopping tolerance is `tol * min(1, smallest positive active component std)`.
Zero-weight components do not set that scale. At a normal tolerance exit the
historical midpoint is retained, except a probability inside an atom's jump
returns that atom exactly. At floating-point resolution, midpoint rounding is
retained when `0 < tol <= 2 * gap` and moving unresolved components across
that adjacent pair leaves both accumulated endpoint CDFs unchanged. A component
is unresolved here when its std is at most the gap (including atoms). The CDF
sums use their original component order. This detects floating-point-irrelevant
residue without a weight floor; meaningful tiny-weight tails and atom jumps
still use the upper endpoint. Components are never dropped from the distribution
or its tolerance scale. This is an approximate inverse of the existing CDF;
it is not a new high-precision tail CDF.

The default iteration cap is 2100 rather than 100, allowing mixtures with very
large separation to reach a tiny component. Explicit smaller budgets still
return an approximate midpoint on exhaustion. The forwarding spliced-tail, pushforward, residual-correction and
homogenization wrappers use the same default. Quantiles require finite mixture
variance and a finite search bracket; overflow fails explicitly. The CDF's erf
rounding limits extreme-tail accuracy, so those cases use x intervals rather
than cross-port bit equality. This change does not modify the CDF.

`quantile_contract.json` supplies the same geometry and x assertions to Python,
JavaScript and Rust. The `unit_*` and `subunit_mixture` expected values were
recorded from upstream main `8baee06362f82504fe47e25f7b91fe6d8b55eb84` in Python
3.14.6. Unit-scale goldens check the historical path, with cross-port numerical
tolerance where the existing erf implementations differ; subunit goldens allow
half the historical default x tolerance for those specified fixtures. This is
not a universal shift bound: rounded historical midpoints can add half a float
spacing in other geometries. The far-component assertion
rejects 1008 when the expected answer is about 1002.32635. Main already expands
the bracket to reach this component; this is a retained accuracy guard. Both reviewed #176
regressions and astronomical separation remain explicit cases. Spread tests
check that tiny distributions retain their width.

Run `PYTHONPATH=src python -m pytest -q tests/test_quantile_inverse_contract.py`,
`node parity/quantile_contract.mjs`, and
`cargo test --release --manifest-path rust/Cargo.toml --test quantile_contract`.
The Rust workflow selects this contract on native and wasm runners; the JS
contract is also selected by pytest. Full parity and robustness gates remain
required. Frozen output-signature and real-corpus acceptance measurements are
separate evidence, not implied by these tests.

The large-scale midpoint discriminator uses a single Gaussian at
`1e12 + 2**-13` with std `1e10`, at probability 0.5, avoiding a platform-sensitive
multi-component erf golden. The JavaScript erf helper has a pre-existing limit:
its internal square can overflow at extreme standardized distances, producing
NaN where Python/Rust may still compute. This change does not repair that helper.
The Rust overflow-panic test is native-only; no wasm execution is implied by it.

The large-level unit-noise, translated sub-unit and tiny-weight-residue goldens
were recorded from the same pinned main/Python 3.14.6 baseline cited above.
The low-weight collapsed and 1e-301 tail cases guard against ignoring meaningful
small components while preserving historical rounding for irrelevant residue.

`visible_narrow_mass_at_crossing` and the two `meaningful_*` cases assert the
intentional upper-endpoint policy for visible unresolved mass; they are accuracy
expectations, not historical-main provenance goldens.
