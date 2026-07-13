//! Online covariance estimation: running (Welford), EMA, and Ledoit-Wolf
//! shrinkage toward identity. Port of src/skaters/cov/.
//!
//! API pattern (mirrors the Python tuple): each estimator is a struct whose
//! `update(y)` returns `(mean, cov)` where `cov` is a flat row-major n*n
//! matrix. State is created lazily on the first call, as in Python.

use serde::{Deserialize, Serialize};

/// Python's `min(a, b)` / `max(a, b)` argument-order semantics (relevant only
/// for NaN, but mirrored literally so the clamp below is branch-for-branch).
fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}

fn py_max(a: f64, b: f64) -> f64 {
    if b > a {
        b
    } else {
        a
    }
}

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

/// Online Ledoit-Wolf shrinkage estimator: EMA covariance, correlations
/// shrunk toward the identity, covariance reconstituted. Port of
/// cov/shrinkage.py.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LedoitWolfCov {
    pub alpha: f64,
    pub shrinkage: f64,
    pub n: u64,
    pub mean: Vec<f64>,
    pub var: Vec<f64>,
    pub corr: Vec<f64>,
}

impl LedoitWolfCov {
    /// Python defaults: alpha = 0.05, shrinkage = 0.5.
    pub fn new() -> LedoitWolfCov {
        LedoitWolfCov::with_params(0.05, 0.5)
    }

    pub fn with_params(alpha: f64, shrinkage: f64) -> LedoitWolfCov {
        LedoitWolfCov {
            alpha,
            shrinkage,
            n: 0,
            mean: Vec::new(),
            var: Vec::new(),
            corr: Vec::new(),
        }
    }

    pub fn update(&mut self, y: &[f64]) -> (Vec<f64>, Vec<f64>) {
        let n = y.len();
        if self.n == 0 {
            self.mean = y.to_vec();
            self.var = vec![0.0; n];
            self.corr = (0..n * n)
                .map(|idx| if idx / n == idx % n { 1.0 } else { 0.0 })
                .collect();
            self.n = 1;
            return (y.to_vec(), vec![0.0; n * n]);
        }
        self.n += 1;
        let alpha = self.alpha;

        // Update mean
        let delta: Vec<f64> = (0..n).map(|i| y[i] - self.mean[i]).collect();
        for i in 0..n {
            self.mean[i] += alpha * delta[i];
        }

        // Update variances
        let delta2: Vec<f64> = (0..n).map(|i| y[i] - self.mean[i]).collect();
        for i in 0..n {
            self.var[i] = (1.0 - alpha) * self.var[i] + alpha * delta[i] * delta2[i];
        }

        // Update correlations (work in standardized space for stability)
        for i in 0..n {
            let si = if self.var[i] > 1e-16 {
                self.var[i].sqrt()
            } else {
                1e-8
            };
            for j in (i + 1)..n {
                let sj = if self.var[j] > 1e-16 {
                    self.var[j].sqrt()
                } else {
                    1e-8
                };
                let z_cross = (delta[i] / si) * (delta[j] / sj);
                let idx = i * n + j;
                let r = (1.0 - alpha) * self.corr[idx] + alpha * z_cross;
                // Clamp to [-1, 1] for stability
                let r = py_max(-1.0, py_min(1.0, r));
                self.corr[idx] = r;
                self.corr[j * n + i] = r;
            }
        }

        // Shrink correlation toward identity
        let mut shrunk = vec![0.0; n * n];
        for i in 0..n {
            let si = if self.var[i] > 1e-16 {
                self.var[i].sqrt()
            } else {
                1e-8
            };
            for j in 0..n {
                let sj = if self.var[j] > 1e-16 {
                    self.var[j].sqrt()
                } else {
                    1e-8
                };
                if i == j {
                    shrunk[i * n + j] = self.var[i];
                } else {
                    let r = (1.0 - self.shrinkage) * self.corr[i * n + j];
                    shrunk[i * n + j] = r * si * sj;
                }
            }
        }
        (self.mean.clone(), shrunk)
    }
}

impl Default for LedoitWolfCov {
    fn default() -> LedoitWolfCov {
        LedoitWolfCov::new()
    }
}
