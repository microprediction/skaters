//! GPD tail splice: the conditional tail fit, in the predictive itself.
//! Port of src/skaters/tails.py (Acklam phi_inv, censored-ML GPD fit,
//! SplicedDist, and the gpdtails wrapper).

use crate::dist::Dist;
use crate::mathx::{fsum, LOG_SQRT2PI, SQRT2, SQRT2PI};
use crate::skater::Sk;
use serde::{Deserialize, Serialize};

pub const EPS: f64 = 1e-12;
const REFIT_EVERY: u64 = 25;

// ---------------------------------------------------------------------------
// standard normal helpers (Acklam inverse: deterministic, portable)
// ---------------------------------------------------------------------------

pub fn phi(z: f64) -> f64 {
    0.5 * libm::erfc(-z / SQRT2)
}

pub fn phi_logpdf(z: f64) -> f64 {
    -0.5 * z * z - LOG_SQRT2PI
}

// Acklam constants, verbatim.
const ACK_A: [f64; 6] = [
    -3.969683028665376e+01,
    2.209460984245205e+02,
    -2.759285104469687e+02,
    1.383577518672690e+02,
    -3.066479806614716e+01,
    2.506628277459239e+00,
];
const ACK_B: [f64; 5] = [
    -5.447609879822406e+01,
    1.615858368580409e+02,
    -1.556989798598866e+02,
    6.680131188771972e+01,
    -1.328068155288572e+01,
];
const ACK_C: [f64; 6] = [
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e+00,
    -2.549732539343734e+00,
    4.374664141464968e+00,
    2.938163982698783e+00,
];
const ACK_D: [f64; 4] = [
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e+00,
    3.754408661907416e+00,
];

/// Acklam's rational approximation to the standard normal quantile,
/// polished with one Halley step (relative error < 1e-13).
pub fn phi_inv(p: f64) -> f64 {
    let p = p.max(EPS).min(1.0 - EPS);
    let x;
    if p < 0.02425 {
        let q = (-2.0 * libm::log(p)).sqrt();
        x = (((((ACK_C[0] * q + ACK_C[1]) * q + ACK_C[2]) * q + ACK_C[3]) * q + ACK_C[4]) * q
            + ACK_C[5])
            / ((((ACK_D[0] * q + ACK_D[1]) * q + ACK_D[2]) * q + ACK_D[3]) * q + 1.0);
    } else if p <= 0.97575 {
        let q = p - 0.5;
        let r = q * q;
        x = (((((ACK_A[0] * r + ACK_A[1]) * r + ACK_A[2]) * r + ACK_A[3]) * r + ACK_A[4]) * r
            + ACK_A[5])
            * q
            / (((((ACK_B[0] * r + ACK_B[1]) * r + ACK_B[2]) * r + ACK_B[3]) * r + ACK_B[4]) * r
                + 1.0);
    } else {
        let q = (-2.0 * libm::log(1.0 - p)).sqrt();
        x = -((((((ACK_C[0] * q + ACK_C[1]) * q + ACK_C[2]) * q + ACK_C[3]) * q + ACK_C[4]) * q
            + ACK_C[5])
            / ((((ACK_D[0] * q + ACK_D[1]) * q + ACK_D[2]) * q + ACK_D[3]) * q + 1.0));
    }
    let e = phi(x) - p;
    let u = e * SQRT2PI * libm::exp(0.5 * x * x);
    x - u / (1.0 + 0.5 * x * u)
}

// ---------------------------------------------------------------------------
// GPD helpers
// ---------------------------------------------------------------------------

fn gpd_logpdf(e: f64, gamma: f64, sigma: f64) -> f64 {
    if gamma.abs() < 1e-9 {
        return -libm::log(sigma) - e / sigma;
    }
    let arg = 1.0 + gamma * e / sigma;
    if arg <= 0.0 {
        return -745.0;
    }
    -libm::log(sigma) - (1.0 / gamma + 1.0) * libm::log(arg)
}

fn gpd_sf(e: f64, gamma: f64, sigma: f64) -> f64 {
    if e <= 0.0 {
        return 1.0;
    }
    if gamma.abs() < 1e-9 {
        return libm::exp(-e / sigma);
    }
    let arg = 1.0 + gamma * e / sigma;
    if arg <= 0.0 {
        return 0.0;
    }
    libm::pow(arg, -1.0 / gamma)
}

