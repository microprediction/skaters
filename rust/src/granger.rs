//! granger: laplace with trained parameters, mixed with laplace so it cannot
//! do much worse. Port of src/skaters/granger.py (horizon 1), parity-gated
//! against it.
//!
//! The trained expert is laplace's own pipeline (pool -> sticky -> GPD tails ->
//! parade) built from a parameter file: every candidate's transform chain with
//! trained values, the ensemble's rates and prior log weights, the terminal
//! leaf's eta and scale rate, and a gate (two dense layers, tanh) that shifts
//! the ensemble's combining weights each step. The issued predictive is the
//! Aggregating-Algorithm mixture of laplace and the expert under log loss, so
//! its total log score is never more than log(1/pi_lap) behind laplace's (up to
//! floating-point rounding).
//!
//! The shipped parameter sets (monthly, weekly, hourly) are compiled into the
//! binary from rust/params/*.json.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use crate::api::{laplace, Forecaster};
use crate::leaf::{CrpsLeaf, Leaf};
use crate::parade::{parade, Parade, ParadeBase};
use crate::skater::{conjugate, sticky, terminal_leaf_ensemble, Sk, TerminalEnsemble};
use crate::tails::{gpdtails, PDist};
use crate::transform::{
    ar, difference, drift, ema_transform, fractional_difference, garch, holt_linear,
    power_transform, seasonal_anchor, seasonal_difference, standardize, theta, yeo_johnson,
    Transform,
};

const NONFINITE_LP: f64 = -1e6;
const INF_LP: f64 = 1e6;

/// A component log density as it enters the mixture weights: +inf (an exact
/// hit on a lattice atom) counts as +1e6, NaN or -inf as -1e6.
fn score(lp: f64) -> f64 {
    if lp == f64::INFINITY {
        INF_LP
    } else if lp.is_finite() {
        lp
    } else {
        NONFINITE_LP
    }
}

