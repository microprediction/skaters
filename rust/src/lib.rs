//! skaters-core: Rust port of the skaters online distributional forecasting
//! library. Parity-gated against the Python reference via parity/vectors.json
//! (seven probes per step and horizon, atol = rtol = 1e-6).
//!
//! All transcendental math routes through the pure-Rust `libm` crate, so the
//! core is bit-deterministic across platforms (x86 / ARM / wasm32).

pub mod mathx;
pub mod dist;
pub mod runstats;
pub mod cov;
pub mod periodicity;
pub mod leaf;
pub mod transform;
pub mod skater;
pub mod spec;
pub mod tails;
pub mod parade;
pub mod api;

pub use api::{build_candidates, laplace, Forecaster};
pub use cov::{EmaCov, LedoitWolfCov, RunningCov};
pub use dist::Dist;
pub use periodicity::{top_periods, PeriodDetector};
pub use spec::{Spec, TransformSpec};
pub use skater::{
    bayesian_ensemble, conjugate, ema, multiscale, precision_weighted_ensemble, sticky,
    terminal_leaf_ensemble, Sk,
};
pub use tails::{gpdtails, PDist, SplicedDist};
