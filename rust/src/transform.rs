//! Invertible online transforms for conjugation. Port of src/skaters/transform.py.
//!
//! Each transform has `forward(&mut self, y) -> f64` (runs per observation) and
//! `inverse_k(&self, dists) -> Vec<Dist>` (maps k transformed-space predictions
//! back). Python initialises transform state lazily on the first call; here an
//! `init` flag reproduces the first-call special cases exactly.

use crate::dist::Dist;
use crate::mathx::fsum;
use crate::pushforward::{bisect_right, log_fwd_query, CoordMap, Pred};
use crate::tails::PDist;
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
    SeasonalScale(SeasonalScale),
    LogT(LogT),
    Gaussianize(Box<Gaussianize>),
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
            Transform::SeasonalScale(t) => t.forward(y),
            Transform::LogT(t) => t.forward(y),
            Transform::Gaussianize(t) => t.forward(y),
        }
    }

    /// Map k transformed-space mixtures back. A transform whose inverse is a
    /// pushforward (exact flags, log_transform) hands a mixture consumer its
    /// moment-matched components, as Python's ensembles read `.components`.
    pub fn inverse_k(&self, dists: &[Dist]) -> Vec<Dist> {
        self.inverse_k_g(dists)
    }

    /// Map k predictives (mixture, tail-spliced or pushforward) back.
    pub fn inverse_k_p(&self, dists: &[PDist]) -> Vec<PDist> {
        self.inverse_k_g(dists)
    }

    pub fn inverse_k_g<P: Pred>(&self, dists: &[P]) -> Vec<P> {
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
            Transform::SeasonalScale(t) => t.inverse_k(dists),
            Transform::LogT(t) => t.inverse_k(dists),
            Transform::Gaussianize(t) => t.inverse_k(dists),
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
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
            result.push(P::from_mix(Dist::gaussian(anchor + cumsum_mean, std)));
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        // Recovered horizons feed back through the same weights, so each carries a
        // row of responses to the future innovations and Var = sum_i c_i^2 var_i
        // (issue #255).
        let hn = dists.len();
        let mut buf = self.buffer.clone();
        let mut cbuf: Vec<Option<Vec<f64>>> = vec![None; buf.len()];
        let mut result = Vec::with_capacity(hn);
        for (h, d_in) in dists.iter().enumerate() {
            buf.push(0.0);
            cbuf.push(None);
            let n = buf.len();
            let mut shift = 0.0;
            let mut coef = vec![0.0; hn];
            coef[h] = 1.0;
            for j in 1..n.min(self.window) {
                shift -= self.w_fwd[j] * buf[n - 1 - j];
                if let Some(cj) = &cbuf[n - 1 - j] {
                    for i in 0..h {
                        coef[i] -= self.w_fwd[j] * cj[i];
                    }
                }
            }
            let recovered_mean = d_in.mean() + shift;
            buf[n - 1] = recovered_mean;
            let mut total_var = 0.0;
            for i in 0..=h {
                total_var += coef[i] * coef[i] * dists[i].var();
            }
            cbuf[n - 1] = Some(coef);
            let std = if total_var > 0.0 {
                total_var.sqrt()
            } else {
                d_in.std().max(1e-12)
            };
            result.push(P::from_mix(Dist::gaussian(recovered_mean, std)));
            if buf.len() > self.window {
                buf.remove(0);
                cbuf.remove(0);
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
        // Emit against the PRIOR state, so the forward map is the affine change
        // of coordinates z = (y - mu) / sigma that the inverse applies. Scaling
        // by the post-update std makes the emission self-normalized (bounded by
        // 1/sqrt(alpha)) and the affine inverse is then not its inverse.
        // Cold start: before the variance is informative, scale by the first
        // nonzero residual, so the first informative emission is +-1.
        let sigma = if self.var > self.eps * self.eps {
            self.var.sqrt()
        } else if diff.abs() > self.eps {
            diff.abs()
        } else {
            self.eps
        };
        let y_prime = diff / sigma;
        self.mu = mu + self.alpha * diff;
        self.var = (1.0 - self.alpha) * self.var + self.alpha * diff * diff;
        y_prime
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let level = self.level;
        let mut out = Vec::with_capacity(dists.len());
        // alpha^2 * sum_{i<h} var_i: the level's accumulated response (ETS(A,N,N), issue #254)
        let mut add = 0.0;
        for d in dists {
            if add > 0.0 {
                out.push(d.widen(level, add));
            } else {
                out.push(d.shift(level));
            }
            add += self.alpha * self.alpha * d.var();
        }
        out
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let (m, ylast) = (self.m, self.y);
        let phi = self.phi;
        let mut out = Vec::with_capacity(dists.len());
        for (h0, d) in dists.iter().enumerate() {
            let h = (h0 + 1) as f64;
            let center = m + libm::pow(phi, h) * (ylast - m);
            // Var = sum_{i<=h0} phi^{2(h0-i)} var_i, as a scale on this horizon's Dist
            // (issue #256); equals the old sqrt(sum_j phi^2j) for equal variances.
            let v_h = d.var();
            let g = if v_h > 0.0 {
                let mut tot = 0.0;
                for i in 0..=h0 {
                    tot += libm::pow(phi, (2 * (h0 - i)) as f64) * dists[i].var();
                }
                (tot / v_h).sqrt()
            } else if phi < 1.0 - 1e-9 {
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let mut result = Vec::with_capacity(dists.len());
        for (h, d) in dists.iter().enumerate() {
            let forecast = self.ses + (h + 1) as f64 * self.slope / 2.0 + d.mean();
            // SES: c_0 = 1, c_j = alpha; Var = sum_j c_j^2 var_{h-j} (issue #253).
            let mut total_var = 0.0;
            for j in 0..=h {
                let c = if j == 0 { 1.0 } else { self.alpha };
                total_var += c * c * dists[h - j].var();
            }
            let std = if total_var > 0.0 {
                total_var.sqrt()
            } else {
                d.std().max(1e-12)
            };
            result.push(P::from_mix(Dist::gaussian(forecast, std)));
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let anchor = self.last;
        let mu = self.mu;
        let rho = self.decay + self.alpha; // 1 - shrinkage: persistence of the drift estimate
        let mut result = Vec::with_capacity(dists.len());
        let mut cumsum_mean = 0.0;
        for (h, d) in dists.iter().enumerate() {
            cumsum_mean += d.mean();
            let total_mean = anchor + (h + 1) as f64 * mu + cumsum_mean;
            // c = 1 + alpha * sum_{m<h-i} rho^m: direct plus through the drift
            // estimate (issue #257).
            let mut total_var = 0.0;
            for i in 0..=h {
                let mut acc = 0.0;
                let mut f = 1.0;
                for _ in 0..(h - i) {
                    acc += f;
                    f *= rho;
                }
                let c = 1.0 + self.alpha * acc;
                total_var += c * c * dists[i].var();
            }
            let total_std = if total_var > 0.0 {
                total_var.sqrt()
            } else {
                d.std().max(1e-12)
            };
            result.push(P::from_mix(Dist::gaussian(total_mean, total_std)));
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let mut result = Vec::with_capacity(dists.len());
        for (h, d) in dists.iter().enumerate() {
            let forecast = self.level + (h + 1) as f64 * self.trend + d.mean();
            // ETS(A,A,N): c_0 = 1, c_j = alpha + alpha*beta*j; Var = sum_j c_j^2 var_{h-j} (issue #242).
            let mut total_var = 0.0;
            for j in 0..=h {
                let c = if j == 0 { 1.0 } else { self.alpha + self.alpha * self.beta * j as f64 };
                total_var += c * c * dists[h - j].var();
            }
            let std = if total_var > 0.0 {
                total_var.sqrt()
            } else {
                d.std().max(1e-12)
            };
            result.push(P::from_mix(Dist::gaussian(forecast, std)));
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
    pub mean_alpha: f64,
    pub eps: f64,
    pub var: f64,
    pub last_dev: f64,
    pub mu: f64,
    pub init: bool,
}

pub fn garch(omega: f64, alpha: f64, beta: f64, mean_alpha: f64, eps: f64) -> Transform {
    assert!(omega > 0.0 && alpha >= 0.0 && beta >= 0.0);
    Transform::Garch(Garch {
        omega,
        alpha,
        beta,
        mean_alpha,
        eps,
        var: 0.0,
        last_dev: 0.0,
        mu: 0.0,
        init: false,
    })
}

pub fn garch_default() -> Transform {
    garch(0.01, 0.1, 0.85, 0.05, 1e-8)
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
            self.last_dev = 0.0;
            self.mu = y;
            return 0.0;
        }
        // GARCH conditional variance of the DEVIATION from a running mean (not
        // the raw value): shift-invariant, so a level series does not report a
        // volatility of order |y|. On mean-zero returns mu stays ~0 and this
        // reduces to the original y/sigma.
        let dev = y - self.mu;
        let var = self.omega + self.alpha * self.last_dev * self.last_dev + self.beta * self.var;
        let sigma = if var > self.eps * self.eps {
            var.sqrt()
        } else {
            self.eps
        };
        self.var = var;
        self.last_dev = dev;
        self.mu += self.mean_alpha * dev;
        dev / sigma
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let sigma = if self.var > 1e-16 {
            self.var.sqrt()
        } else {
            1e-8
        };
        dists.iter().map(|d| d.affine(sigma, self.mu)).collect()
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
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
                result.push(dists[h].widen(anchor_mean, anchor_var));
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let buf = &self.buffer;
        let period = self.period;
        let hn = dists.len();
        let mut recovered_means: Vec<f64> = Vec::new();
        // Innovation-response rows of recovered values and of each phase's EMA: the
        // forward updates the EMA from recovered values too, so an anchor at
        // h >= period responds to the value one period back through (1 - weight)
        // and weight * alpha (issue #258).
        let mut rec_resp: Vec<Vec<f64>> = Vec::new();
        let mut ema_resp: Vec<Vec<f64>> = vec![vec![0.0; hn]; period];
        let mut result = Vec::with_capacity(hn);
        for h in 0..hn {
            let p = (self.n + h) % period;
            let (snaive, sn_resp): (f64, Option<Vec<f64>>);
            if h < period {
                let buf_idx = buf.len() as i64 - period as i64 + h as i64;
                snaive = if buf_idx >= 0 && (buf_idx as usize) < buf.len() {
                    buf[buf_idx as usize]
                } else {
                    *buf.last().unwrap_or(&0.0)
                };
                sn_resp = None;
            } else {
                let lag_idx = h - period;
                snaive = recovered_means[lag_idx];
                sn_resp = Some(rec_resp[lag_idx].clone());
            }
            let e = self.ema[p];
            let a_mean = self.anchor_of(e, snaive);
            let mut a_resp = vec![0.0; hn];
            for i in 0..h {
                let sn = match &sn_resp {
                    Some(v) => v[i],
                    None => 0.0,
                };
                a_resp[i] = match e {
                    Some(_) => self.weight * ema_resp[p][i] + (1.0 - self.weight) * sn,
                    None => sn,
                };
            }
            let mut a_var = 0.0;
            for i in 0..h {
                a_var += a_resp[i] * a_resp[i] * dists[i].var();
            }
            let mut r = a_resp.clone();
            r[h] = 1.0;
            recovered_means.push(dists[h].mean() + a_mean);
            rec_resp.push(r.clone());
            ema_resp[p] = match e {
                None => r.clone(),
                Some(_) => (0..hn)
                    .map(|i| (1.0 - self.alpha) * ema_resp[p][i] + self.alpha * r[i])
                    .collect(),
            };
            if a_var > 0.0 {
                result.push(dists[h].widen(a_mean, a_var));
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
    /// emit the exact pushforward instead of the delta method
    #[serde(default)]
    pub exact: bool,
}

pub fn power_transform(p: f64) -> Transform {
    power_transform_exact(p, false)
}

/// `power_transform(p, exact=...)`.
pub fn power_transform_exact(p: f64, exact: bool) -> Transform {
    assert!(0.0 < p && p < 1.0);
    Transform::Power(Power {
        p,
        inv_p: 1.0 / p,
        exact,
    })
}

impl Power {
    fn forward(&mut self, y: f64) -> f64 {
        libm::copysign(libm::pow(y.abs(), self.p), y)
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let map = CoordMap::Power { inv_p: self.inv_p };
        if self.exact {
            return dists.iter().map(|d| d.push(map.clone())).collect();
        }
        let mut result = Vec::with_capacity(dists.len());
        for d in dists {
            if !d.has_components() {
                // tail-spliced: exact pushforward
                result.push(d.push(map.clone()));
                continue;
            }
            let comps_in = d.comps();
            let mut components = Vec::with_capacity(comps_in.len());
            for &(w, mu, sigma) in comps_in.iter() {
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
            result.push(P::from_mix(Dist::new(components)));
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
    /// emit the exact pushforward instead of the delta method
    #[serde(default)]
    pub exact: bool,
}

pub fn yeo_johnson(lmbda: f64) -> Transform {
    yeo_johnson_exact(lmbda, false)
}

/// `yeo_johnson(lmbda, exact=...)`.
pub fn yeo_johnson_exact(lmbda: f64, exact: bool) -> Transform {
    Transform::YeoJohnson(YeoJohnson { l: lmbda, exact })
}

/// The Yeo-Johnson inverse at lambda (exp arguments clamped at 350).
pub(crate) fn yj_inv(l: f64, yp: f64) -> f64 {
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
        yj_inv(self.l, yp)
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

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let map = CoordMap::YeoJohnson { l: self.l };
        if self.exact {
            return dists.iter().map(|d| d.push(map.clone())).collect();
        }
        let mut result = Vec::with_capacity(dists.len());
        for d in dists {
            if !d.has_components() {
                // tail-spliced: exact pushforward
                result.push(d.push(map.clone()));
                continue;
            }
            let comps = d
                .comps()
                .iter()
                .map(|&(w, mu, sigma)| (w, self.inv(mu), (sigma * self.dinv(mu)).max(1e-12)))
                .collect();
            result.push(P::from_mix(Dist::new(comps)));
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
    /// Stationarity-projected coefficients, re-derived after every update.
    /// Used for BOTH the emitted residual and `inverse_k`'s reconstruction,
    /// so the two always agree on which predictor produced the residual
    /// (skaters#232) -- `phi` alone drives the raw RLS fit. Absent from
    /// checkpoints written before skaters#235: deserialises empty and is
    /// derived from `phi` on first use.
    #[serde(default)]
    pub phi_used: Vec<f64>,
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
        phi_used: vec![0.0; order],
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

            // Emitted residual uses `phi_used` -- the stationarity-projected
            // coefficients as of the end of the previous tick (derived now for
            // a pre-#235 checkpoint, which carries only `phi`).
            if self.phi_used.len() != p {
                self.phi_used = ar_stationary(&self.phi);
            }
            let prediction = fsum((0..p).map(|i| self.phi_used[i] * x[i]));
            residual = y - prediction;

            // RLS keeps fitting the RAW (unconstrained) least-squares problem
            // with its own prediction error.
            let raw_prediction = fsum((0..p).map(|i| self.phi[i] * x[i]));
            let raw_residual = y - raw_prediction;
            let px = mat_vec(&self.pmat, &x, p);
            let denom = self.lam + dot(&x, &px, p);
            if denom.abs() > 1e-15 {
                let kg: Vec<f64> = px.iter().map(|v| v / denom).collect();
                for i in 0..p {
                    self.phi[i] += kg[i] * raw_residual;
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
            // Re-project after every update so the next forward() call and
            // inverse_k always agree on the same constrained coefficients.
            self.phi_used = ar_stationary(&self.phi);
        } else {
            residual = y;
        }
        self.buffer.push(y);
        if self.buffer.len() > 2 * p + 10 {
            self.buffer.remove(0);
        }
        residual
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        if self.phi_used.len() != self.p {
            // pre-#235 checkpoint: the cache follows from the raw coefficients
            return ar_inverse(dists, &self.buffer, &ar_stationary(&self.phi), self.p);
        }
        ar_inverse(dists, &self.buffer, &self.phi_used, self.p)
    }
}

/// Spectral radius of the AR companion matrix (largest |characteristic root|):
/// the h-step forecast converges iff this is < 1. Closed form for p<=2, power
/// iteration otherwise.
fn ar_spectral_radius(phi: &[f64]) -> f64 {
    let p = phi.len();
    if p == 1 {
        return phi[0].abs();
    }
    if p == 2 {
        let (a, b) = (phi[0], phi[1]);
        let disc = a * a + 4.0 * b;
        if disc >= 0.0 {
            let r = disc.sqrt();
            return ((a + r) / 2.0).abs().max(((a - r) / 2.0).abs());
        }
        // libm::hypot, not f64::hypot: the std method calls the platform's own
        // libm (MSVC's differs from glibc's and Apple's) and is not guaranteed
        // bit-identical, which broke the cross-platform digest on Windows while
        // Linux, macOS and wasm agreed. Every other transcendental here already
        // routes through the libm crate for exactly this reason. Python's
        // math.hypot is also platform libm, so the 1e-6 parity tolerance covers
        // the reference comparison; bit-identity is a Rust-to-Rust claim.
        return libm::hypot(a / 2.0, (-disc).sqrt() / 2.0);
    }
    // Power iteration from a single seed can silently miss the true dominant
    // eigenvalue if that seed happens to be (near-)orthogonal to it. Two
    // seeds unlikely to BOTH align with a non-dominant eigenvector; take the
    // max (skaters#232 comment: phi=[3,-2,0,0,0] seeded at all-ones converges
    // to 1 instead of the true radius 2).
    let mut best = 0.0_f64;
    for seed in [
        vec![1.0_f64; p],
        (0..p)
            .map(|i| if i % 2 == 0 { 1.0 } else { -1.0 })
            .collect::<Vec<f64>>(),
    ] {
        let mut v = seed;
        let mut rho = 0.0;
        for _ in 0..60 {
            let mut nv = vec![0.0_f64; p];
            let mut s = 0.0;
            for j in 0..p {
                s += phi[j] * v[j];
            }
            nv[0] = s;
            for i in 1..p {
                nv[i] = v[i - 1];
            }
            let mut m = nv.iter().fold(0.0_f64, |acc, x| acc.max(x.abs()));
            if m == 0.0 {
                m = 1.0;
            }
            for x in nv.iter_mut() {
                *x /= m;
            }
            v = nv;
            rho = m;
        }
        best = best.max(rho);
    }
    best
}

/// Damp AR coefficients into the stationary region for forecasting. Scaling
/// phi_j by gamma^(j+1) scales every companion eigenvalue by gamma; a no-op when
/// already stationary.
fn ar_stationary(phi: &[f64]) -> Vec<f64> {
    let margin = 0.999;
    let rho = ar_spectral_radius(phi);
    if rho <= margin {
        return phi.to_vec();
    }
    let g = margin / rho;
    // libm::pow, not f64::powi: powi lowers to the llvm.powi intrinsic, whose
    // expansion is target dependent, so it is not bit-stable across platforms.
    // pow also matches the reference more closely, since Python's `g ** (j + 1)`
    // calls C pow rather than doing repeated multiplication.
    (0..phi.len())
        .map(|j| phi[j] * libm::pow(g, (j + 1) as f64))
        .collect()
}

/// Shared AR-style inverse (used by Ar and GroupedAr). `phi` must already be
/// the stationarity-projected coefficients the caller's forward() emitted
/// residuals under (skaters#232) -- not re-derived here from the raw fit.
fn ar_inverse<P: Pred>(dists: &[P], buf: &[f64], phi: &[f64], p: usize) -> Vec<P> {
    let n = dists.len();
    // Impulse responses psi_0..psi_{n-1}: psi_0 = 1, psi_i = sum_j phi_j psi_{i-j}.
    let mut psi = vec![0.0_f64; n];
    if n > 0 {
        psi[0] = 1.0;
    }
    for i in 1..n {
        let mut s = 0.0;
        for j in 0..p {
            if i as i64 - 1 - j as i64 >= 0 {
                s += phi[j] * psi[i - 1 - j];
            }
        }
        psi[i] = s;
    }
    let mut recovered_means: Vec<f64> = Vec::new();
    let mut result = Vec::with_capacity(n);
    for h in 0..n {
        let mut ar_mean = 0.0;
        for j in 0..p {
            let lag_h = h as i64 - j as i64 - 1;
            if lag_h < 0 {
                let buf_idx = buf.len() as i64 + lag_h;
                if buf_idx >= 0 && (buf_idx as usize) < buf.len() {
                    ar_mean += phi[j] * buf[buf_idx as usize];
                }
            } else if (lag_h as usize) < recovered_means.len() {
                ar_mean += phi[j] * recovered_means[lag_h as usize];
            }
        }
        let total_mean = dists[h].mean() + ar_mean;
        // Var(y_{t+h+1}) = sum_i psi_{h-i}^2 var_i (issue #245); same order as Python/JS.
        let mut total_var = 0.0;
        for i in 0..=h {
            total_var += psi[h - i] * psi[h - i] * dists[i].var();
        }
        let total_std = if total_var > 0.0 {
            total_var.sqrt()
        } else {
            dists[h].std().max(1e-12)
        };
        recovered_means.push(total_mean);
        result.push(P::from_mix(Dist::gaussian(total_mean, total_std)));
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
    /// Expanded, stationarity-projected per-lag coefficients, re-derived
    /// after every update (see `Ar::phi_used`). Absent from checkpoints
    /// written before skaters#235: deserialises empty, derived from `theta`.
    #[serde(default)]
    pub phi_used: Vec<f64>,
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
        phi_used: vec![0.0; max_lag],
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

            // Emitted residual uses the previous tick's stationarity-projected,
            // per-lag coefficients -- same fix as Ar (skaters#232).
            let lag_x: Vec<f64> = (0..self.max_lag).map(|j| self.buffer[bl - 1 - j]).collect();
            if self.phi_used.len() != self.max_lag {
                let raw: Vec<f64> = (0..self.max_lag).map(|j| self.theta[self.groups[j]]).collect();
                self.phi_used = ar_stationary(&raw);
            }
            let prediction = fsum((0..self.max_lag).map(|j| self.phi_used[j] * lag_x[j]));
            residual = y - prediction;

            // RLS keeps fitting the RAW group-level least-squares problem
            // with its own prediction error.
            let raw_prediction = fsum((0..ng).map(|g| self.theta[g] * x[g]));
            let raw_residual = y - raw_prediction;
            let px = mat_vec(&self.pmat, &x, ng);
            let denom = self.lam + dot(&x, &px, ng);
            if denom.abs() > 1e-15 {
                let kg: Vec<f64> = px.iter().map(|v| v / denom).collect();
                for g in 0..ng {
                    self.theta[g] += kg[g] * raw_residual;
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
            let raw_phi: Vec<f64> = (0..self.max_lag).map(|j| self.theta[self.groups[j]]).collect();
            self.phi_used = ar_stationary(&raw_phi);
        } else {
            residual = y;
        }
        self.buffer.push(y);
        if self.buffer.len() > self.max_lag + 10 {
            self.buffer.remove(0);
        }
        residual
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        // Same coefficients forward() already emitted residuals under
        // (skaters#232) -- maintained incrementally there, not re-derived here,
        // except for a pre-#235 checkpoint that has no cache yet.
        if self.phi_used.len() != self.max_lag {
            let raw: Vec<f64> = (0..self.max_lag).map(|j| self.theta[self.groups[j]]).collect();
            return ar_inverse(dists, &self.buffer, &ar_stationary(&raw), self.max_lag);
        }
        ar_inverse(dists, &self.buffer, &self.phi_used, self.max_lag)
    }
}

// ---------------------------------------------------------------------------
// seasonal scale: phase-indexed running standardization
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SeasonalScale {
    pub period: usize,
    pub alpha: f64,
    pub center: bool,
    pub eps: f64,
    pub init: bool,
    pub mu_g: f64,
    pub var_g: f64,
    pub mu: Vec<f64>,
    pub var: Vec<f64>,
    pub vis: Vec<u64>,
    pub n: u64,
}

/// `seasonal_scale(period, alpha, center, eps)`.
pub fn seasonal_scale(period: usize, alpha: f64, center: bool, eps: f64) -> Transform {
    assert!(period >= 1);
    assert!(0.0 < alpha && alpha < 1.0);
    Transform::SeasonalScale(SeasonalScale {
        period,
        alpha,
        center,
        eps,
        init: false,
        mu_g: 0.0,
        var_g: 0.0,
        mu: vec![0.0; period],
        var: vec![0.0; period],
        vis: vec![0; period],
        n: 0,
    })
}

const SEASONAL_SCALE_K0: f64 = 3.0;

impl SeasonalScale {
    fn a_g(&self) -> f64 {
        self.alpha / self.period as f64
    }

    /// Bias-corrected global variance (the slow EWMA starts from zero).
    fn vg(&self) -> f64 {
        let updates = self.n as i64 - 1;
        if updates <= 0 {
            return 0.0;
        }
        self.var_g / (1.0 - libm::pow(1.0 - self.a_g(), updates as f64))
    }

    /// Shrunk (mu, sigma) for phase p, blending variances in log space.
    fn phase_stats(&self, p: usize) -> (f64, f64) {
        let vis = self.vis[p] as f64;
        let w = vis / (vis + SEASONAL_SCALE_K0);
        let vp = self.var[p].max(self.eps * self.eps);
        let vg = self.vg().max(self.eps * self.eps);
        let var_eff = libm::exp(w * libm::log(vp) + (1.0 - w) * libm::log(vg));
        let mu_eff = if self.center {
            w * self.mu[p] + (1.0 - w) * self.mu_g
        } else {
            0.0
        };
        (mu_eff, var_eff.sqrt())
    }

    fn forward(&mut self, y: f64) -> f64 {
        if !self.init {
            self.init = true;
            self.mu_g = y;
            self.var_g = 0.0;
            self.n = 1;
            return 0.0;
        }
        let p = (self.n % self.period as u64) as usize;
        let (mu_eff, _) = self.phase_stats(p);
        let a_g = self.a_g();
        let dg = y - self.mu_g;
        self.mu_g += a_g * dg;
        self.var_g = (1.0 - a_g) * self.var_g + a_g * dg * dg;
        if self.vis[p] == 0 {
            self.mu[p] = y;
            self.var[p] = self.vg();
        } else {
            let dp = y - self.mu[p];
            self.mu[p] += self.alpha * dp;
            self.var[p] = (1.0 - self.alpha) * self.var[p] + self.alpha * dp * dp;
        }
        self.vis[p] += 1;
        self.n += 1;
        let (_, sigma) = self.phase_stats(p);
        (y - mu_eff) / sigma
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        (0..dists.len())
            .map(|h| {
                let p = ((self.n + h as u64) % self.period as u64) as usize;
                let (mu_eff, sigma) = self.phase_stats(p);
                dists[h].affine(sigma, mu_eff)
            })
            .collect()
    }
}

// ---------------------------------------------------------------------------
// log coordinate with a one-sided bound
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LogT {
    pub b: f64,
    /// +1 for a lower bound, -1 for an upper bound
    pub direction: f64,
}

/// `log_transform(lower=..., upper=...)`: give one bound; neither means lower = 0.
pub fn log_transform(lower: Option<f64>, upper: Option<f64>) -> Transform {
    assert!(
        !(lower.is_some() && upper.is_some()),
        "log_transform takes one bound: lower or upper"
    );
    let b = upper.unwrap_or(lower.unwrap_or(0.0));
    assert!(b.is_finite(), "log_transform needs a finite bound");
    let direction = if upper.is_some() { -1.0 } else { 1.0 };
    Transform::LogT(LogT { b, direction })
}

impl LogT {
    fn forward(&mut self, y: f64) -> f64 {
        if !y.is_finite() {
            return y; // missing: passes through for the inner skater
        }
        let z = log_fwd_query(self.b, self.direction, y);
        if z == -self.direction * f64::INFINITY {
            let label = if self.direction < 0.0 { "upper" } else { "lower" };
            panic!("log_transform: observation {y} must lie inside {label}={}", self.b);
        }
        z
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let map = CoordMap::Log {
            b: self.b,
            direction: self.direction,
        };
        dists.iter().map(|d| d.push_analytic(map.clone())).collect()
    }
}

// ---------------------------------------------------------------------------
// empirical Gaussianization
// ---------------------------------------------------------------------------

/// The standard normal quantile by Wichura's AS241, as CPython's
/// `statistics.NormalDist().inv_cdf`.
pub fn normal_inv_cdf(p: f64) -> f64 {
    assert!(p > 0.0 && p < 1.0, "p must be in the range 0.0 < p < 1.0");
    let q = p - 0.5;
    if q.abs() <= 0.425 {
        let r = 0.180625 - q * q;
        let num = (((((((2.5090809287301226727e+3 * r + 3.3430575583588128105e+4) * r
            + 6.7265770927008700853e+4)
            * r
            + 4.5921953931549871457e+4)
            * r
            + 1.3731693765509461125e+4)
            * r
            + 1.9715909503065514427e+3)
            * r
            + 1.3314166789178437745e+2)
            * r
            + 3.3871328727963666080e+0)
            * q;
        let den = ((((((5.2264952788528545610e+3 * r + 2.8729085735721942674e+4) * r
            + 3.9307895800092710610e+4)
            * r
            + 2.1213794301586595867e+4)
            * r
            + 5.3941960214247511077e+3)
            * r
            + 6.8718700749205790830e+2)
            * r
            + 4.2313330701600911252e+1)
            * r
            + 1.0;
        return 0.0 + num / den;
    }
    let mut r = if q <= 0.0 { p } else { 1.0 - p };
    r = libm::sqrt(-libm::log(r));
    let (num, den);
    if r <= 5.0 {
        r -= 1.6;
        num = ((((((7.74545014278341407640e-4 * r + 2.27238449892691845833e-2) * r
            + 2.41780725177450611770e-1)
            * r
            + 1.27045825245236838258e+0)
            * r
            + 3.64784832476320460504e+0)
            * r
            + 5.76949722146069140550e+0)
            * r
            + 4.63033784615654529590e+0)
            * r
            + 1.42343711074968357734e+0;
        den = ((((((1.05075007164441684324e-9 * r + 5.47593808499534494600e-4) * r
            + 1.51986665636164571966e-2)
            * r
            + 1.48103976427480074590e-1)
            * r
            + 6.89767334985100004550e-1)
            * r
            + 1.67638483018380384940e+0)
            * r
            + 2.05319162663775882187e+0)
            * r
            + 1.0;
    } else {
        r -= 5.0;
        num = ((((((2.01033439929228813265e-7 * r + 2.71155556874348757815e-5) * r
            + 1.24266094738807843860e-3)
            * r
            + 2.65321895265761230930e-2)
            * r
            + 2.96560571828504891230e-1)
            * r
            + 1.78482653991729133580e+0)
            * r
            + 5.46378491116411436990e+0)
            * r
            + 6.65790464350110377720e+0;
        den = ((((((2.04426310338993978564e-15 * r + 1.42151175831644588870e-7) * r
            + 1.84631831751005468180e-5)
            * r
            + 7.86869131145613259100e-4)
            * r
            + 1.48753612908506148525e-2)
            * r
            + 1.36929880922735805310e-1)
            * r
            + 5.99832206555887937690e-1)
            * r
            + 1.0;
    }
    let mut x = num / den;
    if q < 0.0 {
        x = -x;
    }
    0.0 + x
}

fn herm(s: f64, dx: f64, v0: f64, v1: f64, t0: f64, t1: f64) -> f64 {
    let s2 = s * s;
    let s3 = s2 * s;
    v0 * (2.0 * s3 - 3.0 * s2 + 1.0)
        + dx * t0 * (s3 - 2.0 * s2 + s)
        + v1 * (-2.0 * s3 + 3.0 * s2)
        + dx * t1 * (s3 - s2)
}

fn herm_ds(s: f64, dx: f64, v0: f64, v1: f64, t0: f64, t1: f64) -> f64 {
    let s2 = s * s;
    v0 * (6.0 * s2 - 6.0 * s)
        + dx * t0 * (3.0 * s2 - 4.0 * s + 1.0)
        + v1 * (-6.0 * s2 + 6.0 * s)
        + dx * t1 * (3.0 * s2 - 2.0 * s)
}

fn gaussianize_fwd(y: f64, cs: &[f64], zs: &[f64], ts: Option<&[f64]>) -> f64 {
    let k = cs.len();
    if y <= cs[0] {
        let s0 = match ts {
            Some(t) => t[0],
            None => (zs[1] - zs[0]) / (cs[1] - cs[0]),
        };
        return zs[0] + s0 * (y - cs[0]);
    }
    if y >= cs[k - 1] {
        let s1 = match ts {
            Some(t) => t[k - 1],
            None => (zs[k - 1] - zs[k - 2]) / (cs[k - 1] - cs[k - 2]),
        };
        return zs[k - 1] + s1 * (y - cs[k - 1]);
    }
    let i = bisect_right(cs, y) - 1;
    match ts {
        None => zs[i] + (zs[i + 1] - zs[i]) * (y - cs[i]) / (cs[i + 1] - cs[i]),
        Some(t) => {
            let dx = cs[i + 1] - cs[i];
            herm((y - cs[i]) / dx, dx, zs[i], zs[i + 1], t[i], t[i + 1])
        }
    }
}

/// gaussianize's inverse map on its knots (z -> y).
pub(crate) fn gaussianize_inv(z: f64, cs: &[f64], zs: &[f64], ts: Option<&[f64]>) -> f64 {
    let k = cs.len();
    if z <= zs[0] {
        let s0 = match ts {
            Some(t) => t[0],
            None => (zs[1] - zs[0]) / (cs[1] - cs[0]),
        };
        return cs[0] + (z - zs[0]) / s0.max(1e-12);
    }
    if z >= zs[k - 1] {
        let s1 = match ts {
            Some(t) => t[k - 1],
            None => (zs[k - 1] - zs[k - 2]) / (cs[k - 1] - cs[k - 2]),
        };
        return cs[k - 1] + (z - zs[k - 1]) / s1.max(1e-12);
    }
    let i = bisect_right(zs, z) - 1;
    match ts {
        None => cs[i] + (cs[i + 1] - cs[i]) * (z - zs[i]) / (zs[i + 1] - zs[i]),
        Some(t) => {
            let dx = cs[i + 1] - cs[i];
            let mut s = (z - zs[i]) / (zs[i + 1] - zs[i]);
            for _ in 0..6 {
                let d = herm_ds(s, dx, zs[i], zs[i + 1], t[i], t[i + 1]);
                if d <= 1e-14 {
                    break;
                }
                s -= (herm(s, dx, zs[i], zs[i + 1], t[i], t[i + 1]) - z) / d;
                s = if s < 0.0 {
                    0.0
                } else if s > 1.0 {
                    1.0
                } else {
                    s
                };
            }
            cs[i] + s * dx
        }
    }
}

/// Knots of the empirical map: centers, levels, optional cubic tangents.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Knots {
    pub cs: Vec<f64>,
    pub zs: Vec<f64>,
    pub ts: Option<Vec<f64>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Gaussianize {
    pub max_knots: usize,
    pub warmup: usize,
    pub n_particles: usize,
    pub smooth: bool,
    pub slope_cap: f64,
    pub z_max: f64,
    /// "move", "delete" or "emin"
    pub guard: String,
    pub buf: Vec<f64>,
    pub n: usize,
    pub mu: f64,
    pub m2: f64,
    pub knots: Option<Knots>,
}

/// `gaussianize(max_knots, warmup, n_particles, smooth, slope_cap, z_max, guard)`.
pub fn gaussianize(
    max_knots: usize,
    warmup: usize,
    n_particles: usize,
    smooth: bool,
    slope_cap: f64,
    z_max: f64,
    guard: &str,
) -> Transform {
    Transform::Gaussianize(Box::new(Gaussianize {
        max_knots,
        warmup,
        n_particles,
        smooth,
        slope_cap,
        z_max,
        guard: guard.to_string(),
        buf: Vec::new(),
        n: 0,
        mu: 0.0,
        m2: 0.0,
        knots: None,
    }))
}

/// Python's defaults: gaussianize().
pub fn gaussianize_default() -> Transform {
    gaussianize(39, 30, 9, false, 20.0, 8.0, "move")
}

impl Gaussianize {
    fn cap_of(&self, ys: &[f64], zs: &[f64]) -> Option<f64> {
        let (i1, i3) = (ys.len() / 4, 3 * ys.len() / 4);
        if i3 <= i1 || zs[i3] <= zs[i1] {
            return None;
        }
        let cap = self.slope_cap * (ys[i3] - ys[i1]) / (zs[i3] - zs[i1]);
        if cap <= 0.0 {
            return None;
        }
        Some(cap)
    }

    fn prune_slopes(&self, ys: Vec<f64>, zs: Vec<f64>) -> (Vec<f64>, Vec<f64>) {
        let Some(cap) = self.cap_of(&ys, &zs) else {
            return (ys, zs);
        };
        let c = ys.len() / 2;
        let mut keep = vec![c];
        for i in c + 1..ys.len() {
            let j = *keep.last().unwrap();
            if (ys[i] - ys[j]) / (zs[i] - zs[j]) <= cap {
                keep.push(i);
            }
        }
        for i in (0..c).rev() {
            let j = *keep.iter().min().unwrap();
            if (ys[j] - ys[i]) / (zs[j] - zs[i]) <= cap {
                keep.push(i);
            }
        }
        keep.sort_unstable();
        if keep.len() < 2 {
            return (ys, zs);
        }
        (
            keep.iter().map(|&i| ys[i]).collect(),
            keep.iter().map(|&i| zs[i]).collect(),
        )
    }

    fn emin_knots(&self, buf: &[f64], ys: Vec<f64>, zs: Vec<f64>, idxs: &[usize]) -> (Vec<f64>, Vec<f64>) {
        let Some(cap) = self.cap_of(&ys, &zs) else {
            return (ys, zs);
        };
        let (nb, kk) = (buf.len(), ys.len());
        let dz: Vec<f64> = (0..kk - 1).map(|j| zs[j + 1] - zs[j]).collect();
        let corridor = |e: usize| -> Option<(Vec<f64>, Vec<f64>)> {
            let lo: Vec<f64> = (0..kk).map(|j| buf[idxs[j].saturating_sub(e)]).collect();
            let hi: Vec<f64> = (0..kk).map(|j| buf[(idxs[j] + e).min(nb - 1)]).collect();
            let mut u = vec![0.0; kk];
            u[kk - 1] = hi[kk - 1];
            for j in (0..kk - 1).rev() {
                u[j] = hi[j].min(u[j + 1]);
            }
            let mut db = vec![0.0; kk];
            db[kk - 1] = lo[kk - 1];
            for j in (0..kk - 1).rev() {
                db[j] = lo[j].max(db[j + 1] - cap * dz[j]);
            }
            let mut l = vec![0.0; kk];
            l[0] = db[0];
            for j in 1..kk {
                l[j] = db[j].max(l[j - 1]);
            }
            if (0..kk).any(|j| l[j] > u[j]) {
                return None;
            }
            Some((l, u))
        };
        if corridor(0).is_some() {
            return (ys, zs);
        }
        let (mut lo_e, mut hi_e) = (0usize, nb);
        while hi_e - lo_e > 1 {
            let mid = (lo_e + hi_e) / 2;
            if corridor(mid).is_some() {
                hi_e = mid;
            } else {
                lo_e = mid;
            }
        }
        let Some((l, u)) = corridor(hi_e) else {
            return (ys, zs);
        };
        let mut w = vec![0.0; kk];
        w[0] = l[0].max(ys[0].min(u[0]));
        for j in 1..kk {
            let a_j = l[j].max(w[j - 1]);
            let b_j = u[j].min(w[j - 1] + cap * dz[j - 1]);
            w[j] = a_j.max(ys[j].min(b_j));
        }
        let (mut ks, mut kz) = (vec![w[0]], vec![zs[0]]);
        for j in 1..kk {
            if w[j] > *ks.last().unwrap() {
                ks.push(w[j]);
                kz.push(zs[j]);
            }
        }
        (ks, kz)
    }

    fn cap_slopes(&self, ys: &mut [f64], zs: &[f64]) {
        let Some(cap) = self.cap_of(ys, zs) else {
            return;
        };
        let c = ys.len() / 2;
        for i in c + 1..ys.len() {
            ys[i] = ys[i].min(ys[i - 1] + cap * (zs[i] - zs[i - 1]));
        }
        for i in (0..c).rev() {
            ys[i] = ys[i].max(ys[i + 1] - cap * (zs[i + 1] - zs[i]));
        }
    }

    fn tangents(xs: &[f64], vs: &[f64]) -> Vec<f64> {
        let d: Vec<f64> = (0..xs.len() - 1)
            .map(|i| (vs[i + 1] - vs[i]) / (xs[i + 1] - xs[i]))
            .collect();
        let mut t = vec![d[0]];
        for i in 1..xs.len() - 1 {
            let (a, b) = (d[i - 1], d[i]);
            t.push(if a * b > 0.0 { 2.0 * a * b / (a + b) } else { 0.0 });
        }
        t.push(*d.last().unwrap());
        t
    }

    fn build(&self) -> Option<Knots> {
        let buf = &self.buf;
        let n = buf.len();
        let m = self.max_knots.min(n);
        let mut cs: Vec<f64> = Vec::new();
        let mut idxs: Vec<usize> = Vec::new();
        for i in 0..m {
            let idx = ((i as f64 + 0.5) * n as f64 / m as f64) as usize;
            let y = buf[idx];
            if !cs.is_empty() && y <= *cs.last().unwrap() {
                continue;
            }
            cs.push(y);
            idxs.push(idx);
        }
        if cs.len() < 2 {
            return None;
        }
        if !self.smooth {
            let zs: Vec<f64> = idxs
                .iter()
                .map(|&idx| normal_inv_cdf((idx + 1) as f64 / (n + 1) as f64))
                .collect();
            let (cs, zs) = match self.guard.as_str() {
                "delete" => self.prune_slopes(cs, zs),
                "emin" => self.emin_knots(buf, cs, zs, &idxs),
                _ => {
                    let mut cs = cs;
                    self.cap_slopes(&mut cs, &zs);
                    (cs, zs)
                }
            };
            return Some(Knots { cs, zs, ts: None });
        }
        // kernel-smoothed CDF on the sketch, Silverman bandwidth
        let mm = cs.len();
        let (i1, i3) = (mm / 4, 3 * mm / 4);
        let iqr = cs[i3] - cs[i1];
        let mean = fsum(cs.iter().copied()) / mm as f64;
        let sd = (fsum(cs.iter().map(|&c| (c - mean) * (c - mean))) / mm as f64).sqrt();
        let mut scale = if iqr > 0.0 { sd.min(iqr / 1.34) } else { sd };
        if scale <= 0.0 {
            scale = (cs[mm - 1] - cs[0]).abs().max(1e-8);
        }
        let h = (0.9 * scale * libm::pow(n as f64, -0.2)).max(1e-12);
        let r = 8.0 * h;
        let sq2 = std::f64::consts::SQRT_2;
        let mut zs = Vec::with_capacity(mm);
        let (mut lo, mut hi) = (0usize, 0usize);
        for &c in &cs {
            while lo < mm && cs[lo] < c - r {
                lo += 1;
            }
            while hi < mm && cs[hi] <= c + r {
                hi += 1;
            }
            let f = (lo as f64
                + fsum((lo..hi).map(|j| 0.5 * (1.0 + libm::erf((c - cs[j]) / (sq2 * h))))))
                / mm as f64;
            zs.push(normal_inv_cdf((1.0 + n as f64 * f) / (n as f64 + 2.0)));
        }
        let (mut cs2, mut zs2) = (vec![cs[0]], vec![zs[0]]);
        for i in 1..mm {
            if zs[i] > *zs2.last().unwrap() + 1e-12 {
                cs2.push(cs[i]);
                zs2.push(zs[i]);
            }
        }
        if cs2.len() < 2 {
            return None;
        }
        self.cap_slopes(&mut cs2, &zs2);
        let ts = Self::tangents(&cs2, &zs2);
        Some(Knots {
            cs: cs2,
            zs: zs2,
            ts: Some(ts),
        })
    }

    fn moments(&self) -> (f64, f64) {
        let var = if self.n > 2 {
            self.m2 / (self.n - 1) as f64
        } else {
            0.0
        };
        let sigma = if var > 0.0 { var.sqrt() } else { 1e-8 };
        (self.mu, sigma)
    }

    fn forward(&mut self, y: f64) -> f64 {
        let mut z = match &self.knots {
            Some(k) => gaussianize_fwd(y, &k.cs, &k.zs, k.ts.as_deref()),
            None => {
                let (mu, mut sigma) = self.moments();
                if sigma <= 1e-8 {
                    sigma = (y - mu).abs().max(1e-8);
                }
                if self.n > 0 {
                    (y - mu) / sigma
                } else {
                    0.0
                }
            }
        };
        z = (-self.z_max).max(self.z_max.min(z));
        let at = bisect_right(&self.buf, y);
        self.buf.insert(at, y);
        let n = self.n + 1;
        let d0 = y - self.mu;
        let mu = self.mu + d0 / n as f64;
        self.m2 += d0 * (y - mu);
        self.n = n;
        self.mu = mu;
        self.knots = if n >= self.warmup { self.build() } else { None };
        z
    }

    fn inverse_k<P: Pred>(&self, dists: &[P]) -> Vec<P> {
        let Some(k) = &self.knots else {
            let (mu, sigma) = self.moments();
            return dists.iter().map(|d| d.affine(sigma, mu)).collect();
        };
        let jn = self.n_particles;
        let mids: Vec<f64> = (0..jn).map(|j| normal_inv_cdf((j as f64 + 0.5) / jn as f64)).collect();
        let edges: Vec<f64> = (1..jn).map(|j| normal_inv_cdf(j as f64 / jn as f64)).collect();
        let ts = k.ts.as_deref();
        let inv = |z: f64| gaussianize_inv(z, &k.cs, &k.zs, ts);
        let mut result = Vec::with_capacity(dists.len());
        for d in dists {
            if !d.has_components() {
                // tail-spliced: exact pushforward
                result.push(d.push(CoordMap::Gaussianize {
                    cs: k.cs.clone(),
                    zs: k.zs.clone(),
                    ts: k.ts.clone(),
                }));
                continue;
            }
            let mut comps = Vec::new();
            for &(w, mu, sig) in d.comps().iter() {
                let pts: Vec<f64> = mids.iter().map(|&q| inv(mu + sig * q)).collect();
                let eds: Vec<f64> = edges.iter().map(|&e| inv(mu + sig * e)).collect();
                for j in 0..jn {
                    let lo = if j > 0 { Some(eds[j - 1]) } else { None };
                    let hi = if j < jn - 1 { Some(eds[j]) } else { None };
                    let std = match (lo, hi) {
                        (Some(l), Some(h)) => (h - l) / 2.0,
                        (None, Some(h)) => h - pts[j],
                        (Some(l), None) => pts[j] - l,
                        (None, None) => unreachable!(),
                    };
                    comps.push((w / jn as f64, pts[j], std.max(1e-9)));
                }
            }
            result.push(P::from_mix(Dist::new(comps).prune(12)));
        }
        result
    }
}
