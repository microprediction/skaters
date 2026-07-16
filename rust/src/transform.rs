//! Invertible online transforms for conjugation. Port of src/skaters/transform.py.
//!
//! Each transform has `forward(&mut self, y) -> f64` (runs per observation) and
//! `inverse_k(&self, dists) -> Vec<Dist>` (maps k transformed-space predictions
//! back). Python initialises transform state lazily on the first call; here an
//! `init` flag reproduces the first-call special cases exactly.

use crate::dist::Dist;
use crate::mathx::fsum;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum Transform {
    Difference(Difference),
    FracDiff(FracDiff),
    Standardize(Standardize),
    EmaT(EmaT),
    Ou(Ou),
    Theta(Theta),
    Drift(Drift),
    Holt(Holt),
    Garch(Garch),
    Seasonal(Seasonal),
    SeasonalAnchor(SeasonalAnchor),
    Power(Power),
    YeoJohnson(YeoJohnson),
    Ar(Ar),
    GroupedAr(GroupedAr),
}

impl Transform {
    pub fn forward(&mut self, y: f64) -> f64 {
        match self {
            Transform::Difference(t) => t.forward(y),
            Transform::FracDiff(t) => t.forward(y),
            Transform::Standardize(t) => t.forward(y),
            Transform::EmaT(t) => t.forward(y),
            Transform::Ou(t) => t.forward(y),
            Transform::Theta(t) => t.forward(y),
            Transform::Drift(t) => t.forward(y),
            Transform::Holt(t) => t.forward(y),
            Transform::Garch(t) => t.forward(y),
            Transform::Seasonal(t) => t.forward(y),
            Transform::SeasonalAnchor(t) => t.forward(y),
            Transform::Power(t) => t.forward(y),
            Transform::YeoJohnson(t) => t.forward(y),
            Transform::Ar(t) => t.forward(y),
            Transform::GroupedAr(t) => t.forward(y),
        }
    }

    pub fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        match self {
            Transform::Difference(t) => t.inverse_k(dists),
            Transform::FracDiff(t) => t.inverse_k(dists),
            Transform::Standardize(t) => t.inverse_k(dists),
            Transform::EmaT(t) => t.inverse_k(dists),
            Transform::Ou(t) => t.inverse_k(dists),
            Transform::Theta(t) => t.inverse_k(dists),
            Transform::Drift(t) => t.inverse_k(dists),
            Transform::Holt(t) => t.inverse_k(dists),
            Transform::Garch(t) => t.inverse_k(dists),
            Transform::Seasonal(t) => t.inverse_k(dists),
            Transform::SeasonalAnchor(t) => t.inverse_k(dists),
            Transform::Power(t) => t.inverse_k(dists),
            Transform::YeoJohnson(t) => t.inverse_k(dists),
            Transform::Ar(t) => t.inverse_k(dists),
            Transform::GroupedAr(t) => t.inverse_k(dists),
        }
    }
}

// ---------------------------------------------------------------------------
// difference
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Difference {
    pub last: f64,
    pub init: bool,
}

pub fn difference() -> Transform {
    Transform::Difference(Difference {
        last: 0.0,
        init: false,
    })
}

impl Difference {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.last = y;
            return 0.0;
        }
        let dy = y - self.last;
        self.last = y;
        dy
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let anchor = self.last;
        let mut result = Vec::with_capacity(dists.len());
        let mut cumsum_mean = 0.0;
        let mut cumsum_var = 0.0;
        for d in dists {
            cumsum_mean += d.mean();
            cumsum_var += d.var();
            let std = if cumsum_var > 0.0 {
                cumsum_var.sqrt()
            } else {
                d.std().max(1e-12)
            };
            result.push(Dist::gaussian(anchor + cumsum_mean, std));
        }
        result
    }
}

// ---------------------------------------------------------------------------
// fractional difference
// ---------------------------------------------------------------------------

