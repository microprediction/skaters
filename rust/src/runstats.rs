//! Welford online mean/variance. Port of src/skaters/runstats.py.

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct RunningVar {
    pub n: u64,
    pub mean: f64,
    pub m2: f64,
}

impl RunningVar {
    pub fn new() -> RunningVar {
        RunningVar {
            n: 0,
            mean: 0.0,
            m2: 0.0,
        }
    }

    pub fn update(&mut self, x: f64) {
        let n = self.n + 1;
        let delta = x - self.mean;
        let mean = self.mean + delta / n as f64;
        let delta2 = x - mean;
        self.m2 += delta * delta2;
        self.n = n;
        self.mean = mean;
    }

    /// (mean, variance); variance is +inf until two observations.
    pub fn get(&self) -> (f64, f64) {
        if self.n < 2 {
            return (self.mean, f64::INFINITY);
        }
        (self.mean, self.m2 / (self.n - 1) as f64)
    }

    /// Mean squared error (bias^2 + variance) of tracked errors.
    pub fn mse(&self) -> f64 {
        if self.n < 1 {
            return f64::INFINITY;
        }
        let (mean, var) = self.get();
        if !var.is_finite() {
            return f64::INFINITY;
        }
        mean * mean + var
    }
}
