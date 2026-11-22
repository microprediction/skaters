//! Online homogenized scale-mixture correction of a skater's own PIT residual
//! stream. Port of src/skaters/homogenize.py.
//!
//! A pool of two-point Gaussian scale-mixture hypotheses for the resolved
//! residual z, plus an identity candidate holding most of the prior weight,
//! is scored online by discounted Bayesian log weights. The pooled mixture H
//! reshapes the base predictive F as F~(y) = H(Phi^-1(F(y))). One pool per
//! horizon, optionally coupled across horizons ("weights", "state") or shared.

use crate::api::Forecaster;
use crate::dist::Dist;
use crate::mathx::fsum;
use crate::tails::PDist;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::OnceLock;

const EPS: f64 = 1e-12;
/// math.log(math.sqrt(2.0 * math.pi)), as Python computes it.
pub(crate) const LOG_SQRT2PI: f64 = 0.9189385332046727;
const V_MIN: f64 = 0.25;
const V_MAX: f64 = 9.0;
pub const DELTA_MAX: f64 = 0.8;
const INNOVATION_CAP: f64 = 8.0;
const ADAPT_AFTER: u64 = 10;
const WEIGHT_DECAY: f64 = 0.9999;
const LEARNING_RATE: f64 = 0.1;
const SCORE_CAP: f64 = 20.0;
pub(crate) const QGRID_N: usize = 32;
pub(crate) const QGRID_W: f64 = 1.0 / QGRID_N as f64;

pub(crate) fn qgrid_p(i: usize) -> f64 {
    (i as f64 + 0.5) / QGRID_N as f64
}

fn clip(x: f64, lo: f64, hi: f64) -> f64 {
    if x < lo {
        lo
    } else if x > hi {
        hi
    } else {
        x
    }
}

pub(crate) fn clamp01(u: f64) -> f64 {
    u.max(EPS).min(1.0 - EPS)
}

/// The standard normal quantile by the same bisection Python's
/// `Dist.gaussian(0, 1).quantile` runs.
pub(crate) fn phi_inv(p: f64) -> f64 {
    Dist::gaussian(0.0, 1.0).quantile(p)
}

pub(crate) fn std_cdf(z: f64) -> f64 {
    Dist::gaussian(0.0, 1.0).cdf(z)
}

fn phi_logpdf(z: f64) -> f64 {
    -0.5 * z * z - LOG_SQRT2PI
}

/// A scale mixture g(z) = sum_i w_i / s_i * phi(z / s_i).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Correction {
    pub weights: Vec<f64>,
    pub scales: Vec<f64>,
}

/// Log-density of a scale mixture at z (log-sum-exp).
pub fn logg(z: f64, c: &Correction) -> f64 {
    let mut best = f64::NEG_INFINITY;
    let mut terms = Vec::with_capacity(c.weights.len());
    for (&w, &s) in c.weights.iter().zip(c.scales.iter()) {
        if w <= 0.0 {
            continue;
        }
        let t = libm::log(w) - libm::log(s) + phi_logpdf(z / s);
        terms.push(t);
        if t > best {
            best = t;
        }
    }
    if best == f64::NEG_INFINITY {
        return f64::NEG_INFINITY;
    }
    best + libm::log(fsum(terms.iter().map(|&t| libm::exp(t - best))))
}

/// One correction hypothesis: a filter of rate `rho` and gain `gain` on
/// H_2(z), split into a two-point scale mixture by `delta`.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Candidate {
    pub rho: f64,
    pub gain: f64,
    pub delta: f64,
    pub is_identity: bool,
}

