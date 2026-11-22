//! User-facing API: the candidate population and the `laplace` composition.
//! Port of src/skaters/api.py (search/spec paths are out of scope, as in the
//! R port).

use crate::leaf::{CrpsLeaf, Leaf};
use crate::parade::{parade, Parade, ParadeBase};
use crate::skater::{
    conjugate, multiscale, sticky, terminal_leaf_ensemble, Sk,
};
use crate::tails::{gpdtails, GpdTails, PDist};
use crate::transform::{
    ar, ar_default, difference, drift, ema_transform, fractional_difference, garch_default,
    holt_linear, ou_transform, power_transform, seasonal_anchor, seasonal_difference,
    standardize, theta,
    yeo_johnson, Transform,
};
use serde::{Deserialize, Serialize};

fn leaf(k: usize) -> Sk {
    Sk::Leaf(Leaf::new(k))
}

/// The full candidate population (leaf_fn = plain Gaussian leaf), with depths.
/// Order matches api.py::_build_candidates exactly.
pub fn build_candidates(k: usize) -> (Vec<Sk>, Vec<f64>) {
    let mut candidates: Vec<Sk> = Vec::new();
    let mut depths: Vec<f64> = Vec::new();
    let push = |c: &mut Vec<Sk>, d: &mut Vec<f64>, sk: Sk, depth: f64| {
        c.push(sk);
        d.push(depth);
    };

    // Depth 0: just noise (baseline)
    push(&mut candidates, &mut depths, leaf(k), 0.0);

    // Depth 1: single EMA at various speeds
    for alpha in [0.01, 0.05, 0.1, 0.3] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(leaf(k), ema_transform(alpha), k),
            1.0,
        );
    }

    // Depth 1: differencing + leaf
    push(
        &mut candidates,
        &mut depths,
        conjugate(leaf(k), difference(), k),
        1.0,
    );

    // Depth 1: drift + leaf
    for (a, s) in [(0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002)] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(leaf(k), drift(a, s), k),
            1.0,
        );
    }

    // Depth 1: theta
    for a in [0.05, 0.1, 0.3] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(leaf(k), theta(a), k),
            1.0,
        );
    }

    // Depth 1: AR
    push(
        &mut candidates,
        &mut depths,
        conjugate(leaf(k), ar_default(1), k),
        1.0,
    );
    push(
        &mut candidates,
        &mut depths,
        conjugate(leaf(k), ar(2, 0.99, 1.0, 1.0), k),
        1.0,
    );

    // Depth 1: Holt linear
    for (a, b) in [(0.1, 0.02), (0.1, 0.05), (0.3, 0.1)] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(leaf(k), holt_linear(a, b), k),
            1.0,
        );
    }

    // Depth 1: seasonal differencing
    for period in [7, 12, 24] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(leaf(k), seasonal_difference(period), k),
            1.0,
        );
    }

    // Depth 1: hedged seasonal anchor (phase-EMA blended 50/50 with the
    // seasonal-naive; mirrors api.py)
    for period in [7, 12, 24] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(leaf(k), seasonal_anchor(period, 0.2, 0.5), k),
            1.0,
        );
    }

    // Depth 2: seasonal + EMA
    for period in [7, 12, 24] {
        for alpha in [0.05, 0.1] {
            push(
                &mut candidates,
                &mut depths,
                conjugate(
                    conjugate(leaf(k), ema_transform(alpha), k),
                    seasonal_difference(period),
                    k,
                ),
                2.0,
            );
        }
    }

    // Depth 2: differencing + EMA
    for alpha in [0.05, 0.1, 0.3] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(conjugate(leaf(k), ema_transform(alpha), k), difference(), k),
            2.0,
        );
    }

    // Depth 2: standardize + EMA
    for alpha in [0.05, 0.1] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(
                conjugate(leaf(k), ema_transform(alpha), k),
                standardize(0.05, 1e-8),
                k,
            ),
            2.0,
        );
    }

    // Depth 2: fractional diff + EMA
    for d in [0.2, 0.4] {
        push(
            &mut candidates,
            &mut depths,
            conjugate(
                conjugate(leaf(k), ema_transform(0.1), k),
                fractional_difference(d, 30),
                k,
            ),
            2.0,
        );
    }

    // Depth 2: drift + EMA
    for (a_drift, s_drift) in [(0.002, 0.001), (0.0005, 0.0002)] {
        for a_ema in [0.05, 0.1] {
            push(
                &mut candidates,
                &mut depths,
                conjugate(
                    conjugate(leaf(k), ema_transform(a_ema), k),
                    drift(a_drift, s_drift),
                    k,
                ),
                2.0,
            );
        }
    }

    // Depth 2: drift + Holt linear
    push(
        &mut candidates,
        &mut depths,
        conjugate(
            conjugate(leaf(k), holt_linear(0.1, 0.05), k),
            drift(0.001, 0.0005),
            k,
        ),
        2.0,
    );

    // Depth 2: GARCH + EMA
    push(
        &mut candidates,
        &mut depths,
        conjugate(conjugate(leaf(k), ema_transform(0.1), k), garch_default(), k),
        2.0,
    );

    // Depth 2: power transform + EMA
    push(
        &mut candidates,
        &mut depths,
        conjugate(
            conjugate(leaf(k), ema_transform(0.1), k),
            power_transform(0.5),
            k,
        ),
        2.0,
    );

    // Depth 2: "thinking fast and slow" — fast tracker outside, slow scale inside
    fn fast_trackers() -> Vec<Transform> {
        vec![
            ema_transform(0.3),
            ema_transform(0.5),
            holt_linear(0.4, 0.2),
            ar_default(1),
            drift(0.05, 0.01),
            difference(),
        ]
    }
    for scale_alpha in [0.02, 0.05] {
        for tracker in fast_trackers() {
            push(
                &mut candidates,
                &mut depths,
                conjugate(
                    conjugate(leaf(k), standardize(scale_alpha, 1e-8), k),
                    tracker,
                    k,
                ),
                2.0,
            );
        }
    }

    // Coordinate prior (Yeo-Johnson)
    for l in [0.0, 0.5] {
        for inner_tx in [difference(), ema_transform(0.1)] {
            push(
                &mut candidates,
                &mut depths,
                conjugate(conjugate(leaf(k), inner_tx, k), yeo_johnson(l), k),
                2.0,
            );
        }
    }

    // Mean-reversion prior (Ornstein-Uhlenbeck), multi-step only
    if k > 1 {
        for l in [0.0, 0.5] {
            for kappa in [0.03, 0.1, 0.3] {
                push(
                    &mut candidates,
                    &mut depths,
                    conjugate(
                        conjugate(leaf(k), ou_transform(kappa, 0.02), k),
                        yeo_johnson(l),
                        k,
                    ),
                    2.0,
                );
            }
        }
    }

    (candidates, depths)
}

