//! skaters-fast: an opt-in accelerated backend for skaters.
//!
//! This is a thin PyO3 skin over the `skaters-core` Rust crate. The pure
//! Python package remains the reference implementation; this backend exists
//! only to run the identical model faster.
//!
//! Guarantees:
//!   - Cross-backend agreement is 1e-6. The same series through pure Python
//!     and through skaters-fast yields distributional probes that agree to
//!     that tolerance (the same contract the Rust core is parity-gated on).
//!   - Within-backend resume is bit-exact. `state_json()` round-trips through
//!     `from_state_json()` with no drift, because the core serializes floats
//!     with serde_json's `float_roundtrip`.
//!   - Do not switch backends mid-stream. Pick one backend for the life of a
//!     stream; a resumed state must go back into the same backend that wrote
//!     it.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use skaters_core::api::{laplace as core_laplace, Forecaster};
use skaters_core::tails::PDist;

/// A single-horizon distributional prediction handle.
///
/// Wraps the core predictive (a Gaussian mixture, possibly tail-spliced).
/// Methods and properties mirror the pure-Python `Dist`.
#[pyclass(module = "skaters_fast", name = "Dist", skip_from_py_object)]
#[derive(Clone)]
struct Dist {
    inner: PDist,
}

#[pymethods]
impl Dist {
    /// Log density at x.
    fn logpdf(&self, x: f64) -> f64 {
        self.inner.logpdf(x)
    }

    /// Cumulative probability at x.
    fn cdf(&self, x: f64) -> f64 {
        self.inner.cdf(x)
    }

    /// Inverse CDF at probability p in (0, 1).
    fn quantile(&self, p: f64) -> f64 {
        self.inner.quantile(p)
    }

    /// Continuous ranked probability score against observation x.
    fn crps(&self, x: f64) -> f64 {
        self.inner.crps(x)
    }

    /// Predictive mean.
    #[getter]
    fn mean(&self) -> f64 {
        self.inner.mean()
    }

    /// Predictive standard deviation.
    #[getter]
    fn std(&self) -> f64 {
        self.inner.std()
    }

    fn __repr__(&self) -> String {
        format!(
            "Dist(mean={:.6}, std={:.6})",
            self.inner.mean(),
            self.inner.std()
        )
    }
}

/// The `laplace` forecaster: a likelihood-weighted trunk with a CRPS terminal
/// leaf, GPD tails, and the PIT/z calibration parade, running on the Rust core.
#[pyclass(module = "skaters_fast", name = "Laplace")]
struct Laplace {
    inner: Forecaster,
    k: usize,
}

impl Laplace {
    fn parade_state(&self) -> (Vec<Option<f64>>, Vec<Option<f64>>) {
        match &self.inner {
            Forecaster::Parade(p) => (p.pit.clone(), p.z.clone()),
            _ => (vec![None; self.k], vec![None; self.k]),
        }
    }
}

#[pymethods]
impl Laplace {
    /// Build a laplace forecaster for horizons 1..=k.
    #[new]
    fn new(k: usize) -> PyResult<Self> {
        if k == 0 {
            return Err(PyValueError::new_err("k must be >= 1"));
        }
        Ok(Laplace {
            inner: core_laplace(k),
            k,
        })
    }

    /// Feed one observation. Returns the list of predictive Dist handles for
    /// horizons 1..=k.
    fn step(&mut self, y: f64) -> Vec<Dist> {
        self.inner
            .step(y)
            .into_iter()
            .map(|d| Dist { inner: d })
            .collect()
    }

    /// PIT values from the parade after the last step (list of length k;
    /// entries are None until a matching prediction has been scored).
    #[getter]
    fn pit(&self) -> Vec<Option<f64>> {
        self.parade_state().0
    }

    /// z-scores (inverse-normal of the PIT) after the last step.
    #[getter]
    fn z(&self) -> Vec<Option<f64>> {
        self.parade_state().1
    }

    /// Serialize the full forecaster state to JSON. Round-trips bit-exactly
    /// through `from_state_json` (floats use serde_json float_roundtrip).
    fn state_json(&self) -> PyResult<String> {
        serde_json::to_string(&self.inner)
            .map_err(|e| PyValueError::new_err(format!("serialize failed: {e}")))
    }

    /// Rebuild a forecaster from a `state_json` string. `k` must match the
    /// horizon the state was written with.
    #[staticmethod]
    fn from_state_json(s: &str, k: usize) -> PyResult<Self> {
        if k == 0 {
            return Err(PyValueError::new_err("k must be >= 1"));
        }
        let inner: Forecaster = serde_json::from_str(s)
            .map_err(|e| PyValueError::new_err(format!("deserialize failed: {e}")))?;
        Ok(Laplace { inner, k })
    }

    fn __repr__(&self) -> String {
        format!("Laplace(k={})", self.k)
    }
}

/// Build a laplace forecaster on the accelerated backend.
#[pyfunction]
fn laplace(k: usize) -> PyResult<Laplace> {
    Laplace::new(k)
}

#[pymodule]
fn skaters_fast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add(
        "__doc__",
        "skaters_fast: opt-in accelerated backend for skaters.\n\n\
         The pure Python package remains the reference implementation. This \
         module is a PyO3 skin over the parity-gated Rust core.\n\n\
         Cross-backend agreement is 1e-6; within-backend resume via \
         state_json/from_state_json is bit-exact. Do not switch backends \
         mid-stream: pick one backend for the life of a stream and resume a \
         saved state into the same backend that wrote it.",
    )?;
    m.add_function(wrap_pyfunction!(laplace, m)?)?;
    m.add_class::<Laplace>()?;
    m.add_class::<Dist>()?;
    Ok(())
}
