# Changelog

## Note for anyone upgrading from 0.14.0

0.16.0 is the first release since **0.14.0** (2026-07-24). The `v0.15.0` tag
exists in git but was never turned into a GitHub Release, so the publish
workflows never fired and neither PyPI nor npm ever served 0.15.0. Installing
0.16.0 therefore brings two releases of change: everything listed below, plus
0.15.0's additions.

### 0.15.0 (tagged 2026-08-02, never published)

- `gaussianize`: empirical Gaussianization, `z = Phi^-1(F_hat(y))`, from a
  running quantile sketch with fence-post weights
- Empirical distributional leaves
- Benchmark suite for the conformal information gap paper

Also landed after that tag and included here: `homogenize` and
`residual_transform` (#182), the online scale-mixture correction on a skater's
own residual stream, applied explicitly as `homogenize(laplace(k=1))` rather
than being part of `laplace`'s default output; and the `gaussianize`
knot-deletion and smallest-rank-displacement guards (#169).

## 0.16.0

Two user-visible behavior changes, and the first release in which the Python,
JavaScript, Rust, R and Julia ports actually agree.

### The residual cap (all five ports)

`standardize` divided the residual by the **post-update** EWMA variance, which
made the emission self-normalized:

    z = d / sqrt((1-a) v + a d^2)   =>   |z| < 1/sqrt(alpha) = 4.4721

No input could produce a residual past 4.4721. Measured on the old code, `y=100`,
`y=1000` and `y=1e6` all emitted exactly 4.4721, so a million-sigma move was
indistinguishable from a hundred-sigma one. The affine inverse was also not the
forward map's inverse, because the forward scale depended on the value being
predicted: round-tripping `y=7.5` recovered `5.996`.

It now emits against the prior variance, and the cold start scales by the first
nonzero residual so the first informative emission is ±1.

This changes every predictive. Expect small movements in both directions on
aggregate point metrics (on the GIFT-Eval leaderboard protocol at k=13,
`m4_monthly` MASE improved 1.0716 → 1.0619 while `m4_weekly` worsened
3.2377 → 3.3229). Tail and coverage results are the ones most affected, since
the cap is precisely what distorted them.

The Python fix landed on main in #169 but **after** the v0.15.0 tag, so this is
the first release to carry it in any language.

### Missing observations are now a skipped tick

A non-finite `y` (NaN or infinity) means "no observation", not a value and not an
error. Previously the outcome depended on the horizon: at `k=1` laplace returned
`mean=nan, std=0.0` and never recovered, because an EWMA fed NaN is poisoned
permanently (`mu + alpha*(nan - mu) = nan`); at `k>1` it tripped a bare
`assert w_total > 0` inside `Dist`.

Now the value never reaches the tree, the fitted state is not advanced, and the
fan is shifted so the previous tick's horizon `h+1` is returned as this tick's
`h` — the forecast ages by one step rather than relabelling a stale predictive.
After `k` consecutive gaps the longest horizon is held. `state["pit"]` and
`state["z"]` are all `None` for the tick, so a gap cannot look like a zero
residual to the anomaly layer, and `state["skipped"]` counts them.

Callers wanting loud failure should check finiteness before calling. The reverse
is not available: nothing can recover a silently corrupted state.

See the "Missing observations" section of `skaters.conventions`.

### Port parity restored

CI was red from #169 (2026-08-04) to this release: the `standardize` repair
reached Python only. The JS twin, the Rust port, the R package (published on
r-universe) and the Julia package all kept the capped version. R and Julia were
further behind still, each missing four things:

- `garch` had no mean tracking, modelling the variance of the raw value rather
  than of the deviation from a running mean, with a pure-scale inverse instead of
  an affine one
- `_ar_spectral_radius` / `_ar_stationary` were absent entirely, so an explosive
  online fit had no damping and its multi-step forecast could diverge
- `ar` and `grouped_ar` accumulated multi-step variance as `sum phi_j^2 var_{h-j}`
  instead of `sigma^2 sum psi_i^2`; successive horizons share one innovation, so
  the old form both mis-weighted and double counted it
- `seasonal_anchor` was absent entirely, leaving the candidate pool at 57 against
  Python's 60

All five ports now pass at 1e-6.

### Parity gate: two instrument fixes

The drift was invisible because the gates were lying, and both faults are fixed.

**The gates reported `ok` for failing scenarios.** The R and Julia parity scripts
printed `ok <name>` per scenario unconditionally, with the failure detail capped
at 7 lines *globally*, so a port four features behind displayed 59 `ok` lines and
one failure. The budget is now per scenario and the summary reflects the tally.

**Nothing checked the component inventory.** 105,798 numeric probes could not see
three missing candidates, because every individual transform matched to 1e-6 and
only the composed `laplace` drifted. `parity/vectors.json` now carries a
`structure` block (candidate count and full depth vector per k), asserted in all
four ports. The depth vector also pins ordering, since the ensemble aligns weights
by candidate index.

Note that `parity/vectors.json` is generated and untracked: a stale local copy
will report `PARITY OK` against a reference that no longer exists. Regenerate with
`PYTHONPATH=src python parity/gen_vectors.py` before trusting the gate. The
pytest wrapper does this for you.

### Added

- `tests/test_standardize_no_cap.py` — pins the emission contract, the
  forward/inverse pairing, and the cold-start unit emission
- `tests/test_missing_observations.py` — 11 tests covering state preservation,
  fan ageing, the leading-gap case, PIT/z reporting and an all-missing stream
- Gap scenarios in the parity vectors, so the missing-observation rule is held
  identically across ports (gaps travel as the `"nan"` sentinel, since JSON has
  no NaN literal)
