//! Online residual-transform wrapper: learn to reshape a skater's own errors.
//! Port of src/skaters/residual_transform.py.
//!
//! The resolved residual z_t = Phi^-1(F_{t-1}(y_t)) feeds a small online model
//! H_t for the next z, and the corrected predictive is
//! F~(y) = H(Phi^-1(F(y))). Models: m0 (identity), m1 (dynamic scale,
//! ell_{t+1} = a ell_t + c (z_t^2 - 1)), m2 (m1 plus a leverage term b z_t).

use crate::api::Forecaster;
use crate::homogenize::{
    clamp01, grid_crps, phi_inv, qgrid_p, std_cdf, LOG_SQRT2PI, QGRID_N, QGRID_W,
};
use crate::mathx::fsum;
use crate::tails::PDist;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::OnceLock;

const A_MIN: f64 = 0.0;
const A_MAX: f64 = 0.995;
const BC_MAX: f64 = 3.0;
const ELL_MIN: f64 = -20.0;
const ELL_MAX: f64 = 20.0;
const SENS_MAX: f64 = 50.0;
const GRAD_MAX: f64 = 3.0;
const RMS_RHO: f64 = 0.01;
const RMS_EPS: f64 = 1e-6;

fn clip(x: f64, lo: f64, hi: f64) -> f64 {
    if x < lo {
        lo
    } else if x > hi {
        hi
    } else {
        x
    }
}

/// The parameters of H_t: the identity family reads none, the Gaussian
/// shift-scale family reads `m` and `ell`. `a`, `c`, `b` are reported only.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ResidualTheta {
    pub m: f64,
    pub ell: f64,
    pub a: Option<f64>,
    pub c: Option<f64>,
    pub b: Option<f64>,
}

/// The base predictive reshaped by the residual model (Python `CorrectedDist`).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CorrectedDist {
    pub base: PDist,
    /// true: the identity family N(0, 1); false: N(m, exp(ell)).
    pub identity: bool,
    pub theta: ResidualTheta,
    #[serde(skip)]
    qgrid: OnceLock<Vec<f64>>,
}

impl CorrectedDist {
    pub fn new(base: PDist, identity: bool, theta: ResidualTheta) -> CorrectedDist {
        CorrectedDist {
            base,
            identity,
            theta,
            qgrid: OnceLock::new(),
        }
    }

    fn z(&self, y: f64) -> f64 {
        phi_inv(clamp01(self.base.cdf(y)))
    }

    fn fam_cdf(&self, z: f64) -> f64 {
        if self.identity {
            return std_cdf(z);
        }
        let sigma = libm::exp(0.5 * self.theta.ell);
        std_cdf((z - self.theta.m) / sigma)
    }

    fn fam_quantile(&self, p: f64) -> f64 {
        if self.identity {
            return phi_inv(p);
        }
        let sigma = libm::exp(0.5 * self.theta.ell);
        self.theta.m + sigma * phi_inv(p)
    }

    fn fam_logpdf(&self, z: f64) -> f64 {
        if self.identity {
            return -0.5 * z * z - LOG_SQRT2PI;
        }
        let sigma = libm::exp(0.5 * self.theta.ell);
        let zz = (z - self.theta.m) / sigma;
        -0.5 * zz * zz - libm::log(sigma) - LOG_SQRT2PI
    }

    pub fn cdf(&self, y: f64) -> f64 {
        self.fam_cdf(self.z(y))
    }

    pub fn logpdf(&self, y: f64) -> f64 {
        let z = self.z(y);
        self.base.logpdf(y) + self.fam_logpdf(z) + 0.5 * z * z + LOG_SQRT2PI
    }

    pub fn quantile(&self, p: f64) -> f64 {
        self.quantile_tol(p, 1e-9, 2100)
    }

