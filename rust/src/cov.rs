//! Online covariance estimation: running (Welford), EMA, and Ledoit-Wolf
//! shrinkage toward identity. Port of src/skaters/cov/.
//!
//! API pattern (mirrors the Python tuple): each estimator is a struct whose
//! `update(y)` returns `(mean, cov)` where `cov` is a flat row-major n*n
//! matrix. State is created lazily on the first call, as in Python.

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// running_cov: extended Welford
// ---------------------------------------------------------------------------

/// Online covariance via extended Welford's algorithm. Port of cov/running.py.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct RunningCov {
    pub n: u64,
    pub mean: Vec<f64>,
    /// Sum of (y - mean)(y - mean)^T, flat row-major.
    pub c: Vec<f64>,
}

impl RunningCov {
    pub fn new() -> RunningCov {
        RunningCov::default()
    }

    /// Update with a new observation vector; returns (mean, cov) where cov is
    /// the sample covariance (flat, n*n, row-major; zeros until two obs).
    pub fn update(&mut self, y: &[f64]) -> (Vec<f64>, Vec<f64>) {
        let n = y.len();
        if self.n == 0 {
            self.mean = vec![0.0; n];
            self.c = vec![0.0; n * n];
        }
        self.n += 1;
        let k = self.n as f64;

        // Welford update
        let delta: Vec<f64> = (0..n).map(|i| y[i] - self.mean[i]).collect();
        for i in 0..n {
            self.mean[i] += delta[i] / k;
        }
        let delta2: Vec<f64> = (0..n).map(|i| y[i] - self.mean[i]).collect();
        for i in 0..n {
            for j in 0..n {
                self.c[i * n + j] += delta[i] * delta2[j];
            }
        }

        let cov = if self.n < 2 {
            vec![0.0; n * n]
        } else {
            self.c.iter().map(|&v| v / (k - 1.0)).collect()
        };
        (self.mean.clone(), cov)
    }
}

// ---------------------------------------------------------------------------
// ema_cov: exponentially weighted
// ---------------------------------------------------------------------------

/// Exponentially weighted online covariance. Port of cov/ema_cov.py.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EmaCov {
    pub alpha: f64,
    pub n: u64,
    pub mean: Vec<f64>,
    pub cov: Vec<f64>,
}

impl EmaCov {
    /// Python default alpha = 0.05.
    pub fn new() -> EmaCov {
        EmaCov::with_alpha(0.05)
    }

    pub fn with_alpha(alpha: f64) -> EmaCov {
        EmaCov {
            alpha,
            n: 0,
            mean: Vec::new(),
            cov: Vec::new(),
        }
    }

    pub fn update(&mut self, y: &[f64]) -> (Vec<f64>, Vec<f64>) {
        let n = y.len();
        if self.n == 0 {
            self.mean = y.to_vec();
            self.cov = vec![0.0; n * n];
            self.n = 1;
            return (y.to_vec(), vec![0.0; n * n]);
        }
        self.n += 1;
        let alpha = self.alpha;

        let delta: Vec<f64> = (0..n).map(|i| y[i] - self.mean[i]).collect();
        for i in 0..n {
            self.mean[i] += alpha * delta[i];
        }
        for i in 0..n {
            for j in 0..n {
                self.cov[i * n + j] =
                    (1.0 - alpha) * (self.cov[i * n + j] + alpha * delta[i] * delta[j]);
            }
        }
        (self.mean.clone(), self.cov.clone())
    }
}

impl Default for EmaCov {
    fn default() -> EmaCov {
        EmaCov::new()
    }
}

// ---------------------------------------------------------------------------
// ledoit_wolf_cov: shrink the correlation toward identity
// ---------------------------------------------------------------------------

/// Online Ledoit-Wolf shrinkage estimator (skaters#224). Delegates the
/// mean/covariance update to `EmaCov` -- a genuine rank-one EMA update,
/// PSD by construction -- and shrinks THAT coherent covariance toward its
/// diagonal: (1-rho)*C + rho*diag(C) stays PSD because C and diag(C) are
/// both PSD and PSD matrices are convex. The prior version updated each
/// pairwise correlation independently and clamped it to [-1, 1] on its
/// own; pairwise-valid correlations do not imply the resulting MATRIX is
/// PSD. Port of cov/shrinkage.py.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LedoitWolfCov {
    pub shrinkage: f64,
    pub inner: EmaCov,
}

impl LedoitWolfCov {
    /// Python defaults: alpha = 0.05, shrinkage = 0.5.
    pub fn new() -> LedoitWolfCov {
        LedoitWolfCov::with_params(0.05, 0.5)
    }

    pub fn with_params(alpha: f64, shrinkage: f64) -> LedoitWolfCov {
        LedoitWolfCov {
            shrinkage,
            inner: EmaCov::with_alpha(alpha),
        }
    }

    pub fn update(&mut self, y: &[f64]) -> (Vec<f64>, Vec<f64>) {
        let n = y.len();
        let (mean, cov) = self.inner.update(y);

        let mut shrunk = vec![0.0; n * n];
        for i in 0..n {
            for j in 0..n {
                shrunk[i * n + j] = if i == j {
                    cov[i * n + j]
                } else {
                    (1.0 - self.shrinkage) * cov[i * n + j]
                };
            }
        }
        (mean, shrunk)
    }
}

impl Default for LedoitWolfCov {
    fn default() -> LedoitWolfCov {
        LedoitWolfCov::new()
    }
}
