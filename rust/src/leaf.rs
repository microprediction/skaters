//! Residual distribution estimators: the leaves of every prediction tree.
//! Port of src/skaters/leaf.py (leaf, scale_mixture_leaf, crps_leaf, garch_leaf).

use crate::dist::Dist;
use crate::mathx::fsum;
use crate::runstats::RunningVar;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

pub const SCALE_BASIS: [f64; 5] = [0.7, 1.0, 1.6, 3.0, 6.0];

/// FINE = tuple(round(0.4 * 1.28 ** i, 4) for i in range(15)) — precomputed
/// so no runtime rounding semantics are involved.
pub const FINE: [f64; 15] = [
    0.4, 0.512, 0.6554, 0.8389, 1.0737, 1.3744, 1.7592, 2.2518, 2.8823, 3.6893, 4.7224, 6.0446,
    7.7371, 9.9035, 12.6765,
];

fn one_idx(scales: &[f64]) -> usize {
    let mut best = 0usize;
    for i in 1..scales.len() {
        if (scales[i] - 1.0).abs() < (scales[best] - 1.0).abs() {
            best = i;
        }
    }
    best
}

// ---------------------------------------------------------------------------
// Plain centered Gaussian leaf
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Leaf {
    pub k: usize,
    pub var: RunningVar,
}

impl Leaf {
    pub fn new(k: usize) -> Leaf {
        Leaf {
            k,
            var: RunningVar::new(),
        }
    }

    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        self.var.update(y);
        let (_, var) = self.var.get();
        let std = if var.is_finite() && var > 0.0 {
            var.sqrt()
        } else {
            y.abs().max(1e-8)
        };
        vec![Dist::gaussian(0.0, std); self.k]
    }
}

// ---------------------------------------------------------------------------
// Scale-mixture leaf (likelihood / online-EM objective)
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ScaleMixLeaf {
    pub k: usize,
    pub gamma: f64,
    pub scale_alpha: f64,
    pub scales: Vec<f64>,
    pub v: f64,
    pub w: Vec<f64>,
    pub n: u64,
}

impl ScaleMixLeaf {
    pub fn new(k: usize, gamma: f64, scale_alpha: f64) -> ScaleMixLeaf {
        let scales = SCALE_BASIS.to_vec();
        let mut w = vec![1e-6; scales.len()];
        w[one_idx(&scales)] = 1.0;
        ScaleMixLeaf {
            k,
            gamma,
            scale_alpha,
            scales,
            v: 0.0,
            w,
            n: 0,
        }
    }

    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let kk = self.scales.len();
        self.n += 1;
        let a = if self.scale_alpha > 1.0 / self.n as f64 {
            self.scale_alpha
        } else {
            1.0 / self.n as f64
        };
        self.v = (1.0 - a) * self.v + a * y * y;
        let var = self.v;
        let sigma = if var.is_finite() && var > 0.0 {
            var.sqrt()
        } else {
            y.abs().max(1e-8)
        };
        let z = y / sigma;
        let dens: Vec<f64> = (0..kk)
            .map(|i| {
                let c = self.scales[i];
                self.w[i] * libm::exp(-0.5 * z * z / (c * c)) / c
            })
            .collect();
        let total = fsum(dens.iter().copied());
        if total > 0.0 {
            let g = if self.gamma > 1.0 / self.n as f64 {
                self.gamma
            } else {
                1.0 / self.n as f64
            };
            for i in 0..kk {
                self.w[i] = (1.0 - g) * self.w[i] + g * dens[i] / total;
            }
        }
        let d = Dist::new(
            (0..kk)
                .map(|i| (self.w[i], 0.0, self.scales[i] * sigma))
                .collect(),
        );
        vec![d; self.k]
    }
}

// ---------------------------------------------------------------------------
// CRPS leaf: exponentiated-gradient descent on the closed-form mixture CRPS
// ---------------------------------------------------------------------------