    pub fn quantile_tol(&self, p: f64, tol: f64, max_iter: usize) -> f64 {
        assert!(0.0 < p && p < 1.0);
        let hp = self.fam_quantile(p);
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

/// The RTRL-lite online learner for m1/m2 (`b`, `eb`, `g2b` only for m2).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Learner {
    pub ell: f64,
    pub a: f64,
    pub c: f64,
    pub ea: f64,
    pub ec: f64,
    pub g2a: f64,
    pub g2c: f64,
    pub b: Option<f64>,
    pub eb: Option<f64>,
    pub g2b: Option<f64>,
}

impl Learner {
    pub fn new(learn_b: bool) -> Learner {
        Learner {
            ell: 0.0,
            a: 0.5,
            c: 0.05,
            ea: 0.0,
            ec: 0.0,
            g2a: 0.0,
            g2c: 0.0,
            b: if learn_b { Some(0.0) } else { None },
            eb: if learn_b { Some(0.0) } else { None },
            g2b: if learn_b { Some(0.0) } else { None },
        }
    }
}

fn rms_step(lr: f64, grad: f64, g2_prev: f64) -> (f64, f64) {
    let g2_new = (1.0 - RMS_RHO) * g2_prev + RMS_RHO * grad * grad;
    let step = lr * grad / (g2_new + RMS_EPS).sqrt();
    (step, g2_new)
}

fn update_learner(s: &Learner, z: f64, lr: f64, learn_b: bool) -> Learner {
    let ell_prev = s.ell;
    let (a, c) = (s.a, s.c);
    let b = s.b.unwrap_or(0.0);
    let grad_ell = clip(
        0.5 - 0.5 * z * z * libm::exp(-ell_prev),
        -GRAD_MAX,
        GRAD_MAX,
    );
    let (step_a, g2a_new) = rms_step(lr, grad_ell * s.ea, s.g2a);
    let (step_c, g2c_new) = rms_step(lr, grad_ell * s.ec, s.g2c);
    let a_new = clip(a - step_a, A_MIN, A_MAX);
    let c_new = clip(c - step_c, -BC_MAX, BC_MAX);
    let (b_new, g2b_new) = if learn_b {
        let (step_b, g2b_new) = rms_step(lr, grad_ell * s.eb.unwrap_or(0.0), s.g2b.unwrap_or(0.0));
        (clip(b - step_b, -BC_MAX, BC_MAX), g2b_new)
    } else {
        (0.0, 0.0)
    };
    let ea_new = clip(ell_prev + a_new * s.ea, -SENS_MAX, SENS_MAX);
    let ec_new = clip((z * z - 1.0) + a_new * s.ec, -SENS_MAX, SENS_MAX);
    let ell_new = clip(
        a_new * ell_prev + b_new * z + c_new * (z * z - 1.0),
        ELL_MIN,
        ELL_MAX,
    );
    let mut out = Learner {
        ell: ell_new,
        a: a_new,
        c: c_new,
        ea: ea_new,
        ec: ec_new,
        g2a: g2a_new,
        g2c: g2c_new,
        b: None,
        eb: None,
        g2b: None,
    };
    if learn_b {
        out.b = Some(b_new);
        out.eb = Some(clip(z + a_new * s.eb.unwrap_or(0.0), -SENS_MAX, SENS_MAX));
        out.g2b = Some(g2b_new);
    }
    out
}

pub(crate) fn theta_of(model: &str, learner: Option<&Learner>) -> ResidualTheta {
    match (model, learner) {
        ("m0", _) | (_, None) => ResidualTheta {
            m: 0.0,
            ell: 0.0,
            a: None,
            c: None,
            b: None,
        },
        (_, Some(l)) => ResidualTheta {
            m: 0.0,
            ell: l.ell,
            a: Some(l.a),
            c: Some(l.c),
            b: if model == "m2" { l.b } else { None },
        },
    }
}

/// The residual_transform wrapper (Python `residual_transform(base, model, lr, k=1)`).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResidualTransform {
    /// "m0", "m1" or "m2"
    pub model: String,
    pub lr: f64,
    pub inner: Forecaster,
    pub raw: Option<PDist>,
    pub z: Option<f64>,
    pub learner: Option<Learner>,
    pub theta: ResidualTheta,
}