/// One laplace instance on one clock: likelihood-weighted trunk with a CRPS
/// terminal leaf, plus the lattice projection.
fn laplace_single_scale(k: usize, scale_alpha: f64) -> Sk {
    laplace_single_scale_leaf(k, &|| Sk::Crps(CrpsLeaf::new(1, 1.0, scale_alpha)))
}

fn laplace_single_scale_leaf(k: usize, leaf_fn: &dyn Fn() -> Sk) -> Sk {
    let (candidates, depths) = build_candidates(k);
    let tleafs: Vec<Sk> = (0..k).map(|_| leaf_fn()).collect();
    let f = terminal_leaf_ensemble(candidates, tleafs, k, 0.8, 0.005, depths, 20, 0.99);
    sticky(f, k)
}

/// A top-level forecaster: emits `PDist` (possibly tail-spliced) per horizon.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum Forecaster {
    Sk(Sk),
    Gpd(Box<GpdTails>),
    Parade(Box<Parade>),
    Conj(Box<FConj>),
    /// homogenize around any forecaster
    Homog(Box<crate::homogenize::Homogenize>),
    /// residual_transform around any forecaster
    Residual(Box<crate::residual::ResidualTransform>),
}

/// conjugate around any forecaster: the transform's inverse sees the full
/// predictive (mixture, tail-spliced or pushforward), as Python's duck-typed
/// conjugate does. `Sk`'s conjugate keeps mixtures throughout.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FConj {
    pub k: usize,
    pub transform: Transform,
    pub inner: Forecaster,
    /// true for flesaker, whose Python state is the inner laplace's state
    /// itself (its log map is stateless and applied outside the state).
    #[serde(default)]
    pub bare: bool,
}

