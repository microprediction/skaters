//! Exact pushforward of a predictive through a monotone coordinate map.
//! Port of src/skaters/pushforward.py.
//!
//! `PushforwardDist` keeps the inner predictive in the transformed
//! z-coordinate and answers queries through the change of variables
//!
//! ```text
//! F_Y(y)      = F_Z(z(y))
//! log p_Y(y)  = log p_Z(z(y)) + log dz/dy
//! Q_Y(p)      = y(Q_Z(p))
//! ```
//!
//! Python carries the map as closures. Here it is data, a `CoordMap`, so a
//! predictive stays serde-serializable; each variant evaluates exactly the
//! closure Python builds for it, and `Affine` is the composition
//! `PushforwardDist.affine` builds.

use crate::dist::Dist;
use crate::mathx::fsum;
use crate::tails::PDist;
use serde::{Deserialize, Serialize};
use std::borrow::Cow;

const SQRT2: f64 = std::f64::consts::SQRT_2;
const SQRTPI: f64 = 1.772_453_850_905_516;

// 7-point Gauss-Hermite nodes/weights (physicists').
const GH7: [(f64, f64); 7] = [
    (-2.6519613568352334, 9.717812450995192e-04),
    (-1.6735516287674714, 5.451558281912703e-02),
    (-0.8162878828589647, 4.256072526101278e-01),
    (0.0, 8.102646175568073e-01),
    (0.8162878828589647, 4.256072526101278e-01),
    (1.6735516287674714, 5.451558281912703e-02),
    (2.6519613568352334, 9.717812450995192e-04),
];

const RULE_N: usize = 257;

/// Fourth-power odds quantile rule: (midpoint, width) pairs.
fn quantile_rule() -> Vec<(f64, f64)> {
    let n = RULE_N;
    let edges: Vec<f64> = (0..=n)
        .map(|i| {
            let a = (i as f64).powi(4);
            let b = ((n - i) as f64).powi(4);
            a / (a + b)
        })
        .collect();
    (0..n)
        .map(|i| ((edges[i] + edges[i + 1]) * 0.5, edges[i + 1] - edges[i]))
        .collect()
}

/// `math.hypot(*xs)`: scaled sum of squares (agrees with CPython to ~1 ulp).
fn hypot_n(xs: &[f64]) -> f64 {
    let mut mx = 0.0_f64;
    for &x in xs {
        if x.is_infinite() {
            return f64::INFINITY;
        }
        if x.is_nan() {
            return f64::NAN;
        }
        mx = mx.max(x.abs());
    }
    if mx == 0.0 {
        return 0.0;
    }
    mx * fsum(xs.iter().map(|&x| (x / mx) * (x / mx))).sqrt()
}