const S2: f64 = crate::mathx::SQRT2;
const INV: f64 = 0.3989422804014327; // 1/sqrt(2*pi)
const A0: f64 = 0.7978845608028654; // 2*phi(0)

fn phi_cdf(x: f64) -> f64 {
    0.5 * (1.0 + libm::erf(x / S2))
}

fn phi_pdf(x: f64) -> f64 {
    libm::exp(-0.5 * x * x) * INV
}

fn abs_normal(m: f64, s: f64) -> f64 {
    if s <= 0.0 {
        return m.abs();
    }
    let z = m / s;
    m * (2.0 * phi_cdf(z) - 1.0) + 2.0 * s * phi_pdf(z)
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CrpsLeaf {
    pub k: usize,
    pub eta: f64,
    pub scale_alpha: f64,
    pub scales: Vec<f64>,
    pub b: Vec<Vec<f64>>,
    pub v: f64,
    pub w: Vec<f64>,
    pub n: u64,
}

impl CrpsLeaf {
    pub fn new(k: usize, eta: f64, scale_alpha: f64) -> CrpsLeaf {
        let scales = FINE.to_vec();
        let kk = scales.len();
        let b: Vec<Vec<f64>> = (0..kk)
            .map(|a| {
                (0..kk)
                    .map(|bb| (scales[a] * scales[a] + scales[bb] * scales[bb]).sqrt() * A0)
                    .collect()
            })
            .collect();
        let mut w = vec![1e-6; kk];
        w[one_idx(&scales)] = 1.0;
        CrpsLeaf {
            k,
            eta,
            scale_alpha,
            scales,
            b,
            v: 0.0,
            w,
            n: 0,
        }
    }

    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let kk = self.scales.len();
        self.n += 1;
        let a = if self.scale_alpha > 1.0 / self.n as f64 {
            self.scale_alpha
        } else {
            1.0 / self.n as f64
        };
        self.v = (1.0 - a) * self.v + a * y * y;
        let sig = if self.v.is_finite() && self.v > 0.0 {
            self.v.sqrt()
        } else {
            y.abs().max(1e-8)
        };
        let z = y / sig;
        let w = &self.w;
        let g: Vec<f64> = (0..kk)
            .map(|c| {
                abs_normal(-z, self.scales[c]) - fsum((0..kk).map(|j| w[j] * self.b[c][j]))
            })
            .collect();
        let gm = fsum(g.iter().copied()) / kk as f64;
        let e: Vec<f64> = (0..kk).map(|c| -self.eta * (g[c] - gm)).collect();
        let emax = e.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let mut nw: Vec<f64> = (0..kk).map(|c| w[c] * libm::exp(e[c] - emax)).collect();
        let mut zt = fsum(nw.iter().copied());
        if !(zt > 0.0 && zt.is_finite()) {
            nw = w.clone();
            zt = fsum(nw.iter().copied());
        }
        self.w = nw.iter().map(|x| x / zt).collect();
        let d = Dist::new(
            (0..kk)
                .map(|c| (self.w[c], 0.0, self.scales[c] * sig))
                .collect(),
        );
        vec![d; self.k]
    }
}

// ---------------------------------------------------------------------------
// GARCH(1,1)-t leaf: genuine GARCH conditional variance, scale-mixture tails
// ---------------------------------------------------------------------------

const GARCH_A: [f64; 7] = [0.02, 0.04, 0.06, 0.09, 0.12, 0.16, 0.20];
const GARCH_B: [f64; 7] = [0.72, 0.78, 0.84, 0.88, 0.92, 0.95, 0.97];
const GARCH_OMEGA_MULT: [f64; 5] = [0.5, 0.7, 1.0, 1.4, 2.0];

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GarchLeaf {
    pub k: usize,
    pub gamma: f64,
    pub refit_every: u64,
    pub min_obs: u64,
    pub window: usize,
    pub scales: Vec<f64>,
    pub h: f64,
    pub s2: f64,
    pub n: u64,
    pub omega: f64,
    pub alpha: f64,
    pub beta: f64,
    pub buf: VecDeque<f64>,
    pub w: Vec<f64>,
    pub last_r2: f64,
}

