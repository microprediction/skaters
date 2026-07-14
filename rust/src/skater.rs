//! The skater type: every forecaster is a struct with `step(&mut self, y) -> Vec<Dist>`
//! whose fields are plain serde-serializable data (a product contract).
//!
//! This module holds the recursive `Sk` enum and the combinators:
//! conjugate, precision-weighted ensemble, bayesian ensemble, multiscale,
//! sticky (lattice projection), and the terminal-leaf ensemble.
//! Ports of conjugate.py, ensemble.py, bayesian.py, multiscale.py, sticky.py,
//! terminal.py.

use crate::dist::Dist;
use crate::leaf::{CrpsLeaf, GarchLeaf, Leaf, ScaleMixLeaf};
use crate::mathx::fsum;
use crate::runstats::RunningVar;
use crate::transform::{ema_transform, Transform};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum Sk {
    Leaf(Leaf),
    ScaleMix(ScaleMixLeaf),
    Crps(CrpsLeaf),
    GarchLeaf(GarchLeaf),
    Conj(Box<Conj>),
    Pw(Box<PwEnsemble>),
    Bayes(Box<BayesEnsemble>),
    Terminal(Box<TerminalEnsemble>),
    Multiscale(Box<Multiscale>),
    Sticky(Box<Sticky>),
    Search(Box<crate::search::Search>),
}

impl Sk {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        match self {
            Sk::Leaf(s) => s.step(y),
            Sk::ScaleMix(s) => s.step(y),
            Sk::Crps(s) => s.step(y),
            Sk::GarchLeaf(s) => s.step(y),
            Sk::Conj(s) => s.step(y),
            Sk::Pw(s) => s.step(y),
            Sk::Bayes(s) => s.step(y),
            Sk::Terminal(s) => s.step(y),
            Sk::Multiscale(s) => s.step(y),
            Sk::Sticky(s) => s.step(y),
            Sk::Search(s) => s.step(y),
        }
    }
}

// ---------------------------------------------------------------------------
// conjugate: change of reference frame
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Conj {
    pub k: usize,
    pub transform: Transform,
    pub inner: Sk,
}

pub fn conjugate(inner: Sk, transform: Transform, k: usize) -> Sk {
    Sk::Conj(Box::new(Conj {
        k,
        transform,
        inner,
    }))
}

impl Conj {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let y_prime = self.transform.forward(y);
        let dists_prime = self.inner.step(y_prime);
        debug_assert_eq!(dists_prime.len(), self.k);
        self.transform.inverse_k(&dists_prime)
    }
}

/// ema(alpha, k) = conjugate(leaf(k), ema_transform(alpha), k)
pub fn ema(alpha: f64, k: usize) -> Sk {
    conjugate(Sk::Leaf(Leaf::new(k)), ema_transform(alpha), k)
}

// ---------------------------------------------------------------------------
// precision-weighted ensemble
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PwEnsemble {
    pub k: usize,
    pub floor: f64,
    pub subs: Vec<Sk>,
    pub queues: Vec<Vec<VecDeque<f64>>>,
    pub stats: Vec<Vec<RunningVar>>,
}

pub fn precision_weighted_ensemble(subs: Vec<Sk>, k: usize) -> Sk {
    let n = subs.len();
    assert!(n > 0);
    Sk::Pw(Box::new(PwEnsemble {
        k,
        floor: 1e-6,
        subs,
        queues: vec![vec![VecDeque::new(); k]; n],
        stats: vec![vec![RunningVar::new(); k]; n],
    }))
}

impl PwEnsemble {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let n = self.subs.len();
        let k = self.k;
        let all_dists: Vec<Vec<Dist>> = self.subs.iter_mut().map(|f| f.step(y)).collect();

        for i in 0..n {
            for h in 0..k {
                let q = &mut self.queues[i][h];
                q.push_back(all_dists[i][h].mean());
                if q.len() > h + 1 {
                    let pred_mean = q.pop_front().unwrap();
                    let error = y - pred_mean;
                    self.stats[i][h].update(error);
                }
            }
        }