fn bisect_left(xs: &[f64], x: f64) -> usize {
    let (mut lo, mut hi) = (0usize, xs.len());
    while lo < hi {
        let mid = (lo + hi) / 2;
        if xs[mid] < x {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    lo
}

pub(crate) fn bisect_right(xs: &[f64], x: f64) -> usize {
    let (mut lo, mut hi) = (0usize, xs.len());
    while lo < hi {
        let mid = (lo + hi) / 2;
        if x < xs[mid] {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    lo
}

/// Piecewise-linear with linear extrapolation from the end segments.
pub fn interp_table(x: f64, xs: &[f64], fs: &[f64]) -> f64 {
    let mut i = bisect_left(xs, x);
    if i == 0 {
        i = 1;
    } else if i >= xs.len() {
        i = xs.len() - 1;
    }
    let (x0, x1) = (xs[i - 1], xs[i]);
    fs[i - 1] + (fs[i] - fs[i - 1]) * (x - x0) / (x1 - x0)
}

/// (ys, zs) knots of a monotone map y = inv(z) on [z_lo, z_hi].
pub fn table_from_map(map: &CoordMap, z_lo: f64, z_hi: f64, nodes: usize) -> (Vec<f64>, Vec<f64>) {
    let z_hi = z_hi.max(z_lo + 1e-9);
    let step = (z_hi - z_lo) / nodes as f64;
    let mut ys: Vec<f64> = Vec::new();
    let mut zs: Vec<f64> = Vec::new();
    for j in 0..=nodes {
        let z = z_lo + step * j as f64;
        let y = map.inv(z);
        if ys.is_empty() || y > *ys.last().unwrap() {
            ys.push(y);
            zs.push(z);
        }
    }
    if ys.len() < 2 {
        let y0 = map.inv(z_lo);
        ys = vec![y0, y0 + 1e-9];
        zs = vec![z_lo, z_lo + 1e-9];
    }
    (ys, zs)
}

fn nextafter(x: f64, toward: f64) -> f64 {
    if x.is_nan() || toward.is_nan() {
        return f64::NAN;
    }
    if x == toward {
        return toward;
    }
    if x == 0.0 {
        let tiny = f64::from_bits(1);
        return if toward > 0.0 { tiny } else { -tiny };
    }
    let bits = x.to_bits();
    let up = (toward > x) == (x > 0.0);
    f64::from_bits(if up { bits + 1 } else { bits - 1 })
}

/// The coordinate maps the transforms push predictives through.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum CoordMap {
    /// signed power inverse: copysign(|z|^(1/p), z)
    Power { inv_p: f64 },
    /// Yeo-Johnson inverse at lambda
    YeoJohnson { l: f64 },
    /// gaussianize's inverse map on its knots
    Gaussianize {
        cs: Vec<f64>,
        zs: Vec<f64>,
        ts: Option<Vec<f64>>,
    },
    /// log coordinate with a one-sided bound (direction +1 lower, -1 upper)
    Log { b: f64, direction: f64 },
    /// a*Y + b of the base map, with z reflected by r = sign(a)
    Affine {
        a: f64,
        b: f64,
        r: f64,
        base: Box<CoordMap>,
    },
}

impl CoordMap {
    pub fn inv(&self, z: f64) -> f64 {
        match self {
            CoordMap::Power { inv_p } => libm::copysign(libm::pow(z.abs(), *inv_p), z),
            CoordMap::YeoJohnson { l } => crate::transform::yj_inv(*l, z),
            CoordMap::Gaussianize { cs, zs, ts } => {
                crate::transform::gaussianize_inv(z, cs, zs, ts.as_deref())
            }
            CoordMap::Log { b, direction } => {
                let y = log_inverse_at_scale(*b, *direction, z, 1.0);
                if y == *b {
                    nextafter(*b, direction * f64::INFINITY)
                } else {
                    y
                }
            }
            CoordMap::Affine { a, b, r, base } => a * base.inv(r * z) + b,
        }
    }

    pub fn has_fwd(&self) -> bool {
        match self {
            CoordMap::Log { .. } => true,
            CoordMap::Affine { base, .. } => base.has_fwd(),
            _ => false,
        }
    }

    pub fn fwd(&self, y: f64) -> f64 {
        match self {
            CoordMap::Log { b, direction } => log_fwd_query(*b, *direction, y),
            CoordMap::Affine { a, b, r, base } => r * base.fwd((y - b) / a),
            _ => unreachable!("map has no forward"),
        }
    }

    /// Analytic log(dz/dy) evaluated at z, when the map has one.
    pub fn log_jacobian(&self, z: f64) -> Option<f64> {
        match self {
            CoordMap::Log { direction, .. } => Some(-direction * z),
            CoordMap::Affine { a, r, base, .. } => {
                base.log_jacobian(r * z).map(|lj| lj - libm::log(a.abs()))
            }
            _ => None,
        }
    }

    pub fn has_component_moments(&self) -> bool {
        match self {
            CoordMap::Log { .. } => true,
            CoordMap::Affine { base, .. } => base.has_component_moments(),
            _ => false,
        }
    }

    pub fn component_moments(&self, m: f64, s: f64) -> (f64, f64) {
        match self {
            CoordMap::Log { b, direction } => log_moments(*b, *direction, m, s),
            CoordMap::Affine { a, b, r, base } => {
                let (m0, s0) = base.component_moments(r * m, s);
                (a * m0 + b, a.abs() * s0)
            }
            _ => unreachable!("map has no component moments"),
        }
    }

    pub fn has_scaled_inv(&self) -> bool {
        self.has_component_moments()
    }

    pub fn scaled_inv(&self, z: f64, w: f64) -> f64 {
        match self {
            CoordMap::Log { b, direction } => log_inverse_at_scale(*b, *direction, z, w),
            CoordMap::Affine { a, b, r, base } => a * base.scaled_inv(r * z, w) + w * b,
            _ => unreachable!("map has no scaled inverse"),
        }
    }
}

const LOG_TWO: f64 = std::f64::consts::LN_2;

pub(crate) fn log_fwd_query(b: f64, direction: f64, y: f64) -> f64 {
    let gap = direction * (y - b);
    if gap <= 0.0 {
        return -direction * f64::INFINITY;
    }
    if gap.is_infinite() {
        let half_gap = direction * (0.5 * y - 0.5 * b);
        return direction * (libm::log(half_gap) + LOG_TWO);
    }
    direction * libm::log(gap)
}

fn log_inverse_at_scale(b: f64, direction: f64, z: f64, weight: f64) -> f64 {
    let bound = weight * b;
    let log_gap = direction * z + libm::log(weight);
    let gap = libm::exp(log_gap);
    if gap.is_infinite() {
        return 2.0 * (0.5 * bound + direction * libm::exp(log_gap - LOG_TWO));
    }
    bound + direction * gap
}

fn log_moments(b: f64, direction: f64, m: f64, s: f64) -> (f64, f64) {
    let variance = s * s;
    let log_mean_gap = direction * m + 0.5 * variance;
    let mean = log_inverse_at_scale(b, direction, direction * log_mean_gap, 1.0);
    if s == 0.0 {
        return (mean, 0.0);
    }
    let log_relative_std = if variance < 1e-16 {
        libm::log(s)
    } else if variance > 40.0 {
        0.5 * variance
    } else {
        0.5 * libm::log(libm::expm1(variance))
    };
    (mean, libm::exp(log_mean_gap + log_relative_std))
}

/// A z-space predictive pushed through a monotone y <-> z map. With a table
/// (`ys`, `zs`) and the map's inverse, as the transforms build it; or with the
/// analytic map alone (log_transform), `ys`/`zs` absent.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PushforwardDist {
    pub inner: PDist,
    pub ys: Option<Vec<f64>>,
    pub zs: Option<Vec<f64>>,
    pub map: CoordMap,
}

impl PushforwardDist {
    pub fn new(inner: PDist, ys: Option<Vec<f64>>, zs: Option<Vec<f64>>, map: CoordMap) -> Self {
        PushforwardDist { inner, ys, zs, map }
    }

    fn z_of(&self, y: f64) -> f64 {
        if self.map.has_fwd() {
            return self.map.fwd(y);
        }
        interp_table(y, self.ys.as_ref().unwrap(), self.zs.as_ref().unwrap())
    }

    fn y_of(&self, z: f64) -> f64 {
        self.map.inv(z)
    }

    fn slope(&self, y: f64) -> f64 {
        if self.map.has_fwd() {
            let h = 1e-5 * (1.0 + y.abs());
            let (za, zb) = (self.map.fwd(y + h), self.map.fwd(y - h));
            if za.is_finite() && zb.is_finite() && za > zb {
                return (za - zb) / (2.0 * h);
            }
        }
        // every map carries its inverse
        let z = self.z_of(y);
        let h = 1e-5 * (1.0 + z.abs());
        let dy = self.map.inv(z + h) - self.map.inv(z - h);
        if dy > 0.0 {
            return 2.0 * h / dy;
        }
        let ys = self.ys.as_ref().unwrap();
        let zs = self.zs.as_ref().unwrap();
        let i = bisect_left(ys, y).max(1).min(ys.len() - 1);
        (zs[i] - zs[i - 1]) / (ys[i] - ys[i - 1])
    }

    pub fn logpdf(&self, x: f64) -> f64 {
        let z = self.z_of(x);
        if z.is_infinite() {
            return f64::NEG_INFINITY;
        }
        if z.is_nan() {
            return f64::NAN;
        }
        if let Some(lj) = self.map.log_jacobian(z) {
            return self.inner.logpdf(z) + lj;
        }
        self.inner.logpdf(z) + libm::log(self.slope(x))
    }

    pub fn pdf(&self, x: f64) -> f64 {
        libm::exp(self.logpdf(x))
    }

    pub fn cdf(&self, x: f64) -> f64 {
        let z = self.z_of(x);
        if z.is_infinite() {
            return if z < 0.0 { 0.0 } else { 1.0 };
        }
        if z.is_nan() {
            return f64::NAN;
        }
        self.inner.cdf(z)
    }

    pub fn quantile(&self, p: f64) -> f64 {
        self.quantile_tol(p, 1e-9, 2100)
    }

    pub fn quantile_tol(&self, p: f64, tol: f64, max_iter: usize) -> f64 {
        self.y_of(self.inner.quantile_tol(p, tol, max_iter))
    }

    pub fn crps(&self, x: f64) -> f64 {
        if !x.is_finite() {
            return x.abs();
        }
        if self.map.has_fwd() || self.zs.is_none() {
            return self.crps_from_quantiles(x);
        }
        let zstar = self.z_of(x);
        let ys = self.ys.as_ref().unwrap();
        let zs = self.zs.as_ref().unwrap();
        let s_lo = 1.0 / self.slope(ys[0]);
        let s_hi = 1.0 / self.slope(*ys.last().unwrap());
        let (z0, zn) = (zs[0], *zs.last().unwrap());
        let mut base = vec![z0 - 8.0, z0 - 6.0, z0 - 4.0, z0 - 2.0, z0 - 1.0];
        base.extend_from_slice(zs);
        base.extend_from_slice(&[zn + 1.0, zn + 2.0, zn + 4.0, zn + 6.0, zn + 8.0]);
        base.extend_from_slice(&[zstar - 1.0, zstar, zstar + 1.0]);
        base.sort_by(|a, b| a.partial_cmp(b).unwrap());
        base.dedup();
        let mut nodes = vec![base[0]];
        for &z in &base[1..] {
            let lo = *nodes.last().unwrap();
            let gap = z - lo;
            if gap > 0.1 {
                let pieces = (((gap / 0.1) as usize) + 1).min(40);
                let step = gap / pieces as f64;
                for j in 0..pieces - 1 {
                    nodes.push(lo + step * (j + 1) as f64);
                }
            }
            nodes.push(z);
        }
        let mut total = 0.0;
        let mut prev_z = nodes[0];
        let mut c_prev = self.inner.cdf(prev_z);
        for &z in &nodes[1..] {
            let c = self.inner.cdf(z);
            let ind = if prev_z >= zstar { 1.0 } else { 0.0 };
            let g0 = (c_prev - ind) * (c_prev - ind);
            let g1 = (c - ind) * (c - ind);
            let yp = if z <= z0 {
                s_lo
            } else if prev_z >= zn {
                s_hi
            } else {
                (self.y_of(z) - self.y_of(prev_z)) / (z - prev_z)
            };
            total += 0.5 * (g0 + g1) * (z - prev_z) * yp;
            prev_z = z;
            c_prev = c;
        }
        total
    }

    fn crps_from_quantiles(&self, x: f64) -> f64 {
        let rule = quantile_rule();
        let q = self.qgrid();
        let mut total = 0.0;
        for (i, &(p, w)) in rule.iter().enumerate() {
            let weight = 2.0 * w * (if q[i] >= x { 1.0 - p } else { p });
            let gap = (q[i] - x).abs();
            if gap.is_finite() {
                total += weight * gap;
            } else {
                let mut weighted_q = weight * q[i];
                if q[i].is_infinite() && self.map.has_scaled_inv() {
                    weighted_q = self.map.scaled_inv(self.inner.quantile(p), weight);
                }
                total += (weighted_q - weight * x).abs();
            }
        }
        total
    }

    fn qgrid(&self) -> Vec<f64> {
        quantile_rule()
            .iter()
            .map(|&(p, _)| self.quantile(p))
            .collect()
    }

    /// Moment-matched mixture components in y-space (the compatibility view).
    pub fn components(&self) -> Vec<(f64, f64, f64)> {
        let inner_comps = match &self.inner {
            PDist::Push(_) => None,
            other => other.components(),
        };
        match inner_comps {
            None => {
                let rule = quantile_rule();
                let q = self.qgrid();
                let mu = fsum(q.iter().zip(rule.iter()).map(|(&y, &(_, w))| w * y));
                let sd = if !mu.is_finite() {
                    f64::INFINITY
                } else {
                    let v: Vec<f64> = q
                        .iter()
                        .zip(rule.iter())
                        .map(|(&y, &(_, w))| w.sqrt() * (y - mu))
                        .collect();
                    hypot_n(&v)
                };
                vec![(1.0, mu, sd)]
            }
            Some(comps) => comps
                .into_iter()
                .filter(|&(w, _, _)| w > 0.0)
                .map(|(w, m, s)| {
                    let (mu, sd) = if self.map.has_component_moments() {
                        self.map.component_moments(m, s)
                    } else {
                        self.gaussian_moments(m, s)
                    };
                    (w, mu, sd)
                })
                .collect(),
        }
    }

    fn gaussian_moments(&self, m: f64, s: f64) -> (f64, f64) {
        let node_ys: Vec<f64> = GH7
            .iter()
            .map(|&(x, _)| self.y_of(m + s * SQRT2 * x))
            .collect();
        let mu = fsum(
            node_ys
                .iter()
                .zip(GH7.iter())
                .map(|(&y, &(_, w))| (w / SQRTPI) * y),
        );
        if !mu.is_finite() {
            return (mu, f64::INFINITY);
        }
        let v: Vec<f64> = node_ys
            .iter()
            .zip(GH7.iter())
            .map(|(&y, &(_, w))| (w / SQRTPI).sqrt() * (y - mu))
            .collect();
        (mu, hypot_n(&v).max(1e-12))
    }

    pub fn mean(&self) -> f64 {
        fsum(self.components().iter().map(|&(w, m, _)| w * m))
    }

    pub fn var(&self) -> f64 {
        let sd = self.std();
        sd * sd
    }

    pub fn std(&self) -> f64 {
        let comps = self.components();
        if comps.len() == 1 {
            return comps[0].2;
        }
        let mu = fsum(comps.iter().map(|&(w, m, _)| w * m));
        if !mu.is_finite() {
            return f64::INFINITY;
        }
        let v: Vec<f64> = comps
            .iter()
            .map(|&(w, m, s)| w.sqrt() * libm::hypot(s, m - mu))
            .collect();
        hypot_n(&v)
    }

    /// The law of a*Y + b, still a pushforward of (a reflection of) the inner.
    pub fn affine(&self, a: f64, b: f64) -> PushforwardDist {
        assert!(
            a != 0.0 && a.is_finite() && b.is_finite(),
            "affine needs a finite nonzero a and a finite b"
        );
        let r = if a > 0.0 { 1.0 } else { -1.0 };
        let inner = if r > 0.0 {
            self.inner.clone()
        } else {
            self.inner.scale(-1.0)
        };
        let (ys, zs) = match (&self.ys, &self.zs) {
            (Some(ys0), Some(zs0)) => {
                let mut ys: Vec<f64> = ys0.iter().map(|&y| a * y + b).collect();
                let mut zs: Vec<f64> = zs0.iter().map(|&z| r * z).collect();
                if r < 0.0 {
                    ys.reverse();
                    zs.reverse();
                }
                (Some(ys), Some(zs))
            }
            _ => (None, None),
        };
        let map = CoordMap::Affine {
            a,
            b,
            r,
            base: Box::new(self.map.clone()),
        };
        PushforwardDist::new(inner, ys, zs, map)
    }

    pub fn shift(&self, delta: f64) -> PushforwardDist {
        self.affine(1.0, delta)
    }

    pub fn scale(&self, factor: f64) -> PushforwardDist {
        assert!(factor != 0.0, "scale factor must be nonzero");
        self.affine(factor, 0.0)
    }
}

/// The exact pushforward of `d` through `map`. The table window adapts to the
/// predictive: [m - 10s, m + 10s] over a mixture, otherwise the extreme
/// quantiles padded by their own span on each side (transform._pushforward).
pub fn pushforward(d: &PDist, map: CoordMap) -> PDist {
    let comps = match d {
        PDist::Push(_) => None,
        other => other.components(),
    };
    let (lo, hi) = match comps {
        Some(c) => {
            let mut lo = f64::INFINITY;
            let mut hi = f64::NEG_INFINITY;
            for &(_, m, s) in &c {
                lo = lo.min(m - 10.0 * s);
                hi = hi.max(m + 10.0 * s);
            }
            (lo, hi)
        }
        None => {
            let (q_lo, q_hi) = (d.quantile(1e-6), d.quantile(1.0 - 1e-6));
            (2.0 * q_lo - q_hi, 2.0 * q_hi - q_lo)
        }
    };
    let (ys, zs) = table_from_map(&map, lo, hi, 400);
    PDist::Push(Box::new(PushforwardDist::new(
        d.clone(),
        Some(ys),
        Some(zs),
        map,
    )))
}

/// A predictive as the transforms see it: what Python reads through duck
/// typing (`mean`, `var`, `shift`, `affine`, `.components`). `Dist` keeps its
/// historical paths bit for bit; `PDist` adds the spliced and pushforward laws.
pub trait Pred: Clone {
    fn mean(&self) -> f64;
    fn var(&self) -> f64;
    fn std(&self) -> f64;
    fn shift(&self, delta: f64) -> Self;
    fn scale(&self, factor: f64) -> Self;
    fn affine(&self, a: f64, b: f64) -> Self;
    /// `.components` (panics on a law that has none, as Python raises)
    fn comps(&self) -> Cow<'_, [(f64, f64, f64)]>;
    fn has_components(&self) -> bool;
    fn from_mix(d: Dist) -> Self;
    /// shift by delta and add independent Gaussian variance (transform._widen)
    fn widen(&self, delta: f64, add: f64) -> Self;
    /// the exact pushforward through map (transform._pushforward)
    fn push(&self, map: CoordMap) -> Self;
    /// a pushforward with an analytic map, no table (log_transform)
    fn push_analytic(&self, map: CoordMap) -> Self;
}

fn widen_mix(d: &Dist, delta: f64, add: f64) -> Dist {
    Dist::new(
        d.components
            .iter()
            .map(|&(w, m, s)| (w, m + delta, (s * s + add).sqrt()))
            .collect(),
    )
}

impl Pred for Dist {
    fn mean(&self) -> f64 {
        Dist::mean(self)
    }
    fn var(&self) -> f64 {
        Dist::var(self)
    }
    fn std(&self) -> f64 {
        Dist::std(self)
    }
    fn shift(&self, delta: f64) -> Self {
        Dist::shift(self, delta)
    }
    fn scale(&self, factor: f64) -> Self {
        Dist::scale(self, factor)
    }
    fn affine(&self, a: f64, b: f64) -> Self {
        Dist::affine(self, a, b)
    }
    fn comps(&self) -> Cow<'_, [(f64, f64, f64)]> {
        Cow::Borrowed(&self.components)
    }
    fn has_components(&self) -> bool {
        true
    }
    fn from_mix(d: Dist) -> Self {
        d
    }
    fn widen(&self, delta: f64, add: f64) -> Self {
        widen_mix(self, delta, add)
    }
    fn push(&self, map: CoordMap) -> Self {
        // A Dist-typed consumer reads the pushforward through its components.
        pushforward(&PDist::Mix(self.clone()), map).to_mix()
    }
    fn push_analytic(&self, map: CoordMap) -> Self {
        PDist::Mix(self.clone()).push_analytic(map).to_mix()
    }
}

impl Pred for PDist {
    fn mean(&self) -> f64 {
        PDist::mean(self)
    }
    fn var(&self) -> f64 {
        PDist::var(self)
    }
    fn std(&self) -> f64 {
        PDist::std(self)
    }
    fn shift(&self, delta: f64) -> Self {
        PDist::shift(self, delta)
    }
    fn scale(&self, factor: f64) -> Self {
        PDist::scale(self, factor)
    }
    fn affine(&self, a: f64, b: f64) -> Self {
        PDist::affine(self, a, b)
    }
    fn comps(&self) -> Cow<'_, [(f64, f64, f64)]> {
        match self {
            PDist::Mix(d) => Cow::Borrowed(&d.components),
            PDist::Push(d) => Cow::Owned(d.components()),
            PDist::Spliced(_) => panic!("a tail-spliced predictive has no mixture components"),
        }
    }
    fn has_components(&self) -> bool {
        !matches!(self, PDist::Spliced(_))
    }
    fn from_mix(d: Dist) -> Self {
        PDist::Mix(d)
    }
    fn widen(&self, delta: f64, add: f64) -> Self {
        match self {
            PDist::Mix(d) => PDist::Mix(widen_mix(d, delta, add)),
            PDist::Spliced(s) => PDist::Spliced(s.with_body(widen_mix(&s.body, delta, add), false)),
            PDist::Push(p) => PDist::Mix(widen_mix(
                &Dist {
                    components: p.components(),
                },
                delta,
                add,
            )),
        }
    }
    fn push(&self, map: CoordMap) -> Self {
        pushforward(self, map)
    }
    fn push_analytic(&self, map: CoordMap) -> Self {
        PDist::Push(Box::new(PushforwardDist::new(
            self.clone(),
            None,
            None,
            map,
        )))
    }
}
