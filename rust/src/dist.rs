//! Gaussian mixture distribution: the distributional prediction type.
//! Port of src/skaters/dist.py. Operation order mirrors Python exactly,
//! including the ulp-tolerant prune and CPython-compatible compensated sums.

use crate::mathx::{abs_expectation, fsum, gaussian_cdf, gaussian_pdf, LOG_SQRT2PI};
use serde::{Deserialize, Serialize};

/// A weighted mixture of Gaussians. Components are (weight, mean, std).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Dist {
    pub components: Vec<(f64, f64, f64)>,
}

impl Dist {
    pub fn new(components: Vec<(f64, f64, f64)>) -> Dist {
        assert!(!components.is_empty());
        let w_total = fsum(components.iter().map(|c| c.0));
        assert!(w_total > 0.0);
        Dist {
            components: components
                .into_iter()
                .map(|(w, m, s)| (w / w_total, m, s))
                .collect(),
        }
    }

    pub fn gaussian(mean: f64, std: f64) -> Dist {
        Dist {
            components: vec![(1.0, mean, std)],
        }
    }

    /// Weighted mixture of distributions (exact).
    pub fn combine_refs(dists: &[&Dist], weights: Option<&[f64]>) -> Dist {
        let n = dists.len();
        let uniform = vec![1.0 / n as f64; n];
        let weights = weights.unwrap_or(&uniform);
        let w_total = fsum(weights.iter().copied());
        let mut components = Vec::new();
        for (d, &w_outer) in dists.iter().zip(weights.iter()) {
            for &(w_inner, m, s) in &d.components {
                components.push((w_outer / w_total * w_inner, m, s));
            }
        }
        Dist::new(components)
    }

    pub fn pdf(&self, x: f64) -> f64 {
        let mut total = 0.0;
        for &(w, m, s) in &self.components {
            if w <= 0.0 {
                continue; // skaters#222: 0 * infinity at a discarded (s=0) atom is NaN
            }
            total += w * gaussian_pdf(x, m, s);
        }
        total
    }