/// `residual_transform(base, model="m2", lr=0.01, k=1)`; only k = 1 is supported.
pub fn residual_transform(inner: Forecaster, model: &str, lr: f64) -> Forecaster {
    assert!(
        matches!(model, "m0" | "m1" | "m2"),
        "model must be one of m0, m1, m2"
    );
    let mut r = ResidualTransform {
        model: model.to_string(),
        lr,
        inner,
        raw: None,
        z: None,
        learner: None,
        theta: theta_of("m0", None),
    };
    r.reset_own();
    Forecaster::Residual(Box::new(r))
}

impl ResidualTransform {
    pub(crate) fn reset_own(&mut self) {
        self.raw = None;
        self.z = None;
        self.learner = if self.model == "m0" {
            None
        } else {
            Some(Learner::new(self.model == "m2"))
        };
        self.theta = theta_of(&self.model, self.learner.as_ref());
    }

    pub fn step(&mut self, y: f64) -> Vec<PDist> {
        let learn_b = self.model == "m2";
        let mut z = None;
        if let Some(raw) = &self.raw {
            let zz = phi_inv(clamp01(raw.cdf(y)));
            z = Some(zz);
            if self.model != "m0" {
                let l = self.learner.get_or_insert_with(|| Learner::new(learn_b));
                *l = update_learner(l, zz, self.lr, learn_b);
            }
        }
        self.z = z;
        let dists = self.inner.step(y);
        let f_t = dists[0].clone();
        self.raw = Some(f_t.clone());
        self.theta = theta_of(&self.model, self.learner.as_ref());
        vec![PDist::Corrected(Box::new(CorrectedDist::new(
            f_t,
            self.model == "m0",
            self.theta.clone(),
        )))]
    }
}

/// Online EWMA diagnostics on a z stream: moments and the leverage statistic
/// L_k = E[z_t (z_{t+k}^2 - 1)] for k = 1..K (Python `ResidualDiagnostics`).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResidualDiagnostics {
    pub k: usize,
    alpha: f64,
    pub n: u64,
    pub m1: f64,
    pub m2: f64,
    pub m3: f64,
    pub m4: f64,
    buf: VecDeque<f64>,
    pub l: Vec<f64>,
    pub cross_sq: Vec<f64>,
}

impl ResidualDiagnostics {
    /// `ResidualDiagnostics(K=5, halflife=50.0)`.
    pub fn new(k: usize, halflife: f64) -> ResidualDiagnostics {
        ResidualDiagnostics {
            k,
            alpha: 1.0 - libm::pow(0.5, 1.0 / halflife),
            n: 0,
            m1: 0.0,
            m2: 0.0,
            m3: 0.0,
            m4: 0.0,
            buf: VecDeque::new(),
            l: vec![0.0; k],
            cross_sq: vec![0.0; k],
        }
    }

    pub fn update(&mut self, z: f64) {
        self.n += 1;
        let a = if self.alpha > 1.0 / self.n as f64 {
            self.alpha
        } else {
            1.0 / self.n as f64
        };
        let z2 = z * z;
        self.m1 = (1.0 - a) * self.m1 + a * z;
        self.m2 = (1.0 - a) * self.m2 + a * z2;
        self.m3 = (1.0 - a) * self.m3 + a * z * z2;
        self.m4 = (1.0 - a) * self.m4 + a * z2 * z2;
        for lag in 1..=self.k {
            if self.buf.len() >= lag {
                let z_lag = self.buf[self.buf.len() - lag];
                self.l[lag - 1] = (1.0 - a) * self.l[lag - 1] + a * z_lag * (z2 - 1.0);
                self.cross_sq[lag - 1] =
                    (1.0 - a) * self.cross_sq[lag - 1] + a * z_lag * z_lag * z2;
            }
        }
        self.buf.push_back(z);
        if self.buf.len() > self.k {
            self.buf.pop_front();
        }
    }
}