/// Excess e with survival probability p (inverse of gpd_sf).
fn gpd_isf(p: f64, gamma: f64, sigma: f64) -> f64 {
    let p = p.max(1e-300).min(1.0);
    if gamma.abs() < 1e-9 {
        return -sigma * libm::log(p);
    }
    sigma / gamma * (libm::pow(p, -gamma) - 1.0)
}

const TAU_GRID: [f64; 13] = [
    0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0, 3.0, 5.0, 8.0,
];

/// Censored-ML GPD fit (Grimshaw profile over a fixed tau grid).
fn fit_ml(exc: &[f64], s1: f64) -> (f64, f64) {
    let n = exc.len();
    let emean = s1 / n as f64;
    if n < 20 || emean <= 0.0 {
        return (0.0, emean.max(1e-12));
    }
    let emax = exc.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let mut best_g = 0.0;
    let mut best_s = emean.max(1e-12);
    let mut best_ll = -1e300;
    let mut taus: Vec<f64> = TAU_GRID.iter().map(|t| t / emean).collect();
    taus.push(-0.5 / emax);
    taus.push(-0.25 / emax);
    taus.push(-0.1 / emax);
    for tau in taus {
        if tau <= -1.0 / emax || tau.abs() < 1e-12 {
            continue;
        }
        let mut g = 0.0;
        for &e in exc {
            g += libm::log1p(tau * e);
        }
        g /= n as f64;
        if g <= 1e-9 {
            continue;
        }
        let sigma = g / tau;
        if sigma <= 0.0 {
            continue;
        }
        let ll = -(n as f64) * libm::log(sigma) - (1.0 + 1.0 / g) * n as f64 * g;
        if ll > best_ll {
            best_ll = ll;
            best_g = g;
            best_s = sigma;
        }
    }
    (best_g, best_s)
}

// ---------------------------------------------------------------------------
// the spliced predictive
// ---------------------------------------------------------------------------

/// A body Dist with GPD tails spliced in beyond frozen z-thresholds.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SplicedDist {
    pub body: Dist,
    pub t_lo: f64,
    pub t_up: f64,
    pub zeta_lo: f64,
    pub zeta_up: f64,
    pub g_lo: f64,
    pub s_lo: f64,
    pub g_up: f64,
    pub s_up: f64,
    plo: f64,
    pup: f64,
    c: f64,
}

const GRID_N: usize = 65;

