//! The prediction parade: online PIT/z calibration diagnostics in the state,
//! plus the finite-input gate. Port of src/skaters/parade.py.

use crate::dist::Dist;
use crate::skater::Sk;
use crate::tails::{GpdTails, PDist};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

const EPS: f64 = 1e-12;
/// A leading missing tick has no prior forecast to age and no observation has
/// fixed the series' scale yet, so emit a deliberately wide zero-centred
/// Gaussian rather than a confident guess. The tree is left untouched, so the
/// first finite value initializes it exactly as a true first observation would.
const NO_INFO_STD: f64 = 1e6;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum ParadeBase {
    Sk(Sk),
    Gpd(GpdTails),
}

impl ParadeBase {
    fn step(&mut self, y: f64) -> Vec<PDist> {
        match self {
            ParadeBase::Sk(s) => s.step(y).into_iter().map(PDist::Mix).collect(),
            ParadeBase::Gpd(g) => g.step(y),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Parade {
    pub k: usize,
    pub base: ParadeBase,
    pub pending: VecDeque<Vec<PDist>>,
    pub pit: Vec<Option<f64>>,
    pub z: Vec<Option<f64>>,
    /// Count of missing (non-finite) ticks skipped. `serde(default)` so state
    /// checkpointed before this field existed still deserializes.
    #[serde(default)]
    pub skipped: u64,
}

pub fn parade(base: ParadeBase, k: usize) -> Parade {
    Parade {
        k,
        base,
        pending: VecDeque::new(),
        pit: vec![None; k],
        z: vec![None; k],
        skipped: 0,
    }
}

impl Parade {
    pub fn step(&mut self, y: f64) -> Vec<PDist> {
        let k = self.k;
        let n = self.pending.len();
        // Missing observation — port of the Python parade's missing-tick rule.
        // A non-finite y must never reach the tree: an EWMA fed NaN is poisoned
        // permanently and no later clean data recovers it. Treat the tick as
        // "no observation": time advanced, information did not. Leave the base
        // state untouched and SHIFT the fan, so the previous tick's horizon
        // h+1 becomes this tick's horizon h and the forecast ages by one step.
        // After k consecutive gaps h=k is held.
        if !y.is_finite() {
            self.skipped += 1;
            self.pit = vec![None; k];
            self.z = vec![None; k];
            if n == 0 {
                return vec![PDist::Mix(Dist::gaussian(0.0, NO_INFO_STD)); k];
            }
            let prev = &self.pending[n - 1];
            let shifted: Vec<PDist> = (1..=k)
                .map(|h| prev[h.min(prev.len() - 1)].clone())
                .collect();
            self.pending.push_back(shifted.clone());
            while self.pending.len() > k {
                self.pending.pop_front();
            }
            return shifted;
        }
        let std_normal = Dist::gaussian(0.0, 1.0);
        let mut pit: Vec<Option<f64>> = vec![None; k];
        let mut z: Vec<Option<f64>> = vec![None; k];
        for m in 1..=k {
            if m <= n {
                let d = &self.pending[n - m][m - 1];
                let u = d.cdf(y);
                if !u.is_finite() {
                    continue;
                }
                let u = u.max(EPS).min(1.0 - EPS);
                pit[m - 1] = Some(u);
                z[m - 1] = Some(std_normal.quantile(u));
            }
        }
        // Finite-input gate: clamp the fed observation to a magnitude-relative
        // window around the 1-step predictive so no finite input can crash the
        // tree (exactly as in Python; identity on any comfortable stream).
        let mut y_fed = y;
        if y_fed.is_finite() {
            y_fed = y_fed.max(-1e60).min(1e60);
            if n > 0 {
                let d1 = &self.pending[n - 1][0];
                // For a spliced predictive use the body's closed-form moments.
                let (mp, sp) = match d1 {
                    PDist::Mix(d) => (d.mean(), d.std()),
                    PDist::Spliced(s) => (s.body.mean(), s.body.std()),
                };
                if mp.is_finite() && sp.is_finite() {
                    let w = 1e12 * (1.0 + mp.abs() + sp);
                    y_fed = y_fed.max(mp - w).min(mp + w);
                }
            }
        }
        let dists = self.base.step(y_fed);
        self.pending.push_back(dists.clone());
        if self.pending.len() > k {
            self.pending.pop_front();
        }
        self.pit = pit;
        self.z = z;
        dists
    }
}