/// Python's `make_candidates(rho_grid, gain_grid, delta_grid, delta_max)`:
/// the identity candidate, then the grid in rho, gain, delta order.
pub fn make_candidates(
    rho_grid: &[f64],
    gain_grid: &[f64],
    delta_grid: &[f64],
    delta_max: f64,
) -> Result<Vec<Candidate>, String> {
    if !(0.0..1.0).contains(&delta_max) {
        return Err(format!(
            "delta_max must satisfy 0 <= delta_max < 1, got {delta_max}"
        ));
    }
    for &d in delta_grid {
        if !(0.0..1.0).contains(&d) {
            return Err(format!(
                "delta_grid entries must satisfy 0 <= delta < 1, got {d}"
            ));
        }
    }
    let mut c = vec![Candidate {
        rho: 0.0,
        gain: 0.0,
        delta: 0.0,
        is_identity: true,
    }];
    for &rho in rho_grid {
        for &gain in gain_grid {
            for &delta in delta_grid {
                c.push(Candidate {
                    rho,
                    gain,
                    delta: clip(delta, 0.0, delta_max),
                    is_identity: false,
                });
            }
        }
    }
    Ok(c)
}

/// The default grid: rho in (0, 0.8, 0.95, 0.99), gain in (0.03, 0.12),
/// delta in (0, 0.25, 0.5).
pub fn default_candidates() -> Vec<Candidate> {
    make_candidates(
        &[0.0, 0.8, 0.95, 0.99],
        &[0.03, 0.12],
        &[0.0, 0.25, 0.50],
        DELTA_MAX,
    )
    .expect("default grid")
}

fn cand_scales(v: f64, delta: f64) -> Vec<f64> {
    if delta <= 0.0 {
        return vec![v.sqrt()];
    }
    vec![(v * (1.0 - delta)).sqrt(), (v * (1.0 + delta)).sqrt()]
}

fn cand_weights(delta: f64) -> Vec<f64> {
    if delta <= 0.0 {
        vec![1.0]
    } else {
        vec![0.5, 0.5]
    }
}

/// One candidate's online state.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CandState {
    pub q: f64,
    pub log_weight: f64,
    pub guard_run: u64,
}

/// One horizon's pool: per-candidate state, the issued correction, a count.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Cell {
    pub dynamic: Vec<CandState>,
    pub issued: Option<Correction>,
    pub n: u64,
}

fn init_cell(candidates: &[Candidate]) -> Cell {
    let n_other = candidates.iter().filter(|c| !c.is_identity).count().max(1);
    Cell {
        dynamic: candidates
            .iter()
            .map(|c| CandState {
                q: 0.0,
                log_weight: if c.is_identity {
                    libm::log(n_other as f64)
                } else {
                    0.0
                },
                guard_run: 0,
            })
            .collect(),
        issued: None,
        n: 0,
    }
}

fn update_q(d: &mut CandState, cfg: &Candidate, x: f64) {
    let q_minus = cfg.rho * d.q;
    let resid = x - q_minus;
    let capped = resid.abs() > INNOVATION_CAP;
    d.guard_run = if capped { d.guard_run + 1 } else { 0 };
    let used = if capped && d.guard_run <= ADAPT_AFTER {
        clip(resid, -INNOVATION_CAP, INNOVATION_CAP)
    } else {
        resid
    };
    d.q = q_minus + cfg.gain * used;
}

/// Exact Bayesian pooling of the candidates into one scale mixture.
pub fn pool(candidates: &[Candidate], dynamic: &[CandState]) -> Correction {
    let m = dynamic
        .iter()
        .map(|d| d.log_weight)
        .fold(f64::NEG_INFINITY, f64::max);
    let raw: Vec<f64> = dynamic
        .iter()
        .map(|d| libm::exp(d.log_weight - m))
        .collect();
    let total = fsum(raw.iter().copied());
    let mut weights = Vec::new();
    let mut scales = Vec::new();
    for ((cfg, d), r) in candidates.iter().zip(dynamic.iter()).zip(raw.iter()) {
        let w = r / total;
        let v = clip(1.0 + d.q, V_MIN, V_MAX);
        for (s, cw) in cand_scales(v, cfg.delta)
            .into_iter()
            .zip(cand_weights(cfg.delta))
        {
            scales.push(s);
            weights.push(w * cw);
        }
    }
    Correction { weights, scales }
}