impl SplicedDist {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        body: Dist,
        t_lo: f64,
        t_up: f64,
        zeta_lo: f64,
        zeta_up: f64,
        g_lo: f64,
        s_lo: f64,
        g_up: f64,
        s_up: f64,
    ) -> SplicedDist {
        let plo = phi(t_lo);
        let pup = phi(t_up);
        let interior = (pup - plo).max(1e-12);
        let c = (1.0 - zeta_lo - zeta_up).max(1e-12) / interior;
        SplicedDist {
            body,
            t_lo,
            t_up,
            zeta_lo,
            zeta_up,
            g_lo,
            s_lo,
            g_up,
            s_up,
            plo,
            pup,
            c,
        }
    }

    fn z(&self, x: f64) -> f64 {
        let u = self.body.cdf(x).max(EPS).min(1.0 - EPS);
        phi_inv(u)
    }

    pub fn cdf(&self, x: f64) -> f64 {
        let z = self.z(x);
        if z < self.t_lo {
            return self.zeta_lo * gpd_sf(self.t_lo - z, self.g_lo, self.s_lo);
        }
        if z > self.t_up {
            return 1.0 - self.zeta_up * gpd_sf(z - self.t_up, self.g_up, self.s_up);
        }
        self.zeta_lo + self.c * (phi(z) - self.plo)
    }

    pub fn logpdf(&self, x: f64) -> f64 {
        let base = self.body.logpdf(x);
        if !base.is_finite() {
            return base;
        }
        let z = self.z(x);
        let corr = if z < self.t_lo {
            libm::log(self.zeta_lo.max(1e-300)) + gpd_logpdf(self.t_lo - z, self.g_lo, self.s_lo)
                - phi_logpdf(z)
        } else if z > self.t_up {
            libm::log(self.zeta_up.max(1e-300)) + gpd_logpdf(z - self.t_up, self.g_up, self.s_up)
                - phi_logpdf(z)
        } else {
            libm::log(self.c)
        };
        base + corr
    }

    pub fn quantile(&self, p: f64) -> f64 {
        self.quantile_tol(p, 1e-9, 100)
    }

    pub fn quantile_tol(&self, p: f64, tol: f64, max_iter: usize) -> f64 {
        assert!(0.0 < p && p < 1.0);
        let z;
        if p < self.zeta_lo {
            z = self.t_lo - gpd_isf(p / self.zeta_lo, self.g_lo, self.s_lo);
        } else if p > 1.0 - self.zeta_up {
            z = self.t_up + gpd_isf((1.0 - p) / self.zeta_up, self.g_up, self.s_up);
        } else {
            let u = self.plo + (p - self.zeta_lo) / self.c;
            z = phi_inv(u.max(EPS).min(1.0 - EPS));
        }
        let ub = phi(z).max(EPS).min(1.0 - EPS);
        self.body.quantile_tol(ub, tol, max_iter)
    }

    /// Numeric moments and CRPS over a fixed 65-node quantile grid.
    fn qgrid(&self) -> Vec<f64> {
        (0..GRID_N)
            .map(|i| self.quantile((i as f64 + 0.5) / GRID_N as f64))
            .collect()
    }

    pub fn mean(&self) -> f64 {
        let q = self.qgrid();
        fsum(q.iter().copied()) / q.len() as f64
    }

    pub fn var(&self) -> f64 {
        let q = self.qgrid();
        let m = fsum(q.iter().copied()) / q.len() as f64;
        fsum(q.iter().map(|&x| (x - m) * (x - m))) / q.len() as f64
    }

    pub fn std(&self) -> f64 {
        self.var().sqrt()
    }

    pub fn crps(&self, x: f64) -> f64 {
        let q = self.qgrid();
        let n = q.len() as f64;
        let t1 = fsum(q.iter().map(|&v| (v - x).abs())) / n;
        let t2 = 2.0
            * fsum(
                q.iter()
                    .enumerate()
                    .map(|(i, &v)| v * (2.0 * (i as f64 + 0.5) / n - 1.0)),
            )
            / n;
        t1 - t2 * 0.5
    }
}

/// A predictive that is either a plain Gaussian mixture or a tail-spliced one.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum PDist {
    Mix(Dist),
    Spliced(SplicedDist),
}

impl PDist {
    pub fn mean(&self) -> f64 {
        match self {
            PDist::Mix(d) => d.mean(),
            PDist::Spliced(d) => d.mean(),
        }
    }
    pub fn std(&self) -> f64 {
        match self {
            PDist::Mix(d) => d.std(),
            PDist::Spliced(d) => d.std(),
        }
    }
    pub fn logpdf(&self, x: f64) -> f64 {
        match self {
            PDist::Mix(d) => d.logpdf(x),
            PDist::Spliced(d) => d.logpdf(x),
        }
    }
    pub fn cdf(&self, x: f64) -> f64 {
        match self {
            PDist::Mix(d) => d.cdf(x),
            PDist::Spliced(d) => d.cdf(x),
        }
    }
    pub fn quantile(&self, p: f64) -> f64 {
        match self {
            PDist::Mix(d) => d.quantile(p),
            PDist::Spliced(d) => d.quantile(p),
        }
    }
    pub fn crps(&self, x: f64) -> f64 {
        match self {
            PDist::Mix(d) => d.crps(x),
            PDist::Spliced(d) => d.crps(x),
        }
    }
}

// ---------------------------------------------------------------------------
// the wrapper
// ---------------------------------------------------------------------------

const GUARD_SF: f64 = 1e-3;
const ADAPT_AFTER: u64 = 10;

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct Tail {
    pub t: Option<f64>,
    pub exc: Vec<f64>,
    pub s1: f64,
    pub nx: u64,
    pub r: f64,
    pub g: f64,
    pub s: f64,
    pub since: u64,
    pub run: u64,
}

fn tail_new() -> Tail {
    Tail {
        t: None,
        exc: Vec::new(),
        s1: 0.0,
        nx: 0,
        r: 0.0,
        g: 0.0,
        s: 1.0,
        since: 0,
        run: 0,
    }
}