fn frac_diff_weights(d: f64, window: usize) -> Vec<f64> {
    let mut w = vec![1.0];
    for i in 1..window {
        let last = *w.last().unwrap();
        w.push(-last * (d - i as f64 + 1.0) / i as f64);
    }
    w
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FracDiff {
    pub window: usize,
    pub w_fwd: Vec<f64>,
    pub buffer: Vec<f64>,
}

pub fn fractional_difference(d: f64, window: usize) -> Transform {
    Transform::FracDiff(FracDiff {
        window,
        w_fwd: frac_diff_weights(d, window),
        buffer: Vec::new(),
    })
}

impl FracDiff {
    fn forward(&mut self, y: f64) -> f64 {
        self.buffer.push(y);
        if self.buffer.len() > self.window {
            self.buffer.remove(0);
        }
        let n = self.buffer.len();
        fsum((0..n).map(|j| self.w_fwd[j] * self.buffer[n - 1 - j]))
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let mut buf = self.buffer.clone();
        let mut result = Vec::with_capacity(dists.len());
        for d_in in dists {
            buf.push(0.0);
            let n = buf.len();
            let mut shift = 0.0;
            for j in 1..n.min(self.window) {
                shift -= self.w_fwd[j] * buf[n - 1 - j];
            }
            let recovered_mean = d_in.mean() + shift;
            buf[n - 1] = recovered_mean;
            result.push(Dist::gaussian(recovered_mean, d_in.std()));
            if buf.len() > self.window {
                buf.remove(0);
            }
        }
        result
    }
}

// ---------------------------------------------------------------------------
// standardize
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Standardize {
    pub alpha: f64,
    pub eps: f64,
    pub mu: f64,
    pub var: f64,
    pub init: bool,
}

pub fn standardize(alpha: f64, eps: f64) -> Transform {
    Transform::Standardize(Standardize {
        alpha,
        eps,
        mu: 0.0,
        var: 0.0,
        init: false,
    })
}

impl Standardize {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.mu = y;
            self.var = 0.0;
            return 0.0;
        }
        let mu = self.mu;
        let diff = y - mu;
        let mu_new = mu + self.alpha * diff;
        let var = (1.0 - self.alpha) * self.var + self.alpha * diff * diff;
        let sigma = if var > self.eps * self.eps {
            var.sqrt()
        } else {
            self.eps
        };
        self.mu = mu_new;
        self.var = var;
        diff / sigma
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let sigma = if self.var > 1e-16 {
            self.var.sqrt()
        } else {
            1e-8
        };
        dists.iter().map(|d| d.affine(sigma, self.mu)).collect()
    }
}

// ---------------------------------------------------------------------------
// ema transform
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EmaT {
    pub alpha: f64,
    pub level: f64,
    pub init: bool,
}

pub fn ema_transform(alpha: f64) -> Transform {
    assert!(0.0 < alpha && alpha < 1.0);
    Transform::EmaT(EmaT {
        alpha,
        level: 0.0,
        init: false,
    })
}

impl EmaT {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.level = y;
            return 0.0;
        }
        let residual = y - self.level;
        self.level += self.alpha * residual;
        residual
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        dists.iter().map(|d| d.shift(self.level)).collect()
    }
}

// ---------------------------------------------------------------------------
// Ornstein-Uhlenbeck transform
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Ou {
    pub alpha: f64,
    pub phi: f64,
    pub m: f64,
    pub fc: f64,
    pub y: f64,
    pub init: bool,
}

pub fn ou_transform(kappa: f64, alpha: f64) -> Transform {
    assert!(0.0 < kappa && kappa <= 1.0);
    assert!(0.0 < alpha && alpha < 1.0);
    Transform::Ou(Ou {
        alpha,
        phi: 1.0 - kappa,
        m: 0.0,
        fc: 0.0,
        y: 0.0,
        init: false,
    })
}