    /// Log density at x, accumulated in log-space (log-sum-exp).
    pub fn logpdf(&self, x: f64) -> f64 {
        let mut best = f64::NEG_INFINITY;
        let mut terms: Vec<f64> = Vec::new();
        for &(w, m, s) in &self.components {
            if w <= 0.0 {
                continue;
            }
            if s <= 0.0 {
                if x == m {
                    return f64::INFINITY;
                }
                continue;
            }
            let z = (x - m) / s;
            let t = libm::log(w) - 0.5 * z * z - libm::log(s) - LOG_SQRT2PI;
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

    pub fn cdf(&self, x: f64) -> f64 {
        let mut total = 0.0;
        for &(w, m, s) in &self.components {
            total += w * gaussian_cdf(x, m, s);
        }
        total
    }

    /// CRPS at observation x (closed form for a Gaussian mixture).
    pub fn crps(&self, x: f64) -> f64 {
        let comps = &self.components;
        let mut t1 = 0.0;
        for &(w, m, s) in comps {
            t1 += w * abs_expectation(m - x, s);
        }
        let mut t2 = 0.0;
        for &(wi, mi, si) in comps {
            for &(wj, mj, sj) in comps {
                t2 += wi * wj * abs_expectation(mi - mj, (si * si + sj * sj).sqrt());
            }
        }
        t1 - 0.5 * t2
    }

    /// Inverse CDF: relative x tolerance below unit scale, with a binary64
    /// convergence budget. An explicit smaller budget may return a midpoint
    /// before convergence. Mirrors Python/JS, including exact atom jumps.
    pub fn quantile(&self, p: f64) -> f64 {
        self.quantile_tol(p, 1e-9, 2100)
    }

    pub fn quantile_tol(&self, p: f64, tol: f64, max_iter: usize) -> f64 {
        assert!(0.0 < p && p < 1.0);
        let mu = self.mean();
        let sigma = self.var().sqrt();
        assert!(
            sigma.is_finite(),
            "quantile needs a finite mixture variance"
        );
        let mut min_sigma = f64::INFINITY;
        for &(w, _, s) in &self.components {
            if w > 0.0 && s > 0.0 {
                min_sigma = min_sigma.min(s);
            }
        }
        if !min_sigma.is_finite() {
            min_sigma = 1.0;
        }
        let x_tol = tol * min_sigma.min(1.0);
        let mut lo = mu - 8.0 * sigma;
        let mut hi = mu + 8.0 * sigma;
        let seed = (16.0 * sigma).max(1e-12 * mu.abs().max(1.0));
        let mut width = seed;
        let mut found = false;
        for _ in 0..120 {
            if self.cdf(lo) < p {
                found = true;
                break;
            }
            lo -= width;
            width *= 2.0;
        }
        assert!(found, "could not bracket quantile from below");
        width = seed;
        found = false;
        for _ in 0..120 {
            if self.cdf(hi) >= p {
                found = true;
                break;
            }
            hi += width;
            width *= 2.0;
        }
        assert!(found, "could not bracket quantile from above");
        assert!(
            lo.is_finite() && hi.is_finite(),
            "quantile needs a finite search bracket"
        );
        for _ in 0..max_iter {
            let mut mid = 0.5 * (lo + hi);
            if !mid.is_finite() {
                mid = 0.5 * lo + 0.5 * hi;
            }
            if !(lo < mid && mid < hi) {
                let gap = hi - lo;
                if 0.0 < tol && tol <= 2.0 * gap {
                    let (mut lower, mut upper, mut swapped_lower, mut swapped_upper) =
                        (0.0, 0.0, 0.0, 0.0);
                    for &(w, m, s) in &self.components {
                        let cl = w * gaussian_cdf(lo, m, s);
                        let cu = w * gaussian_cdf(hi, m, s);
                        lower += cl;
                        upper += cu;
                        let unresolved = w > 0.0 && s <= gap;
                        swapped_lower += if unresolved { cu } else { cl };
                        swapped_upper += if unresolved { cl } else { cu };
                    }
                    if swapped_lower == lower && swapped_upper == upper {
                        return mid;
                    }
                }
                return hi;
            }
            if self.cdf(mid) < p {
                lo = mid;
            } else {
                hi = mid;
            }
            if hi - lo < x_tol {
                for &(w, m, s) in &self.components {
                    if w > 0.0 && s == 0.0 && lo <= m && m <= hi {
                        let mut left = 0.0;
                        for &(wi, mi, si) in &self.components {
                            left += wi
                                * if si == 0.0 {
                                    if mi < m {
                                        1.0
                                    } else {
                                        0.0
                                    }
                                } else {
                                    gaussian_cdf(m, mi, si)
                                };
                        }
                        if left < p && p <= self.cdf(m) {
                            return m;
                        }
                    }
                }
                break;
            }
        }
        let mid = 0.5 * (lo + hi);
        if mid.is_finite() {
            mid
        } else {
            0.5 * lo + 0.5 * hi
        }
    }

    pub fn mean(&self) -> f64 {
        fsum(self.components.iter().map(|&(w, m, _)| w * m))
    }

    /// Variance of the mixture (law of total variance, centered form).
    pub fn var(&self) -> f64 {
        let mu = self.mean();
        fsum(
            self.components
                .iter()
                .map(|&(w, m, s)| w * (s * s + (m - mu) * (m - mu))),
        )
    }

    pub fn std(&self) -> f64 {
        let v = self.var();
        if v > 0.0 {
            v.sqrt()
        } else {
            0.0
        }
    }

    pub fn shift(&self, delta: f64) -> Dist {
        Dist {
            components: self
                .components
                .iter()
                .map(|&(w, m, s)| (w, m + delta, s))
                .collect(),
        }
    }

    pub fn scale(&self, factor: f64) -> Dist {
        assert!(factor != 0.0);
        let f = factor.abs();
        Dist {
            components: self
                .components
                .iter()
                .map(|&(w, m, s)| (w, m * factor, s * f))
                .collect(),
        }
    }

    pub fn affine(&self, a: f64, b: f64) -> Dist {
        assert!(a != 0.0);
        Dist {
            components: self
                .components
                .iter()
                .map(|&(w, m, s)| (w, a * m + b, a.abs() * s))
                .collect(),
        }
    }

    pub fn len(&self) -> usize {
        self.components.len()
    }

    /// Reduce component count by merging closest pairs (ulp-tolerant pair
    /// selection, mirroring Python's platform-stable prune exactly).
    pub fn prune(&self, max_components: usize) -> Dist {
        let max_components = max_components.max(1);
        if self.components.len() <= max_components {
            return self.clone();
        }
        // Sort by (mean, std, weight) — Python's stable tuple sort.
        let mut comps = self.components.clone();
        comps.sort_by(|a, b| {
            a.1.partial_cmp(&b.1)
                .unwrap()
                .then(a.2.partial_cmp(&b.2).unwrap())
                .then(a.0.partial_cmp(&b.0).unwrap())
        });
        // Translation-invariant (skaters#226): the span of the sorted means,
        // not the sum of their absolute locations (which inflates with
        // translation).
        let scale = (comps[comps.len() - 1].1 - comps[0].1) + 1e-12;
        while comps.len() > max_components {
            let mut best_dist = f64::INFINITY;
            for i in 0..comps.len() {
                for j in (i + 1)..comps.len() {
                    let d = (comps[i].1 - comps[j].1).abs();
                    if d < best_dist {
                        best_dist = d;
                    }
                }
            }
            let thresh = best_dist + 1e-9 * scale;
            let mut best_pair: Option<(usize, usize)> = None;
            'outer: for i in 0..comps.len() {
                for j in (i + 1)..comps.len() {
                    if (comps[i].1 - comps[j].1).abs() <= thresh {
                        best_pair = Some((i, j));
                        break 'outer;
                    }
                }
            }
            // NaN-mean fallback: merge the first pair so pruning terminates.
            let (best_i, best_j) = best_pair.unwrap_or((0, 1));
            let (wi, mi, si) = comps[best_i];
            let (wj, mj, sj) = comps[best_j];
            let w_new = wi + wj;
            let (m_new, s_new);
            if w_new < 1e-300 {
                m_new = 0.5 * (mi + mj);
                s_new = si.max(sj).max(1e-12);
            } else {
                m_new = (wi * mi + wj * mj) / w_new;
                let v_new = (wi * (si * si + (mi - m_new) * (mi - m_new))
                    + wj * (sj * sj + (mj - m_new) * (mj - m_new)))
                    / w_new;
                s_new = v_new.max(0.0).sqrt();
            }
            comps[best_i] = (w_new, m_new, s_new);
            comps.remove(best_j);
        }
        Dist::new(comps)
    }
}