        let mut combined = Vec::with_capacity(k);
        for h in 0..k {
            let mut weights = Vec::with_capacity(n);
            for i in 0..n {
                let mse = self.stats[i][h].mse();
                let w = if mse.is_finite() && mse > 0.0 {
                    1.0 / mse
                } else {
                    self.floor
                };
                weights.push(w.max(self.floor));
            }
            let horizon: Vec<&Dist> = (0..n).map(|i| &all_dists[i][h]).collect();
            combined.push(Dist::combine_refs(&horizon, Some(&weights)));
        }
        combined
    }
}

// ---------------------------------------------------------------------------
// bayesian model-averaging ensemble
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BayesEnsemble {
    pub k: usize,
    pub learning_rate: f64,
    pub complexity_penalty: f64,
    pub depths: Vec<f64>,
    pub max_components: usize,
    pub subs: Vec<Sk>,
    pub queues: Vec<Vec<VecDeque<Dist>>>,
    pub log_w: Vec<Vec<f64>>,
    pub n_obs: u64,
}

pub fn bayesian_ensemble(
    subs: Vec<Sk>,
    k: usize,
    learning_rate: f64,
    complexity_penalty: f64,
    depths: Vec<f64>,
) -> Sk {
    let n = subs.len();
    assert!(n > 0);
    Sk::Bayes(Box::new(BayesEnsemble {
        k,
        learning_rate,
        complexity_penalty,
        depths,
        max_components: 20,
        subs,
        queues: vec![vec![VecDeque::new(); k]; n],
        log_w: vec![vec![0.0; k]; n],
        n_obs: 0,
    }))
}

impl BayesEnsemble {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let n = self.subs.len();
        let k = self.k;
        self.n_obs += 1;

        let all_dists: Vec<Vec<Dist>> = self.subs.iter_mut().map(|f| f.step(y)).collect();

        for i in 0..n {
            for h in 0..k {
                let q = &mut self.queues[i][h];
                q.push_back(all_dists[i][h].clone());
                if q.len() > h + 1 {
                    let past = q.pop_front().unwrap();
                    let mut lp = past.logpdf(y);
                    if lp > 20.0 {
                        lp = 20.0;
                    } else if !(lp >= -20.0) {
                        lp = -20.0;
                    }
                    self.log_w[i][h] +=
                        self.learning_rate * lp - self.complexity_penalty * self.depths[i];
                }
            }
        }

        let mut combined = Vec::with_capacity(k);
        for h in 0..k {
            let log_ws: Vec<f64> = (0..n).map(|i| self.log_w[i][h]).collect();
            let max_lw = log_ws.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            let weights: Vec<f64> = if max_lw.is_finite() {
                log_ws.iter().map(|&lw| libm::exp(lw - max_lw)).collect()
            } else {
                vec![1.0; n]
            };
            let horizon: Vec<&Dist> = (0..n).map(|i| &all_dists[i][h]).collect();
            let mut dist = Dist::combine_refs(&horizon, Some(&weights));
            if dist.len() > self.max_components {
                dist = dist.prune(self.max_components);
            }
            combined.push(dist);
        }
        combined
    }
}

// ---------------------------------------------------------------------------
// terminal-leaf ensemble: mix for the mean, model the residual once
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TerminalEnsemble {
    pub k: usize,
    pub learning_rate: f64,
    pub complexity_penalty: f64,
    pub forget: f64,
    pub max_components: usize,
    pub depths: Vec<f64>,
    pub subs: Vec<Sk>,
    pub qdist: Vec<VecDeque<Dist>>,
    pub log_w: Vec<f64>,
    pub tleafs: Vec<Sk>,
    pub leaf_pred: Vec<Option<Dist>>,
    pub mean_q: Vec<VecDeque<f64>>,
}

#[allow(clippy::too_many_arguments)]
pub fn terminal_leaf_ensemble(
    subs: Vec<Sk>,
    tleafs: Vec<Sk>,
    k: usize,
    learning_rate: f64,
    complexity_penalty: f64,
    depths: Vec<f64>,
    max_components: usize,
    forget: f64,
) -> Sk {
    let n = subs.len();
    assert!(n > 0 && tleafs.len() == k);
    Sk::Terminal(Box::new(TerminalEnsemble {
        k,
        learning_rate,
        complexity_penalty,
        forget,
        max_components,
        depths,
        subs,
        qdist: vec![VecDeque::new(); n],
        log_w: vec![0.0; n],
        tleafs,
        leaf_pred: vec![None; k],
        mean_q: vec![VecDeque::new(); k],
    }))
}