pub const MONTHLY_JSON: &str = include_str!("../params/monthly.json");
pub const WEEKLY_JSON: &str = include_str!("../params/weekly.json");
pub const HOURLY_JSON: &str = include_str!("../params/hourly.json");

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrunkParams {
    pub learning_rate: f64,
    pub complexity_penalty: f64,
    pub forget: f64,
    pub prior_log_weights: Vec<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TleafParams {
    pub eta: f64,
    pub scale_alpha: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CandidateParams {
    pub chain: Vec<(String, Map<String, Value>)>,
    pub depth: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GateParams {
    pub l1_weight: Vec<Vec<f64>>,
    pub l1_bias: Vec<f64>,
    pub l2_weight: Vec<Vec<f64>>,
    pub l2_bias: Vec<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GrangerParams {
    pub pi_lap: f64,
    pub trunk: TrunkParams,
    pub tleaf: TleafParams,
    pub candidates: Vec<CandidateParams>,
    pub gate: GateParams,
    #[serde(default)]
    pub frequency: String,
    #[serde(default = "format_one")]
    pub granger_format: u32,
}

fn format_one() -> u32 {
    1
}

const KNOWN: &[(&str, &[&str])] = &[
    ("ema_transform", &["alpha"]),
    ("difference", &[]),
    ("drift", &["alpha", "shrinkage"]),
    ("theta", &["alpha"]),
    ("ar", &["order", "lam", "ridge", "decay"]),
    ("holt_linear", &["alpha", "beta"]),
    ("seasonal_difference", &["period"]),
    ("seasonal_anchor", &["period", "alpha", "weight"]),
    ("standardize", &["alpha", "eps"]),
    ("fractional_difference", &["d", "window"]),
    ("garch", &["omega", "alpha", "beta", "mean_alpha", "eps"]),
    ("power_transform", &["p"]),
    ("yeo_johnson", &["lmbda"]),
];

impl GrangerParams {
    pub fn from_json(s: &str) -> Result<GrangerParams, serde_json::Error> {
        serde_json::from_str(s)
    }

    /// Check everything the builder relies on, so a bad file is an error, not a panic.
    pub fn validate(&self) -> Result<(), String> {
        if self.granger_format != 1 {
            return Err(format!("unsupported granger parameter format {}", self.granger_format));
        }
        if !(self.pi_lap > 0.0 && self.pi_lap < 1.0) {
            return Err(format!("pi_lap must lie in (0, 1), got {}", self.pi_lap));
        }
        let n = self.candidates.len();
        if n == 0 || self.trunk.prior_log_weights.len() != n {
            return Err("prior_log_weights must have one entry per candidate".into());
        }
        for c in &self.candidates {
            for (name, kw) in &c.chain {
                let keys = KNOWN
                    .iter()
                    .find(|(k, _)| *k == name.as_str())
                    .ok_or_else(|| format!("unknown transform {name}"))?
                    .1;
                for key in keys {
                    if kw.get(*key).and_then(Value::as_f64).is_none() {
                        return Err(format!("{name}: missing or non-numeric {key}"));
                    }
                }
                for (key, lo, hi) in [("order", 1.0, 64.0), ("period", 1.0, 10_000.0), ("window", 1.0, 10_000.0)] {
                    if let Some(v) = kw.get(key).and_then(Value::as_f64) {
                        if !(v >= lo && v <= hi && v.fract() == 0.0) {
                            return Err(format!("{name}: {key} must be an integer in [{lo}, {hi}], got {v}"));
                        }
                    }
                }
                if kw.get("exact").and_then(Value::as_bool).unwrap_or(false) {
                    return Err(format!("{name}(exact=True) is not ported"));
                }
            }
        }
        let g = &self.gate;
        let hidden = g.l1_weight.len();
        if hidden == 0
            || g.l1_bias.len() != hidden
            || g.l1_weight.iter().any(|r| r.len() != n + 3)
            || g.l2_weight.len() != n
            || g.l2_bias.len() != n
            || g.l2_weight.iter().any(|r| r.len() != hidden)
        {
            return Err(format!("gate dimensions do not match {n} candidates (inputs must be {})", n + 3));
        }
        Ok(())
    }

    /// A shipped parameter set: "monthly", "weekly" or "hourly".
    pub fn shipped(frequency: &str) -> Option<GrangerParams> {
        let s = match frequency {
            "monthly" => MONTHLY_JSON,
            "weekly" => WEEKLY_JSON,
            "hourly" => HOURLY_JSON,
            _ => return None,
        };
        Some(GrangerParams::from_json(s).expect("shipped granger parameters parse"))
    }
}

fn num(kw: &Map<String, Value>, key: &str) -> f64 {
    kw.get(key).and_then(Value::as_f64).unwrap_or_else(|| panic!("granger: missing {key}"))
}

fn int(kw: &Map<String, Value>, key: &str) -> usize {
    num(kw, key) as usize
}

fn exact_off(kw: &Map<String, Value>, name: &str) {
    if kw.get("exact").and_then(Value::as_bool).unwrap_or(false) {
        panic!("granger: {name}(exact=True) is not ported");
    }
}

fn transform(name: &str, kw: &Map<String, Value>) -> Transform {
    match name {
        "ema_transform" => ema_transform(num(kw, "alpha")),
        "difference" => difference(),
        "drift" => drift(num(kw, "alpha"), num(kw, "shrinkage")),
        "theta" => theta(num(kw, "alpha")),
        "ar" => ar(int(kw, "order"), num(kw, "lam"), num(kw, "ridge"), num(kw, "decay")),
        "holt_linear" => holt_linear(num(kw, "alpha"), num(kw, "beta")),
        "seasonal_difference" => seasonal_difference(int(kw, "period")),
        "seasonal_anchor" => seasonal_anchor(int(kw, "period"), num(kw, "alpha"), num(kw, "weight")),
        "standardize" => standardize(num(kw, "alpha"), num(kw, "eps")),
        "fractional_difference" => fractional_difference(num(kw, "d"), int(kw, "window")),
        "garch" => garch(num(kw, "omega"), num(kw, "alpha"), num(kw, "beta"), num(kw, "mean_alpha"), num(kw, "eps")),
        "power_transform" => {
            exact_off(kw, name);
            power_transform(num(kw, "p"))
        }
        "yeo_johnson" => {
            exact_off(kw, name);
            yeo_johnson(num(kw, "lmbda"))
        }
        other => panic!("granger: unknown transform {other}"),
    }
}

fn expert(p: &GrangerParams) -> Parade {
    let cands: Vec<Sk> = p
        .candidates
        .iter()
        .map(|c| {
            let mut f = Sk::Leaf(Leaf::new(1));
            for (name, kw) in c.chain.iter().rev() {
                f = conjugate(f, transform(name, kw), 1);
            }
            f
        })
        .collect();
    let depths: Vec<f64> = p.candidates.iter().map(|c| c.depth).collect();
    let tleafs = vec![Sk::Crps(CrpsLeaf::new(1, p.tleaf.eta, p.tleaf.scale_alpha))];
    let mut f = terminal_leaf_ensemble(
        cands, tleafs, 1, p.trunk.learning_rate, p.trunk.complexity_penalty, depths, 20,
        p.trunk.forget,
    );
    if let Sk::Terminal(t) = &mut f {
        t.log_w = p.trunk.prior_log_weights.clone();
    }
    let f = sticky(f, 1);
    let g = gpdtails(f, 1, 0.98, 500, 500);
    parade(ParadeBase::Gpd(g), 1)
}

fn trunk_mut(p: &mut Parade) -> &mut TerminalEnsemble {
    match &mut p.base {
        ParadeBase::Gpd(g) => match &mut g.base {
            Sk::Sticky(s) => match &mut s.base {
                Sk::Terminal(t) => t,
                _ => panic!("granger: expected the ensemble under sticky"),
            },
            _ => panic!("granger: expected sticky under the tails"),
        },
        _ => panic!("granger: expected GPD tails under the parade"),
    }
}

fn gate(g: &GateParams, feats: &[f64]) -> Vec<f64> {
    let hidden: Vec<f64> = g
        .l1_weight
        .iter()
        .zip(g.l1_bias.iter())
        .map(|(row, b)| {
            let mut acc = 0.0;
            for (w, x) in row.iter().zip(feats.iter()) {
                acc += w * x;
            }
            libm::tanh(b + acc)
        })
        .collect();
    g.l2_weight
        .iter()
        .zip(g.l2_bias.iter())
        .map(|(row, b)| {
            let mut acc = 0.0;
            for (w, h) in row.iter().zip(hidden.iter()) {
                acc += w * h;
            }
            b + acc
        })
        .collect()
}

/// The two-component mixture granger issues.
#[derive(Clone, Debug)]
pub struct Mixture {
    pub dists: [PDist; 2],
    pub log_w: [f64; 2],
    pub w: [f64; 2],
}

impl Mixture {
    fn new(dists: [PDist; 2], lw: [f64; 2]) -> Mixture {
        let m = lw[0].max(lw[1]);
        let s = libm::log(libm::exp(lw[0] - m) + libm::exp(lw[1] - m)) + m;
        let log_w = [lw[0] - s, lw[1] - s];
        Mixture { dists, log_w, w: [libm::exp(log_w[0]), libm::exp(log_w[1])] }
    }

    pub fn logpdf(&self, x: f64) -> f64 {
        let term = |i: usize| {
            let v = self.dists[i].logpdf(x);
            if v.is_nan() { f64::NEG_INFINITY } else { self.log_w[i] + v } // a NaN component contributes nothing
        };
        let t = [term(0), term(1)];
        let m = t[0].max(t[1]);
        if m == f64::INFINITY {
            return f64::INFINITY;
        }
        if m == f64::NEG_INFINITY {
            return f64::NEG_INFINITY;
        }
        m + libm::log(libm::exp(t[0] - m) + libm::exp(t[1] - m))
    }

    pub fn cdf(&self, x: f64) -> f64 {
        self.w[0] * self.dists[0].cdf(x) + self.w[1] * self.dists[1].cdf(x)
    }

    pub fn mean(&self) -> f64 {
        self.w[0] * self.dists[0].mean() + self.w[1] * self.dists[1].mean()
    }

    pub fn var(&self) -> f64 {
        let mu = self.mean();
        (0..2)
            .map(|i| {
                let s = self.dists[i].std();
                let d = self.dists[i].mean() - mu;
                self.w[i] * (s * s + d * d)
            })
            .sum()
    }

    pub fn std(&self) -> f64 {
        self.var().max(0.0).sqrt()
    }

    pub fn quantile(&self, p: f64) -> f64 {
        assert!(0.0 < p && p < 1.0, "quantile needs 0 < p < 1");
        let tol = 1e-9;
        let q0 = self.dists[0].quantile(p);
        let q1 = self.dists[1].quantile(p);
        let (mut lo, mut hi) = (q0.min(q1), q0.max(q1));
        if hi - lo < tol {
            return 0.5 * (lo + hi);
        }
        for _ in 0..200 {
            let mid = 0.5 * (lo + hi);
            if self.cdf(mid) < p {
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

    pub fn crps(&self, x: f64) -> f64 {
        let n = 65usize;
        let q: Vec<f64> = (0..n).map(|i| self.quantile((i as f64 + 0.5) / n as f64)).collect();
        let t1: f64 = q.iter().map(|v| (v - x).abs()).sum::<f64>() / n as f64;
        let t2: f64 = 2.0
            * q.iter()
                .enumerate()
                .map(|(i, v)| v * (2.0 * (i as f64 + 0.5) / n as f64 - 1.0))
                .sum::<f64>()
            / n as f64;
        t1 - 0.5 * t2
    }
}

/// granger at horizon 1.
#[derive(Clone, Debug)]
pub struct Granger {
    pub params: GrangerParams,
    pub lap: Forecaster,
    pub expert: Parade,
    pend: Option<(PDist, PDist)>,
    cum: [f64; 2],
    log_prior: [f64; 2],
    pub t: u64,
    pub z: Option<f64>,
    repeat_frac: f64,
    abs_z_mean: f64,
    n: u64,
    last_y: Option<f64>,
}

impl Granger {
    /// Build from validated parameters (see [`Granger::try_new`] for a fallible build).
    pub fn new(params: GrangerParams) -> Granger {
        Granger::try_new(params).expect("granger parameters")
    }

    pub fn try_new(params: GrangerParams) -> Result<Granger, String> {
        params.validate()?;
        Ok(Granger::build(params))
    }

    fn build(params: GrangerParams) -> Granger {
        let expert = expert(&params);
        let log_prior = [libm::log(params.pi_lap), libm::log(1.0 - params.pi_lap)];
        Granger {
            params,
            lap: laplace(1),
            expert,
            pend: None,
            cum: [0.0, 0.0],
            log_prior,
            t: 0,
            z: None,
            repeat_frac: 0.0,
            abs_z_mean: 0.0,
            n: 0,
            last_y: None,
        }
    }

    /// A shipped parameter set: "monthly", "weekly" or "hourly".
    pub fn shipped(frequency: &str) -> Option<Granger> {
        GrangerParams::shipped(frequency).map(Granger::new)
    }

    fn features(&mut self) -> Vec<f64> {
        let n = self.params.candidates.len();
        let z = self.z.map(|v| v.clamp(-8.0, 8.0)).unwrap_or(0.0);
        let mut f = vec![z, self.repeat_frac, self.abs_z_mean];
        // zeros until the ensemble has stepped once (a leading missing value
        // leaves it unstepped, as in the Python reference)
        let stepped = trunk_mut(&mut self.expert).qdist.first().is_some_and(|q| !q.is_empty());
        if !stepped {
            f.extend(std::iter::repeat(0.0).take(n));
        } else {
            let lw = &trunk_mut(&mut self.expert).log_w;
            let m = lw.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            f.extend(lw.iter().map(|v| (v - m).max(-20.0) / 20.0));
        }
        f
    }

    pub fn step(&mut self, y: f64) -> Mixture {
        let finite = y.is_finite();
        // 1. score the matured forecasts for y (undiscounted, unfloored)
        if finite {
            if let Some((lap_d, lrn_d)) = &self.pend {
                for (j, d) in [lap_d, lrn_d].iter().enumerate() {
                    self.cum[j] += score(d.logpdf(y));
                }
                // re-centre: the weights depend only on the difference
                let mx = self.cum[0].max(self.cum[1]);
                self.cum[0] -= mx;
                self.cum[1] -= mx;
            }
        }
        // 2. the trained expert with its combining weights shifted by the gate
        let feats = self.features();
        let offset = gate(&self.params.gate, &feats);
        trunk_mut(&mut self.expert).gate_offset = Some(offset);
        let lrn = self.expert.step(y).remove(0);
        trunk_mut(&mut self.expert).gate_offset = None;
        let lap = self.lap.step(y).remove(0);
        self.pend = Some((lap.clone(), lrn.clone()));
        // 3. descriptors for the next step's gate
        self.z = self.expert.z.first().cloned().flatten();
        if finite {
            self.n += 1;
            let rep = if self.last_y == Some(y) { 1.0 } else { 0.0 };
            self.repeat_frac += (rep - self.repeat_frac) / self.n as f64;
            if let Some(z0) = self.z {
                if z0.is_finite() {
                    self.abs_z_mean += (z0.abs().min(8.0) - self.abs_z_mean) / self.n as f64;
                }
            }
            self.last_y = Some(y);
        }
        // 4. the guaranteed mixture
        let lw = [self.log_prior[0] + self.cum[0], self.log_prior[1] + self.cum[1]];
        self.t += 1;
        Mixture::new([lap, lrn], lw)
    }
}
