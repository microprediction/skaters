//! Online periodicity detection via running autocorrelation. Port of
//! src/skaters/periodicity.py.
//!
//! Maintains exponentially weighted estimates of autocorrelation at a set of
//! candidate lags; the top-scoring lags are the detected periods. O(n_lags)
//! per observation.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

/// Common periods to scan.
pub const DEFAULT_LAGS: [usize; 16] = [
    2, 3, 4, 5, 6, 7, 12, 14, 24, 28, 30, 52, 60, 90, 168, 365,
];

/// Online period detector: `step(y)` returns (lag, acf) pairs sorted by
/// |acf| descending (stable sort, so ties keep candidate-lag order, exactly
/// as Python's `list.sort`).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PeriodDetector {
    pub lags: Vec<usize>,
    pub alpha: f64,
    pub min_observations: u64,
    pub max_lag: usize,
    pub buffer: VecDeque<f64>,
    pub n: u64,
    pub mean: f64,
    pub var: f64,
    /// Per-lag running EMA of (y_t - mu) * (y_{t-L} - mu), parallel to `lags`.
    pub cross: Vec<f64>,
}

impl PeriodDetector {
    /// Python defaults: DEFAULT_LAGS, alpha = 0.01, min_observations = 50.
    pub fn new() -> PeriodDetector {
        PeriodDetector::with_params(None, 0.01, 50)
    }

    pub fn with_params(
        lags: Option<Vec<usize>>,
        alpha: f64,
        min_observations: u64,
    ) -> PeriodDetector {
        let lags = lags.unwrap_or_else(|| DEFAULT_LAGS.to_vec());
        let max_lag = *lags.iter().max().expect("lags must be non-empty");
        let n_lags = lags.len();
        PeriodDetector {
            lags,
            alpha,
            min_observations,
            max_lag,
            buffer: VecDeque::new(),
            n: 0,
            mean: 0.0,
            var: 0.0,
            cross: vec![0.0; n_lags],
        }
    }

    pub fn step(&mut self, y: f64) -> Vec<(usize, f64)> {
        self.buffer.push_back(y);
        self.n += 1;

        // Update running mean and variance
        let diff = y - self.mean;
        self.mean += self.alpha * diff;
        self.var = (1.0 - self.alpha) * (self.var + self.alpha * diff * diff);

        let mu = self.mean;
        let var = self.var;

        // Update cross-correlation for each lag
        let nb = self.buffer.len();
        for (li, &lag) in self.lags.iter().enumerate() {
            if nb > lag {
                let y_lagged = self.buffer[nb - (lag + 1)];
                let cross = (y - mu) * (y_lagged - mu);
                self.cross[li] = (1.0 - self.alpha) * self.cross[li] + self.alpha * cross;
            }
        }

        // Trim buffer
        if self.buffer.len() > self.max_lag + 1 {
            self.buffer.pop_front();
        }

        // Compute ACF scores
        if self.n < self.min_observations || var < 1e-12 {
            return Vec::new();
        }

        let mut scores: Vec<(usize, f64)> = Vec::new();
        for (li, &lag) in self.lags.iter().enumerate() {
            if self.n > lag as u64 {
                let acf = if var > 0.0 { self.cross[li] / var } else { 0.0 };
                scores.push((lag, acf));
            }
        }

        // Sort by |acf| descending (stable; Equal on NaN so a poisoned
        // score cannot panic, matching Python's non-raising sort)
        scores.sort_by(|a, b| {
            b.1.abs()
                .partial_cmp(&a.1.abs())
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        scores
    }
}

impl Default for PeriodDetector {
    fn default() -> PeriodDetector {
        PeriodDetector::new()
    }
}

/// Extract the best periods from detector scores: the first `max_periods`
/// entries with |acf| at or above `threshold`, in strength order.
pub fn top_periods(scores: &[(usize, f64)], threshold: f64, max_periods: usize) -> Vec<usize> {
    scores
        .iter()
        .take(max_periods)
        .filter(|(_, acf)| acf.abs() >= threshold)
        .map(|&(lag, _)| lag)
        .collect()
}