impl TerminalEnsemble {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let n = self.subs.len();
        let k = self.k;
        let all_dists: Vec<Vec<Dist>> = self.subs.iter_mut().map(|f| f.step(y)).collect();

        for i in 0..n {
            let q = &mut self.qdist[i];
            if let Some(past) = q.pop_front() {
                let mut lp = past.logpdf(y);
                if lp > 20.0 {
                    lp = 20.0;
                } else if !(lp >= -20.0) {
                    lp = -20.0;
                }
                self.log_w[i] = self.forget * self.log_w[i] + self.learning_rate * lp
                    - self.complexity_penalty * self.depths[i];
            }
            q.push_back(all_dists[i][0].clone());
        }

        let max_lw = self.log_w.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let w: Vec<f64> = self.log_w.iter().map(|&lw| libm::exp(lw - max_lw)).collect();
        let tot = fsum(w.iter().copied());

        let mut combined = Vec::with_capacity(k);
        for h in 0..k {
            let mu_h = fsum((0..n).map(|i| w[i] * all_dists[i][h].mean())) / tot;

            if self.mean_q[h].len() >= h + 1 {
                let r = y - self.mean_q[h].pop_front().unwrap();
                let ld = self.tleafs[h].step(r);
                self.leaf_pred[h] = Some(ld[0].clone());
            }

            let pred = if let Some(lp) = &self.leaf_pred[h] {
                lp.shift(mu_h)
            } else {
                let horizon: Vec<&Dist> = (0..n).map(|i| &all_dists[i][h]).collect();
                let mut p = Dist::combine_refs(&horizon, Some(&w));
                if p.len() > self.max_components {
                    p = p.prune(self.max_components);
                }
                p
            };
            combined.push(pred);
            self.mean_q[h].push_back(mu_h);
        }
        combined
    }
}

// ---------------------------------------------------------------------------
// multiscale: combine forecasters running on decimated clocks
// ---------------------------------------------------------------------------

const LOGPDF_FLOOR: f64 = -20.0;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Multiscale {
    pub k: usize,
    pub forget: f64,
    pub max_components: usize,
    pub scales: Vec<usize>,
    /// phase[si][ph]: one sub-skater instance per phase of scale si.
    pub phase: Vec<Vec<Sk>>,
    pub pending: Vec<Vec<Option<Dist>>>,
    pub latest: Vec<Option<Vec<Dist>>>,
    pub score: Vec<Option<f64>>,
    pub t: u64,
}

/// Mirrors Python `multiscale(base, k, scales=None, forget=0.99, max_components=20)`.
/// With scales == [1] the base forecaster is returned unwrapped.
pub fn multiscale<F: Fn(usize) -> Sk>(base: F, k: usize, scales: Option<Vec<usize>>) -> Sk {
    let mut scales = scales.unwrap_or_else(|| {
        let root = libm::ceil(libm::sqrt(k as f64)) as usize;
        vec![1, root, k]
    });
    scales.retain(|&s| 1 <= s && s <= k);
    scales.sort_unstable();
    scales.dedup();
    assert!(!scales.is_empty() && scales[0] == 1, "scales must include 1");
    if scales == [1] {
        return base(k);
    }
    let mut phase = Vec::new();
    let mut pending = Vec::new();
    for &s in &scales {
        let ks = ((k + s - 1) / s).max(1); // max(1, ceil(k / s))
        phase.push((0..s).map(|_| base(ks)).collect::<Vec<Sk>>());
        pending.push(vec![None; s]);
    }
    let ns = scales.len();
    Sk::Multiscale(Box::new(Multiscale {
        k,
        forget: 0.99,
        max_components: 20,
        scales,
        phase,
        pending,
        latest: vec![None; ns],
        score: vec![None; ns],
        t: 0,
    }))
}