pub fn conjugate_f(inner: Forecaster, transform: Transform, k: usize) -> Forecaster {
    Forecaster::Conj(Box::new(FConj {
        k,
        transform,
        inner,
        bare: false,
    }))
}

impl Forecaster {
    pub fn step(&mut self, y: f64) -> Vec<PDist> {
        match self {
            Forecaster::Sk(s) => s.step(y).into_iter().map(PDist::Mix).collect(),
            Forecaster::Gpd(g) => g.step(y),
            Forecaster::Parade(p) => p.step(y),
            Forecaster::Conj(c) => {
                let y_prime = c.transform.forward(y);
                let dists_prime = c.inner.step(y_prime);
                assert_eq!(dists_prime.len(), c.k, "conjugate k must match the wrapped forecaster");
                c.transform.inverse_k_p(&dists_prime)
            }
            Forecaster::Homog(h) => h.step(y),
            Forecaster::Residual(r) => r.step(y),
        }
    }
}

/// The general forecaster (defaults: objective="crps", sticky=True,
/// scale_alpha=0.03, tails="gpd", multiscale at k > 1).
pub fn laplace(k: usize) -> Forecaster {
    let f = multiscale(|kk| laplace_single_scale(kk, 0.03), k, None);
    let g = gpdtails(f, k, 0.98, 500, 500);
    Forecaster::Parade(Box::new(parade(ParadeBase::Gpd(g), k)))
}

/// `laplace(k, leaf=...)`: laplace with a custom terminal leaf, given as a
/// factory of a k = 1 leaf, e.g. `|| Sk::GarchLeaf(GarchLeaf::new(1))` for
/// Python's `laplace(leaf=garch_leaf)`.
pub fn laplace_with_leaf<F: Fn() -> Sk>(k: usize, leaf_fn: F) -> Forecaster {
    let f = multiscale(|kk| laplace_single_scale_leaf(kk, &leaf_fn), k, None);
    let g = gpdtails(f, k, 0.98, 500, 500);
    Forecaster::Parade(Box::new(parade(ParadeBase::Gpd(g), k)))
}

/// `dantzig(k)`: the adaptive-search policy (Python's `dantzig`, which is
/// `search` under its roster name). Adjust the returned search's public knobs
/// (e.g. `expand_interval`) before the first step, as Python's keyword
/// arguments do.
pub fn dantzig(k: usize) -> crate::search::Search {
    crate::search::search(k)
}

/// `dantzig(k, expand_interval=...)` as a forecaster.
pub fn dantzig_f(k: usize, expand_interval: u64) -> Forecaster {
    let mut s = dantzig(k);
    s.expand_interval = expand_interval;
    Forecaster::Sk(Sk::Search(Box::new(s)))
}

/// `laplace` for a series that never crosses a known bound. Experimental, as
/// in Python: laplace on log(y - lower) (or -log(upper - y)), mapped back by
/// the exact change of variables. Give one bound; neither means lower = 0.
pub fn flesaker(k: usize, lower: Option<f64>, upper: Option<f64>) -> Forecaster {
    let mut f = conjugate_f(laplace(k), crate::transform::log_transform(lower, upper), k);
    if let Forecaster::Conj(c) = &mut f {
        c.bare = true;
    }
    f
}