impl Ou {
    fn forward(&mut self, y: f64) -> f64 {
        // Python: `if state is None or not math.isfinite(y)` — a non-finite y
        // RESETS the state even after initialisation.
        if !self.init || !y.is_finite() {
            let y0 = if y.is_finite() { y } else { 0.0 };
            self.init = true;
            self.m = y0;
            self.fc = y0;
            self.y = y0;
            return 0.0;
        }
        let mut resid = y - self.fc;
        if !resid.is_finite() {
            resid = 0.0;
        }
        let m = self.m + self.alpha * (y - self.m);
        let fc = m + self.phi * (y - m);
        self.m = m;
        self.fc = fc;
        self.y = y;
        resid
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let (m, ylast) = (self.m, self.y);
        let phi = self.phi;
        let mut out = Vec::with_capacity(dists.len());
        for (h0, d) in dists.iter().enumerate() {
            let h = (h0 + 1) as f64;
            let center = m + libm::pow(phi, h) * (ylast - m);
            let g = if phi < 1.0 - 1e-9 {
                ((1.0 - libm::pow(phi, 2.0 * h)) / (1.0 - phi * phi)).sqrt()
            } else {
                h.sqrt()
            };
            out.push(d.scale(g).shift(center));
        }
        out
    }
}

// ---------------------------------------------------------------------------
// theta
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Theta {
    pub alpha: f64,
    pub ses: f64,
    pub t: u64,
    pub sum_t: f64,
    pub sum_t2: f64,
    pub sum_y: f64,
    pub sum_ty: f64,
    pub slope: f64,
    pub init: bool,
}

pub fn theta(alpha: f64) -> Transform {
    assert!(0.0 < alpha && alpha < 1.0);
    Transform::Theta(Theta {
        alpha,
        ses: 0.0,
        t: 0,
        sum_t: 0.0,
        sum_t2: 0.0,
        sum_y: 0.0,
        sum_ty: 0.0,
        slope: 0.0,
        init: false,
    })
}

impl Theta {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.ses = y;
            self.t = 1;
            self.sum_t = 1.0;
            self.sum_t2 = 1.0;
            self.sum_y = y;
            self.sum_ty = y;
            self.slope = 0.0; // Python: key absent, read via .get(..., 0.0)
            return 0.0;
        }
        self.t += 1;
        let t = self.t as f64;

        let forecast = self.ses + self.slope / 2.0;
        let residual = y - forecast;

        self.ses = self.alpha * y + (1.0 - self.alpha) * self.ses;

        self.sum_t += t;
        self.sum_t2 += t * t;
        self.sum_y += y;
        self.sum_ty += t * y;

        let n = t;
        let denom = n * self.sum_t2 - self.sum_t * self.sum_t;
        self.slope = if denom.abs() > 1e-12 {
            (n * self.sum_ty - self.sum_t * self.sum_y) / denom
        } else {
            0.0
        };
        residual
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let mut result = Vec::with_capacity(dists.len());
        let mut cumsum_var = 0.0;
        for (h, d) in dists.iter().enumerate() {
            cumsum_var += d.var();
            let forecast = self.ses + (h + 1) as f64 * self.slope / 2.0 + d.mean();
            let std = if cumsum_var > 0.0 {
                cumsum_var.sqrt()
            } else {
                d.std().max(1e-12)
            };
            result.push(Dist::gaussian(forecast, std));
        }
        result
    }
}

// ---------------------------------------------------------------------------
// drift
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Drift {
    pub alpha: f64,
    pub decay: f64,
    pub last: f64,
    pub mu: f64,
    pub init: bool,
}

pub fn drift(alpha: f64, shrinkage: f64) -> Transform {
    assert!(0.0 < alpha && alpha < 1.0);
    assert!((0.0..1.0).contains(&shrinkage));
    Transform::Drift(Drift {
        alpha,
        decay: 1.0 - alpha - shrinkage,
        last: 0.0,
        mu: 0.0,
        init: false,
    })
}