impl Multiscale {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let t = self.t;
        for si in 0..self.scales.len() {
            let s = self.scales[si];
            let ph = (t % s as u64) as usize;
            if let Some(prev) = &self.pending[si][ph] {
                let lp = prev.logpdf(y).max(LOGPDF_FLOOR);
                self.score[si] = Some(match self.score[si] {
                    None => lp,
                    Some(m) => self.forget * m + (1.0 - self.forget) * lp,
                });
            }
            let dists = self.phase[si][ph].step(y);
            self.pending[si][ph] = Some(dists[0].clone());
            self.latest[si] = Some(dists);
        }
        self.t = t + 1;

        let top = self
            .score
            .iter()
            .filter_map(|m| *m)
            .fold(f64::NEG_INFINITY, f64::max);
        let top = if top == f64::NEG_INFINITY { 0.0 } else { top };

        let mut out = Vec::with_capacity(self.k);
        for h in 1..=self.k {
            let mut fcs: Vec<&Dist> = Vec::new();
            let mut wts: Vec<f64> = Vec::new();
            for si in 0..self.scales.len() {
                let s = self.scales[si];
                if s > h {
                    continue;
                }
                let dists = match &self.latest[si] {
                    Some(d) => d,
                    None => continue,
                };
                let j = ((h as f64 / s as f64 + 0.5) as i64).max(1) as usize; // half-up
                if j - 1 >= dists.len() {
                    continue;
                }
                fcs.push(&dists[j - 1]);
                let m = self.score[si].unwrap_or(top);
                wts.push(libm::exp(m - top));
            }
            if fcs.len() == 1 {
                out.push(fcs[0].clone());
            } else {
                out.push(Dist::combine_refs(&fcs, Some(&wts)).prune(self.max_components));
            }
        }
        out
    }
}

// ---------------------------------------------------------------------------
// sticky: mean-preserving lattice atoms
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Sticky {
    pub k: usize,
    pub propensity_alpha: f64,
    pub spike_frac: f64,
    pub thresh_mult: f64,
    pub max_atoms: usize,
    pub prune_eps: f64,
    pub base: Sk,
    /// Insertion-ordered (value, recency weight) table — mirrors a Python dict.
    pub counts: Vec<(f64, f64)>,
}

pub fn sticky(base: Sk, k: usize) -> Sk {
    Sk::Sticky(Box::new(Sticky {
        k,
        propensity_alpha: 0.05,
        spike_frac: 0.005,
        thresh_mult: 1.8,
        max_atoms: 6,
        prune_eps: 1e-6,
        base,
        counts: Vec::new(),
    }))
}

impl Sticky {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let dists = self.base.step(y);

        for e in self.counts.iter_mut() {
            e.1 *= 1.0 - self.propensity_alpha;
        }
        let eps = self.prune_eps;
        self.counts.retain(|e| e.1 >= eps);
        match self.counts.iter_mut().find(|e| e.0 == y) {
            Some(e) => e.1 += self.propensity_alpha,
            None => self.counts.push((y, self.propensity_alpha)),
        }

        let thr = self.thresh_mult * self.propensity_alpha;
        let mut atoms: Vec<(f64, f64)> = self
            .counts
            .iter()
            .filter(|e| e.1 > thr)
            .copied()
            .collect();
        atoms.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap()); // stable desc by weight
        atoms.truncate(self.max_atoms);

        let mut out = Vec::with_capacity(dists.len());
        for d in &dists {
            if atoms.is_empty() {
                out.push(d.clone());
                continue;
            }
            let sw = fsum(atoms.iter().map(|a| a.1));
            let p_mass = sw.min(0.999);
            let pc = 1.0 - p_mass;
            let atom_mean = fsum(atoms.iter().map(|a| a.1 * a.0)) / sw;
            let spike_std = (self.spike_frac * d.std()).max(1e-9);
            if pc <= 1e-9 {
                let comps = atoms.iter().map(|&(v, w)| (w / sw, v, spike_std)).collect();
                out.push(Dist::new(comps));
                continue;
            }
            let mu = d.mean();
            let delta = p_mass * (mu - atom_mean) / pc;
            let mut comps: Vec<(f64, f64, f64)> = atoms
                .iter()
                .map(|&(v, w)| (p_mass * (w / sw), v, spike_std))
                .collect();
            comps.extend(d.components.iter().map(|&(w, m, s)| (pc * w, m + delta, s)));
            out.push(Dist::new(comps));
        }
        out
    }
}