/// Score, update and pool one horizon's candidates against a resolved z.
pub fn cell_step(z: f64, cell: Option<Cell>, candidates: &[Candidate]) -> (Correction, Cell) {
    let mut cell = cell.unwrap_or_else(|| init_cell(candidates));
    let x = z * z - 1.0;
    for (cfg, d) in candidates.iter().zip(cell.dynamic.iter_mut()) {
        let v = clip(1.0 + d.q, V_MIN, V_MAX);
        let c = Correction {
            weights: cand_weights(cfg.delta),
            scales: cand_scales(v, cfg.delta),
        };
        let r = logg(z, &c) - phi_logpdf(z);
        d.log_weight = WEIGHT_DECAY * d.log_weight + LEARNING_RATE * clip(r, -SCORE_CAP, SCORE_CAP);
    }
    for (cfg, d) in candidates.iter().zip(cell.dynamic.iter_mut()) {
        update_q(d, cfg, x);
    }
    let correction = pool(candidates, &cell.dynamic);
    cell.issued = Some(correction.clone());
    cell.n += 1;
    (correction, cell)
}

/// The base predictive reshaped by a pooled scale-mixture correction.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HomogenizedDist {
    pub base: PDist,
    pub correction: Correction,
    #[serde(skip)]
    qgrid: OnceLock<Vec<f64>>,
}

impl HomogenizedDist {
    pub fn new(base: PDist, correction: Correction) -> HomogenizedDist {
        HomogenizedDist {
            base,
            correction,
            qgrid: OnceLock::new(),
        }
    }

    fn z(&self, y: f64) -> f64 {
        phi_inv(clamp01(self.base.cdf(y)))
    }

    fn z_cdf(&self, z: f64) -> f64 {
        let mut total = 0.0;
        for (&w, &s) in self
            .correction
            .weights
            .iter()
            .zip(self.correction.scales.iter())
        {
            total += w * std_cdf(z / s);
        }
        clamp01(total)
    }

    fn z_quantile(&self, p: f64, tol: f64, max_iter: usize) -> f64 {
        let (mut lo, mut hi) = (-40.0_f64, 40.0_f64);
        for _ in 0..max_iter {
            let mid = 0.5 * (lo + hi);
            if self.z_cdf(mid) < p {
                lo = mid;
            } else {
                hi = mid;
            }
            if hi - lo < tol {
                break;
            }
        }
        0.5 * (lo + hi)
    }

    pub fn cdf(&self, y: f64) -> f64 {
        self.z_cdf(self.z(y))
    }

    pub fn logpdf(&self, y: f64) -> f64 {
        let z = self.z(y);
        self.base.logpdf(y) + logg(z, &self.correction) - phi_logpdf(z)
    }

    pub fn quantile(&self, p: f64) -> f64 {
        self.quantile_tol(p, 1e-9, 2100)
    }

    pub fn quantile_tol(&self, p: f64, tol: f64, max_iter: usize) -> f64 {
        assert!(0.0 < p && p < 1.0);
        let hp = self.z_quantile(p, tol, max_iter);
        let u = clamp01(std_cdf(hp));
        self.base.quantile_tol(u, tol, max_iter)
    }

    fn grid(&self) -> &[f64] {
        self.qgrid
            .get_or_init(|| (0..QGRID_N).map(|i| self.quantile(qgrid_p(i))).collect())
    }

    pub fn mean(&self) -> f64 {
        fsum(self.grid().iter().copied()) * QGRID_W
    }

    pub fn var(&self) -> f64 {
        let mu = self.mean();
        fsum(self.grid().iter().map(|&q| (q - mu) * (q - mu))) * QGRID_W
    }

    pub fn std(&self) -> f64 {
        let v = self.var();
        if v > 0.0 {
            v.sqrt()
        } else {
            0.0
        }
    }

    pub fn crps(&self, x: f64) -> f64 {
        grid_crps(self.grid(), x)
    }
}

/// CRPS by the quantile-form identity on the 32-point midpoint grid.
pub(crate) fn grid_crps(q: &[f64], x: f64) -> f64 {
    let mut total = 0.0;
    for (i, &qi) in q.iter().enumerate() {
        let ind = if x <= qi { 1.0 } else { 0.0 };
        total += (qi - x) * (ind - qgrid_p(i));
    }
    2.0 * total * QGRID_W
}