impl Drift {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.last = y;
            self.mu = 0.0;
            return 0.0;
        }
        let dy = y - self.last;
        let residual = dy - self.mu;
        self.mu = self.decay * self.mu + self.alpha * dy;
        self.last = y;
        residual
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let anchor = self.last;
        let mu = self.mu;
        let mut result = Vec::with_capacity(dists.len());
        let mut cumsum_mean = 0.0;
        let mut cumsum_var = 0.0;
        for (h, d) in dists.iter().enumerate() {
            cumsum_mean += d.mean();
            cumsum_var += d.var();
            let total_mean = anchor + (h + 1) as f64 * mu + cumsum_mean;
            let total_std = if cumsum_var > 0.0 {
                cumsum_var.sqrt()
            } else {
                d.std().max(1e-12)
            };
            result.push(Dist::gaussian(total_mean, total_std));
        }
        result
    }
}

// ---------------------------------------------------------------------------
// Holt linear
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Holt {
    pub alpha: f64,
    pub beta: f64,
    pub level: f64,
    pub trend: f64,
    pub init: bool,
}

pub fn holt_linear(alpha: f64, beta: f64) -> Transform {
    assert!(0.0 < alpha && alpha < 1.0);
    assert!(0.0 < beta && beta < 1.0);
    Transform::Holt(Holt {
        alpha,
        beta,
        level: 0.0,
        trend: 0.0,
        init: false,
    })
}

impl Holt {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.level = y;
            self.trend = 0.0;
            return 0.0;
        }
        let l_prev = self.level;
        let b_prev = self.trend;
        let l_new = self.alpha * y + (1.0 - self.alpha) * (l_prev + b_prev);
        let b_new = self.beta * (l_new - l_prev) + (1.0 - self.beta) * b_prev;
        let residual = y - (l_prev + b_prev);
        self.level = l_new;
        self.trend = b_new;
        residual
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let mut result = Vec::with_capacity(dists.len());
        let mut cumsum_var = 0.0;
        for (h, d) in dists.iter().enumerate() {
            cumsum_var += d.var();
            let forecast = self.level + (h + 1) as f64 * self.trend + d.mean();
            let std = if cumsum_var > 0.0 {
                cumsum_var.sqrt()
            } else {
                d.std().max(1e-12)
            };
            result.push(Dist::gaussian(forecast, std));
        }
        result
    }
}

// ---------------------------------------------------------------------------
// GARCH(1,1) volatility scaling
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Garch {
    pub omega: f64,
    pub alpha: f64,
    pub beta: f64,
    pub eps: f64,
    pub var: f64,
    pub last_y: f64,
    pub init: bool,
}

pub fn garch(omega: f64, alpha: f64, beta: f64, eps: f64) -> Transform {
    assert!(omega > 0.0 && alpha >= 0.0 && beta >= 0.0);
    Transform::Garch(Garch {
        omega,
        alpha,
        beta,
        eps,
        var: 0.0,
        last_y: 0.0,
        init: false,
    })
}

pub fn garch_default() -> Transform {
    garch(0.01, 0.1, 0.85, 1e-8)
}

impl Garch {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            let persist = self.alpha + self.beta;
            let var0 = if persist < 1.0 {
                self.omega / (1.0 - persist)
            } else {
                self.omega / self.eps
            };
            self.var = var0;
            self.last_y = y;
            return y / var0.sqrt().max(self.eps);
        }
        let var = self.omega + self.alpha * self.last_y * self.last_y + self.beta * self.var;
        let sigma = if var > self.eps * self.eps {
            var.sqrt()
        } else {
            self.eps
        };
        self.var = var;
        self.last_y = y;
        y / sigma
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let sigma = if self.var > 1e-16 {
            self.var.sqrt()
        } else {
            1e-8
        };
        dists.iter().map(|d| d.scale(sigma)).collect()
    }
}

// ---------------------------------------------------------------------------
// seasonal difference
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Seasonal {
    pub period: usize,
    pub buffer: Vec<f64>,
    pub init: bool,
}

pub fn seasonal_difference(period: usize) -> Transform {
    assert!(period >= 1);
    Transform::Seasonal(Seasonal {
        period,
        buffer: Vec::new(),
        init: false,
    })
}

