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
pub mod search;
pub mod spec;
pub mod tails;
pub mod pushforward;
pub mod parade;
pub mod api;
pub mod granger;
pub mod homogenize;
pub mod residual;
pub mod state;

pub use api::{
    build_candidates, conjugate_f, dantzig, flesaker, laplace, laplace_with_leaf, FConj, Forecaster,
};
pub use homogenize::{homogenize, make_candidates as homogenize_candidates, HomogenizedDist};
pub use residual::{residual_transform, CorrectedDist, ResidualDiagnostics};
pub use state::{state_from_json, state_to_json, State};
pub use pushforward::{CoordMap, PushforwardDist};
pub use granger::{Granger, GrangerParams, Mixture};
pub use cov::{EmaCov, LedoitWolfCov, RunningCov};
pub use dist::Dist;
pub use periodicity::{top_periods, PeriodDetector};
pub use search::{search, Search};
pub use spec::{Spec, TransformSpec};
pub use skater::{
    bayesian_ensemble, conjugate, ema, multiscale, precision_weighted_ensemble, sticky,
    terminal_leaf_ensemble, with_adaptive_temperature, with_prior_log_weights, Sk,
};
pub use tails::{gpdtails, PDist, SplicedDist};