/// The homogenize wrapper (Python `homogenize(base, candidates, k, couple, lam)`).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Homogenize {
    pub k: usize,
    /// "none", "weights", "state" or "shared"
    pub couple: String,
    pub lam: f64,
    pub candidates: Vec<Candidate>,
    pub inner: Forecaster,
    pub raw: Option<PDist>,
    pub pending: VecDeque<Vec<PDist>>,
    pub cell: Vec<Option<Cell>>,
    pub correction: Vec<Option<Correction>>,
}

/// `homogenize(base, candidates=None, k, couple="none", lam=0.25)`.
pub fn homogenize(
    inner: Forecaster,
    candidates: Option<Vec<Candidate>>,
    k: usize,
    couple: &str,
    lam: f64,
) -> Forecaster {
    assert!(k >= 1);
    assert!(
        matches!(couple, "none" | "weights" | "state" | "shared"),
        "couple must be none, weights, state or shared"
    );
    Forecaster::Homog(Box::new(Homogenize {
        k,
        couple: couple.to_string(),
        lam,
        candidates: candidates.unwrap_or_else(default_candidates),
        inner,
        raw: None,
        pending: VecDeque::new(),
        cell: vec![None; k],
        correction: vec![None; k],
    }))
}

impl Homogenize {
    pub(crate) fn reset(&mut self) {
        self.raw = None;
        self.pending.clear();
        self.cell = vec![None; self.k];
        self.correction = vec![None; self.k];
    }

    fn couple_cells(&mut self) {
        let lam = self.lam;
        let live: Vec<usize> = (0..self.k).filter(|&j| self.cell[j].is_some()).collect();
        if live.len() < 2 || lam <= 0.0 {
            return;
        }
        let n = self.cell[live[0]].as_ref().unwrap().dynamic.len();
        if self.couple == "weights" {
            for i in 0..n {
                let mean_w = fsum(
                    live.iter()
                        .map(|&j| self.cell[j].as_ref().unwrap().dynamic[i].log_weight),
                ) / live.len() as f64;
                for &j in &live {
                    let d = &mut self.cell[j].as_mut().unwrap().dynamic[i];
                    d.log_weight = (1.0 - lam) * d.log_weight + lam * mean_w;
                }
            }
        } else if self.couple == "state" {
            for i in 0..n {
                let mut prev: Option<f64> = None;
                for &j in &live {
                    let d = &mut self.cell[j].as_mut().unwrap().dynamic[i];
                    if let Some(p) = prev {
                        d.q = (1.0 - lam) * d.q + lam * p;
                    }
                    prev = Some(d.q);
                }
            }
        }
    }

    pub fn step(&mut self, y: f64) -> Vec<PDist> {
        let k = self.k;
        let n = self.pending.len();
        let shared = self.couple == "shared";
        for m in 1..=k {
            if m > n {
                continue;
            }
            let u = clamp01(self.pending[n - m][m - 1].cdf(y));
            let z = phi_inv(u);
            if z.is_nan() {
                continue;
            }
            let slot = if shared { 0 } else { m - 1 };
            let (corr, cell) = cell_step(z, self.cell[slot].take(), &self.candidates);
            self.cell[slot] = Some(cell);
            if shared {
                for j in 0..k {
                    self.correction[j] = Some(corr.clone());
                }
            } else {
                self.correction[m - 1] = Some(corr);
            }
        }
        if self.couple == "weights" || self.couple == "state" {
            self.couple_cells();
            for m in 0..k {
                if let Some(c) = &self.cell[m] {
                    self.correction[m] = Some(pool(&self.candidates, &c.dynamic));
                }
            }
        }
        let dists = self.inner.step(y);
        self.raw = Some(dists[0].clone());
        self.pending.push_back(dists.clone());
        if self.pending.len() > k {
            self.pending.pop_front();
        }
        (1..=k)
            .map(|m| {
                let d = if m - 1 < dists.len() {
                    dists[m - 1].clone()
                } else {
                    dists[dists.len() - 1].clone()
                };
                match &self.correction[m - 1] {
                    None => d,
                    Some(c) => PDist::Homog(Box::new(HomogenizedDist::new(d, c.clone()))),
                }
            })
            .collect()
    }
}