impl Seasonal {
    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.buffer = vec![y];
            return 0.0;
        }
        let y_prime = if self.buffer.len() >= self.period {
            y - self.buffer[self.buffer.len() - self.period]
        } else {
            0.0
        };
        self.buffer.push(y);
        if self.buffer.len() > 2 * self.period {
            self.buffer.remove(0);
        }
        y_prime
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let buf = &self.buffer;
        let period = self.period;
        let mut recovered_means: Vec<f64> = Vec::new();
        let mut recovered_vars: Vec<f64> = Vec::new();
        let mut result = Vec::with_capacity(dists.len());
        for h in 0..dists.len() {
            let (anchor_mean, anchor_var);
            if h < period {
                let buf_idx = buf.len() as i64 - period as i64 + h as i64;
                anchor_mean = if buf_idx >= 0 && (buf_idx as usize) < buf.len() {
                    buf[buf_idx as usize]
                } else {
                    0.0
                };
                anchor_var = 0.0;
            } else {
                let lag_idx = h - period;
                anchor_mean = recovered_means[lag_idx];
                anchor_var = recovered_vars[lag_idx];
            }
            recovered_means.push(dists[h].mean() + anchor_mean);
            recovered_vars.push(dists[h].var() + anchor_var);
            if anchor_var > 0.0 {
                result.push(Dist::new(
                    dists[h]
                        .components
                        .iter()
                        .map(|&(w, m, s)| (w, m + anchor_mean, (s * s + anchor_var).sqrt()))
                        .collect(),
                ));
            } else {
                result.push(dists[h].shift(anchor_mean));
            }
        }
        result
    }
}


// ---------------------------------------------------------------------------
// seasonal anchor: hedged seasonal location (phase-EMA blended with naive)
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SeasonalAnchor {
    pub period: usize,
    pub alpha: f64,
    pub weight: f64,
    pub ema: Vec<Option<f64>>,
    pub buffer: Vec<f64>,
    pub n: usize,
    pub init: bool,
}

pub fn seasonal_anchor(period: usize, alpha: f64, weight: f64) -> Transform {
    assert!(period >= 1);
    assert!(0.0 < alpha && alpha < 1.0);
    assert!((0.0..=1.0).contains(&weight));
    Transform::SeasonalAnchor(SeasonalAnchor {
        period,
        alpha,
        weight,
        ema: vec![None; period],
        buffer: Vec::new(),
        n: 0,
        init: false,
    })
}

impl SeasonalAnchor {
    fn anchor_of(&self, ema: Option<f64>, snaive: f64) -> f64 {
        match ema {
            Some(e) => self.weight * e + (1.0 - self.weight) * snaive,
            None => snaive,
        }
    }

    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.buffer = vec![y];
            self.n = 1;
            return 0.0;
        }
        let p = self.n % self.period;
        let snaive = if self.buffer.len() >= self.period {
            self.buffer[self.buffer.len() - self.period]
        } else {
            *self.buffer.last().unwrap()
        };
        let y_prime = y - self.anchor_of(self.ema[p], snaive);
        self.ema[p] = Some(match self.ema[p] {
            Some(e) => e + self.alpha * (y - e),
            None => y,
        });
        self.buffer.push(y);
        if self.buffer.len() > 2 * self.period {
            self.buffer.remove(0);
        }
        self.n += 1;
        y_prime
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let buf = &self.buffer;
        let period = self.period;
        let mut recovered_means: Vec<f64> = Vec::new();
        let mut recovered_vars: Vec<f64> = Vec::new();
        let mut result = Vec::with_capacity(dists.len());
        for h in 0..dists.len() {
            let p = (self.n + h) % period;
            let (snaive, snaive_var);
            if h < period {
                let buf_idx = buf.len() as i64 - period as i64 + h as i64;
                snaive = if buf_idx >= 0 && (buf_idx as usize) < buf.len() {
                    buf[buf_idx as usize]
                } else {
                    *buf.last().unwrap_or(&0.0)
                };
                snaive_var = 0.0;
            } else {
                let lag_idx = h - period;
                snaive = recovered_means[lag_idx];
                snaive_var = recovered_vars[lag_idx];
            }
            let a_mean = self.anchor_of(self.ema[p], snaive);
            let a_var = (1.0 - self.weight) * (1.0 - self.weight) * snaive_var;
            recovered_means.push(dists[h].mean() + a_mean);
            recovered_vars.push(dists[h].var() + a_var);
            if a_var > 0.0 {
                result.push(Dist::new(
                    dists[h]
                        .components
                        .iter()
                        .map(|&(w, m, s)| (w, m + a_mean, (s * s + a_var).sqrt()))
                        .collect(),
                ));
            } else {
                result.push(dists[h].shift(a_mean));
            }
        }
        result
    }
}