fn tail_add(tail: &mut Tail, e: f64, nexc: usize) {
    let mut e = e;
    if tail.exc.len() >= 20 {
        let cap = gpd_isf(GUARD_SF, tail.g, tail.s);
        if e > cap {
            if tail.run < ADAPT_AFTER {
                e = cap;
            }
            tail.run += 1;
        } else {
            tail.run = 0;
        }
    }
    tail.exc.push(e);
    tail.s1 += e;
    tail.nx += 1;
    if tail.exc.len() > nexc {
        tail.s1 -= tail.exc.remove(0);
    }
    tail.since += 1;
    if tail.since >= REFIT_EVERY || tail.exc.len() <= 25 {
        let (g, s) = fit_ml(&tail.exc, tail.s1);
        tail.g = g;
        tail.s = s;
        tail.since = 0;
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HorizonTail {
    pub up: Tail,
    pub lo: Tail,
    pub warm: Vec<f64>,
    pub n: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GpdTails {
    pub k: usize,
    pub level: f64,
    pub nexc: usize,
    pub warmup: usize,
    pub rate_alpha: f64,
    pub base: Sk,
    pub pending: Vec<Vec<Dist>>,
    pub tails: Vec<HorizonTail>,
}

pub fn gpdtails(base: Sk, k: usize, level: f64, nexc: usize, warmup: usize) -> GpdTails {
    assert!(k >= 1);
    assert!(0.5 < level && level < 1.0);
    assert!(nexc >= 50 && warmup >= 100);
    GpdTails {
        k,
        level,
        nexc,
        warmup,
        rate_alpha: 0.002,
        base,
        pending: Vec::new(),
        tails: (0..k)
            .map(|_| HorizonTail {
                up: tail_new(),
                lo: tail_new(),
                warm: Vec::new(),
                n: 0,
            })
            .collect(),
    }
}

impl GpdTails {
    pub fn step(&mut self, y: f64) -> Vec<PDist> {
        let k = self.k;
        let n = self.pending.len();
        for m in 1..=k {
            if m > n {
                continue;
            }
            let d = &self.pending[n - m][m - 1];
            let u = d.cdf(y);
            if !u.is_finite() {
                continue;
            }
            let z = phi_inv(u.max(EPS).min(1.0 - EPS));
            let th = &mut self.tails[m - 1];
            if th.up.t.is_none() {
                th.warm.push(z);
                if th.warm.len() >= self.warmup {
                    let mut w = th.warm.clone();
                    w.sort_by(|a, b| a.partial_cmp(b).unwrap());
                    let iu = ((self.level * w.len() as f64) as usize).min(w.len() - 1);
                    th.up.t = Some(w[iu]);
                    th.lo.t = Some(w[w.len() - 1 - iu]);
                    let (tu, tl) = (w[iu], w[w.len() - 1 - iu]);
                    for &x in &w {
                        if x > tu {
                            tail_add(&mut th.up, x - tu, self.nexc);
                        } else if x < tl {
                            tail_add(&mut th.lo, tl - x, self.nexc);
                        }
                    }
                    th.n = w.len() as i64;
                    th.up.r = th.up.nx as f64 / w.len() as f64;
                    th.lo.r = th.lo.nx as f64 / w.len() as f64;
                    th.warm.clear();
                }
            } else {
                th.n += 1;
                let tu = th.up.t.unwrap();
                let tl = th.lo.t.unwrap();
                th.up.r += self.rate_alpha * ((if z > tu { 1.0 } else { 0.0 }) - th.up.r);
                th.lo.r += self.rate_alpha * ((if z < tl { 1.0 } else { 0.0 }) - th.lo.r);
                if z > tu {
                    tail_add(&mut th.up, z - tu, self.nexc);
                } else if z < tl {
                    tail_add(&mut th.lo, tl - z, self.nexc);
                }
            }
        }

        let dists = self.base.step(y);
        self.pending.push(dists.clone());
        if self.pending.len() > k {
            self.pending.remove(0);
        }

        let mut out = Vec::with_capacity(k);
        for (m0, d) in dists.into_iter().enumerate() {
            let th = &self.tails[m0];
            if th.up.t.is_none() || th.up.exc.len() < 8 || th.lo.exc.len() < 8 || th.n <= 0 {
                out.push(PDist::Mix(d));
                continue;
            }
            out.push(PDist::Spliced(SplicedDist::new(
                d,
                th.lo.t.unwrap(),
                th.up.t.unwrap(),
                th.lo.r,
                th.up.r,
                th.lo.g,
                th.lo.s,
                th.up.g,
                th.up.s,
            )));
        }
        out
    }
}