impl GarchLeaf {
    pub fn new(k: usize) -> GarchLeaf {
        let scales = SCALE_BASIS.to_vec();
        let mut w = vec![1e-6; scales.len()];
        w[one_idx(&scales)] = 1.0;
        GarchLeaf {
            k,
            gamma: 0.02,
            refit_every: 40,
            min_obs: 80,
            window: 400,
            scales,
            h: 0.0,
            s2: 0.0,
            n: 0,
            omega: 0.0,
            alpha: 0.05,
            beta: 0.90,
            buf: VecDeque::new(),
            w,
            last_r2: 0.0,
        }
    }

    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let kk = self.scales.len();
        self.n += 1;
        let a0 = if 0.02 > 1.0 / self.n as f64 {
            0.02
        } else {
            1.0 / self.n as f64
        };
        self.s2 = (1.0 - a0) * self.s2 + a0 * y * y;
        if self.s2 <= 0.0 {
            self.s2 = (y * y).max(1e-12);
        }

        let mut h = if self.n == 1 {
            self.s2
        } else {
            self.omega + self.alpha * self.last_r2 + self.beta * self.h
        };
        if h <= 1e-300 {
            h = self.s2;
        }
        self.h = h;
        self.last_r2 = y * y;
        self.buf.push_back(y);
        if self.buf.len() > self.window {
            self.buf.pop_front();
        }

        if self.n >= self.min_obs
            && self.n % self.refit_every == 0
            && self.buf.len() >= self.min_obs as usize
        {
            let resid: Vec<f64> = self.buf.iter().copied().collect();
            let s2 = fsum(resid.iter().map(|r| r * r)) / resid.len() as f64;
            if s2 > 0.0 {
                let mut best_v = f64::INFINITY;
                let mut best = (self.omega, self.alpha, self.beta);
                let mut found = false;
                for &al in GARCH_A.iter() {
                    for &be in GARCH_B.iter() {
                        if al + be >= 0.999 {
                            continue;
                        }
                        let base = (1.0 - al - be) * s2;
                        for &c in GARCH_OMEGA_MULT.iter() {
                            let om = if base * c > 1e-12 { base * c } else { 1e-12 };
                            let mut hh = om / (1.0 - al - be);
                            let mut v = 0.0;
                            for &r in &resid {
                                hh = om + al * (r * r) + be * hh;
                                if hh <= 1e-300 {
                                    hh = 1e-300;
                                }
                                v += libm::log(hh) + (r * r) / hh;
                            }
                            if v < best_v {
                                best_v = v;
                                best = (om, al, be);
                                found = true;
                            }
                        }
                    }
                }
                if found {
                    self.omega = best.0;
                    self.alpha = best.1;
                    self.beta = best.2;
                }
            }
        }

        let sigma = if h.is_finite() && h > 0.0 {
            h.sqrt()
        } else {
            y.abs().max(1e-8)
        };
        let z = y / sigma;
        let dens: Vec<f64> = (0..kk)
            .map(|i| {
                let c = self.scales[i];
                self.w[i] * libm::exp(-0.5 * z * z / (c * c)) / c
            })
            .collect();
        let total = fsum(dens.iter().copied());
        if total > 0.0 {
            let g = if self.gamma > 1.0 / self.n as f64 {
                self.gamma
            } else {
                1.0 / self.n as f64
            };
            for i in 0..kk {
                self.w[i] = (1.0 - g) * self.w[i] + g * dens[i] / total;
            }
        }
        let d = Dist::new(
            (0..kk)
                .map(|i| (self.w[i], 0.0, self.scales[i] * sigma))
                .collect(),
        );
        vec![d; self.k]
    }
}