// ---------------------------------------------------------------------------
// signed power transform
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Power {
    pub p: f64,
    pub inv_p: f64,
}

pub fn power_transform(p: f64) -> Transform {
    assert!(0.0 < p && p < 1.0);
    Transform::Power(Power { p, inv_p: 1.0 / p })
}

impl Power {
    fn forward(&mut self, y: f64) -> f64 {
        libm::copysign(libm::pow(y.abs(), self.p), y)
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let mut result = Vec::with_capacity(dists.len());
        for d in dists {
            let mut components = Vec::with_capacity(d.components.len());
            for &(w, mu, sigma) in &d.components {
                let orig_mean = libm::copysign(libm::pow(mu.abs(), self.inv_p), mu);
                let abs_mu = mu.abs();
                let deriv = if abs_mu > 1e-12 {
                    self.inv_p * libm::pow(abs_mu, self.inv_p - 1.0)
                } else {
                    self.inv_p
                };
                let orig_std = (sigma * deriv).max(1e-12);
                components.push((w, orig_mean, orig_std));
            }
            result.push(Dist::new(components));
        }
        result
    }
}

// ---------------------------------------------------------------------------
// Yeo-Johnson
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct YeoJohnson {
    pub l: f64,
}

pub fn yeo_johnson(lmbda: f64) -> Transform {
    Transform::YeoJohnson(YeoJohnson { l: lmbda })
}

impl YeoJohnson {
    fn fwd(&self, y: f64) -> f64 {
        let l = self.l;
        if y >= 0.0 {
            if l == 0.0 {
                libm::log1p(y)
            } else {
                (libm::pow(y + 1.0, l) - 1.0) / l
            }
        } else if l == 2.0 {
            -libm::log1p(-y)
        } else {
            -((libm::pow(-y + 1.0, 2.0 - l) - 1.0) / (2.0 - l))
        }
    }

    fn inv(&self, yp: f64) -> f64 {
        let l = self.l;
        if yp >= 0.0 {
            if l == 0.0 {
                return libm::expm1(yp.min(350.0));
            }
            let base = (l * yp + 1.0).max(1e-12);
            return libm::pow(base, 1.0 / l) - 1.0;
        }
        if l == 2.0 {
            return 1.0 - libm::exp((-yp).min(350.0));
        }
        let base = (-(2.0 - l) * yp + 1.0).max(1e-12);
        1.0 - libm::pow(base, 1.0 / (2.0 - l))
    }

    fn dinv(&self, yp: f64) -> f64 {
        let l = self.l;
        if yp >= 0.0 {
            if l == 0.0 {
                return libm::exp(yp.min(350.0));
            }
            let base = (l * yp + 1.0).max(1e-12);
            return libm::pow(base, 1.0 / l - 1.0);
        }
        if l == 2.0 {
            return libm::exp((-yp).min(350.0));
        }
        let base = (-(2.0 - l) * yp + 1.0).max(1e-12);
        libm::pow(base, 1.0 / (2.0 - l) - 1.0)
    }

    fn forward(&mut self, y: f64) -> f64 {
        self.fwd(y)
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let mut result = Vec::with_capacity(dists.len());
        for d in dists {
            let comps = d
                .components
                .iter()
                .map(|&(w, mu, sigma)| (w, self.inv(mu), (sigma * self.dinv(mu)).max(1e-12)))
                .collect();
            result.push(Dist::new(comps));
        }
        result
    }
}

// ---------------------------------------------------------------------------
// AR(p) with recursive least squares
// ---------------------------------------------------------------------------

fn mat_vec(m: &[f64], v: &[f64], n: usize) -> Vec<f64> {
    let mut result = vec![0.0; n];
    for i in 0..n {
        let mut s = 0.0;
        for j in 0..n {
            s += m[i * n + j] * v[j];
        }
        result[i] = s;
    }
    result
}

fn dot(a: &[f64], b: &[f64], n: usize) -> f64 {
    fsum((0..n).map(|i| a[i] * b[i]))
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Ar {
    pub p: usize,
    pub lam: f64,
    pub ridge: f64,
    pub decay: f64,
    pub buffer: Vec<f64>,
    pub phi: Vec<f64>,
    pub pmat: Vec<f64>,
    pub n: u64,
}

pub fn ar(order: usize, lam: f64, ridge: f64, decay: f64) -> Transform {
    assert!(order >= 1);
    assert!(0.0 < lam && lam <= 1.0);
    assert!(decay >= 0.0);
    let mut t = Ar {
        p: order,
        lam,
        ridge,
        decay,
        buffer: Vec::new(),
        phi: vec![0.0; order],
        pmat: Vec::new(),
        n: 0,
    };
    t.pmat = t.init_p();
    Transform::Ar(t)
}

pub fn ar_default(order: usize) -> Transform {
    ar(order, 0.99, 1.0, 0.0)
}

impl Ar {
    fn init_p(&self) -> Vec<f64> {
        let p = self.p;
        let mut pm = vec![0.0; p * p];
        for j in 0..p {
            pm[j * p + j] = if self.decay > 0.0 {
                self.ridge / libm::pow((j + 1) as f64, self.decay)
            } else {
                self.ridge
            };
        }
        pm
    }

    fn forward(&mut self, y: f64) -> f64 {
        let p = self.p;
        self.n += 1;
        let residual;
        if self.buffer.len() >= p {
            let bl = self.buffer.len();
            let x: Vec<f64> = (0..p).map(|i| self.buffer[bl - 1 - i]).collect();
            let prediction = fsum((0..p).map(|i| self.phi[i] * x[i]));
            residual = y - prediction;

            let px = mat_vec(&self.pmat, &x, p);
            let denom = self.lam + dot(&x, &px, p);
            if denom.abs() > 1e-15 {
                let kg: Vec<f64> = px.iter().map(|v| v / denom).collect();
                for i in 0..p {
                    self.phi[i] += kg[i] * residual;
                }
                for i in 0..p {
                    for j in 0..p {
                        self.pmat[i * p + j] = (self.pmat[i * p + j] - kg[i] * px[j]) / self.lam;
                    }
                }
                let bad = !self.pmat.iter().all(|v| v.is_finite())
                    || self.pmat.iter().fold(0.0_f64, |a, v| a.max(v.abs())) > 1e10;
                if bad {
                    self.pmat = self.init_p();
                }
            }
        } else {
            residual = y;
        }
        self.buffer.push(y);
        if self.buffer.len() > 2 * p + 10 {
            self.buffer.remove(0);
        }
        residual
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        ar_inverse(dists, &self.buffer, &self.phi, self.p)
    }
}

/// Shared AR-style inverse (used by Ar and GroupedAr).
fn ar_inverse(dists: &[Dist], buf: &[f64], phi: &[f64], p: usize) -> Vec<Dist> {
    let mut recovered_means: Vec<f64> = Vec::new();
    let mut recovered_vars: Vec<f64> = Vec::new();
    let mut result = Vec::with_capacity(dists.len());
    for h in 0..dists.len() {
        let mut ar_mean = 0.0;
        let mut ar_var = 0.0;
        for j in 0..p {
            let lag_h = h as i64 - j as i64 - 1;
            if lag_h < 0 {
                let buf_idx = buf.len() as i64 + lag_h;
                if buf_idx >= 0 && (buf_idx as usize) < buf.len() {
                    ar_mean += phi[j] * buf[buf_idx as usize];
                }
            } else if (lag_h as usize) < recovered_means.len() {
                ar_mean += phi[j] * recovered_means[lag_h as usize];
                ar_var += phi[j] * phi[j] * recovered_vars[lag_h as usize];
            }
        }
        let total_mean = dists[h].mean() + ar_mean;
        let total_var = dists[h].var() + ar_var;
        let total_std = if total_var > 0.0 {
            total_var.sqrt()
        } else {
            dists[h].std().max(1e-12)
        };
        recovered_means.push(total_mean);
        recovered_vars.push(total_var);
        result.push(Dist::gaussian(total_mean, total_std));
    }
    result
}

// ---------------------------------------------------------------------------
// grouped AR
// ---------------------------------------------------------------------------

fn build_groups(max_lag: usize) -> Vec<usize> {
    let mut groups = Vec::new();
    let mut g = 0usize;
    let mut size = 1usize;
    let mut assigned = 0usize;
    while assigned < max_lag {
        for _ in 0..size {
            if assigned >= max_lag {
                break;
            }
            groups.push(g);
            assigned += 1;
        }
        g += 1;
        size *= 2;
    }
    groups
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GroupedAr {
    pub max_lag: usize,
    pub lam: f64,
    pub ridge: f64,
    pub groups: Vec<usize>,
    pub n_groups: usize,
    pub buffer: Vec<f64>,
    pub theta: Vec<f64>,
    pub pmat: Vec<f64>,
    pub n: u64,
}

pub fn grouped_ar(max_lag: usize, lam: f64, ridge: f64) -> Transform {
    assert!(max_lag >= 1);
    assert!(0.0 < lam && lam <= 1.0);
    assert!(ridge > 0.0);
    let groups = build_groups(max_lag);
    let n_groups = groups.iter().copied().max().unwrap() + 1;
    let mut pmat = vec![0.0; n_groups * n_groups];
    for i in 0..n_groups {
        pmat[i * n_groups + i] = ridge;
    }
    Transform::GroupedAr(GroupedAr {
        max_lag,
        lam,
        ridge,
        groups,
        n_groups,
        buffer: Vec::new(),
        theta: vec![0.0; n_groups],
        pmat,
        n: 0,
    })
}

impl GroupedAr {
    fn forward(&mut self, y: f64) -> f64 {
        let ng = self.n_groups;
        self.n += 1;
        let residual;
        if self.buffer.len() >= self.max_lag {
            let bl = self.buffer.len();
            let mut x = vec![0.0; ng];
            for j in 0..self.max_lag {
                x[self.groups[j]] += self.buffer[bl - 1 - j];
            }
            let prediction = fsum((0..ng).map(|g| self.theta[g] * x[g]));
            residual = y - prediction;

            let px = mat_vec(&self.pmat, &x, ng);
            let denom = self.lam + dot(&x, &px, ng);
            if denom.abs() > 1e-15 {
                let kg: Vec<f64> = px.iter().map(|v| v / denom).collect();
                for g in 0..ng {
                    self.theta[g] += kg[g] * residual;
                }
                for i in 0..ng {
                    for j in 0..ng {
                        self.pmat[i * ng + j] = (self.pmat[i * ng + j] - kg[i] * px[j]) / self.lam;
                    }
                }
                let bad = !self.pmat.iter().all(|v| v.is_finite())
                    || self.pmat.iter().fold(0.0_f64, |a, v| a.max(v.abs())) > 1e10;
                if bad {
                    self.pmat = vec![0.0; ng * ng];
                    for i in 0..ng {
                        self.pmat[i * ng + i] = self.ridge;
                    }
                }
            }
        } else {
            residual = y;
        }
        self.buffer.push(y);
        if self.buffer.len() > self.max_lag + 10 {
            self.buffer.remove(0);
        }
        residual
    }

    fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        let phi: Vec<f64> = (0..self.max_lag)
            .map(|j| self.theta[self.groups[j]])
            .collect();
        ar_inverse(dists, &self.buffer, &phi, self.max_lag)
    }
}
