//! Canonical skater state: the plain JSON layout of docs/STATE.md.
//!
//! Python is the reference. A Rust skater is a struct holding both its
//! configuration and its state; [`State::state_to_json`] writes the state
//! part in exactly the layout Python's `state_to_json` produces, and
//! [`State::load_state`] reads it back into a skater built from the same
//! factory. `null` (Python's `None`, before the first observation) maps to a
//! fresh state, and a fresh Rust state writes `null`, so a checkpoint moves
//! between the ports in both directions.
//!
//! Distributions are `{"components": [[w, mean, std], ...]}` and the
//! GPD-spliced predictive is `{"spliced": true, "body": ..., ...}`. Integer
//! fields are written as JSON integers and floats as floats, as Python writes
//! them; a reader accepts either for any numeric field. Weights that already
//! sum to one within 1e-9 are kept bit for bit (`Dist.from_dict`).
//!
//! The serde derives on the structs remain: they are Rust's own native
//! format (configuration plus state), which older skaters-fast checkpoints
//! use and which still loads.

use crate::api::{FConj, Forecaster};
use crate::dist::Dist;
use crate::granger::Granger;
use crate::homogenize::{CandState, Cell, Correction, Homogenize};
use crate::leaf::{one_idx, CrpsLeaf, GarchLeaf, Leaf, ScaleMixLeaf};
use crate::mathx::fsum;
use crate::parade::{Parade, ParadeBase};
use crate::periodicity::PeriodDetector;
use crate::residual::{theta_of, Learner, ResidualTheta, ResidualTransform};
use crate::runstats::RunningVar;
use crate::search::{
    base_transforms, build_from_recipe, GrammarEntry, GrammarOp, Search, SearchEntry,
};
use crate::skater::{
    Adapt, BayesEnsemble, Conj, Multiscale, PwEnsemble, Sk, Sticky, TerminalEnsemble,
};
use crate::tails::{GpdTails, HorizonTail, PDist, SplicedDist, Tail};
use crate::transform::*;
use serde_json::{Map, Value};
use std::collections::VecDeque;

pub type SResult<T> = Result<T, String>;

/// A skater whose state has the canonical plain-JSON layout.
pub trait State {
    /// The canonical state, `null` when fresh (before the first observation).
    fn state_to_json(&self) -> Value;
    /// Load a canonical state into a skater built from the same factory.
    /// `null` resets it to fresh.
    fn load_state(&mut self, v: &Value) -> SResult<()>;
    /// True before the first observation (the state Python calls `None`).
    fn is_fresh(&self) -> bool;
}

/// Python's `state_to_json(state)` for a Rust skater.
pub fn state_to_json<S: State + ?Sized>(s: &S) -> Value {
    s.state_to_json()
}

/// Load a canonical state (Python's `state_from_json`, then resume).
pub fn state_from_json<S: State + ?Sized>(s: &mut S, v: &Value) -> SResult<()> {
    s.load_state(v)
}

// ---------------------------------------------------------------------------
// writers
// ---------------------------------------------------------------------------

pub(crate) fn fv(x: f64) -> Value {
    match serde_json::Number::from_f64(x) {
        Some(n) => Value::Number(n),
        None => panic!("skater state holds a non-finite float {x} (JSON has no literal for it)"),
    }
}

pub(crate) fn ofv(x: Option<f64>) -> Value {
    x.map(fv).unwrap_or(Value::Null)
}

pub(crate) fn fvs<'a, I: IntoIterator<Item = &'a f64>>(xs: I) -> Value {
    Value::Array(xs.into_iter().map(|&x| fv(x)).collect())
}

pub(crate) fn iv(x: u64) -> Value {
    Value::from(x)
}

pub(crate) fn obj(pairs: Vec<(&str, Value)>) -> Value {
    let mut m = Map::new();
    for (k, v) in pairs {
        m.insert(k.to_string(), v);
    }
    Value::Object(m)
}

pub fn dist_to_json(d: &Dist) -> Value {
    obj(vec![(
        "components",
        Value::Array(
            d.components
                .iter()
                .map(|&(w, m, s)| Value::Array(vec![fv(w), fv(m), fv(s)]))
                .collect(),
        ),
    )])
}

pub fn spliced_to_json(s: &SplicedDist) -> Value {
    obj(vec![
        ("spliced", Value::Bool(true)),
        ("body", dist_to_json(&s.body)),
        ("t_lo", fv(s.t_lo)),
        ("t_up", fv(s.t_up)),
        ("zeta_lo", fv(s.zeta_lo)),
        ("zeta_up", fv(s.zeta_up)),
        ("g_lo", fv(s.g_lo)),
        ("s_lo", fv(s.s_lo)),
        ("g_up", fv(s.g_up)),
        ("s_up", fv(s.s_up)),
    ])
}

/// A predictive in state. Only mixtures and GPD-spliced laws are plain data;
/// Python's `state_to_json` raises on anything else, and this panics.
pub fn pdist_to_json(d: &PDist) -> Value {
    match d {
        PDist::Mix(d) => dist_to_json(d),
        PDist::Spliced(s) => spliced_to_json(s),
        _ => panic!("skater state holds a predictive that is not a Dist or SplicedDist"),
    }
}

fn dists_to_json<'a, I: IntoIterator<Item = &'a Dist>>(ds: I) -> Value {
    Value::Array(ds.into_iter().map(dist_to_json).collect())
}

fn pdists_to_json<'a, I: IntoIterator<Item = &'a PDist>>(ds: I) -> Value {
    Value::Array(ds.into_iter().map(pdist_to_json).collect())
}

fn odist_to_json(d: &Option<Dist>) -> Value {
    d.as_ref().map(dist_to_json).unwrap_or(Value::Null)
}

fn rv_to_json(r: &RunningVar) -> Value {
    obj(vec![("n", iv(r.n)), ("mean", fv(r.mean)), ("m2", fv(r.m2))])
}

// ---------------------------------------------------------------------------
// readers
// ---------------------------------------------------------------------------

pub(crate) fn get<'a>(v: &'a Value, k: &str) -> SResult<&'a Value> {
    match v {
        Value::Object(m) => m
            .get(k)
            .ok_or_else(|| format!("state is missing key {k:?}")),
        _ => Err(format!(
            "expected an object holding {k:?}, got {}",
            short(v)
        )),
    }
}

fn short(v: &Value) -> String {
    let s = v.to_string();
    if s.len() > 60 {
        format!("{}...", &s[..60])
    } else {
        s
    }
}

pub(crate) fn num(v: &Value) -> SResult<f64> {
    v.as_f64()
        .ok_or_else(|| format!("expected a number, got {}", short(v)))
}

pub(crate) fn gnum(v: &Value, k: &str) -> SResult<f64> {
    num(get(v, k)?).map_err(|e| format!("{k}: {e}"))
}

pub(crate) fn uint(v: &Value) -> SResult<u64> {
    if let Some(u) = v.as_u64() {
        return Ok(u);
    }
    if let Some(f) = v.as_f64() {
        if f >= 0.0 && f == libm::trunc(f) && f < 1.8e19 {
            return Ok(f as u64);
        }
    }
    Err(format!("expected a non-negative integer, got {}", short(v)))
}

pub(crate) fn guint(v: &Value, k: &str) -> SResult<u64> {
    uint(get(v, k)?).map_err(|e| format!("{k}: {e}"))
}

fn sint(v: &Value) -> SResult<i64> {
    if let Some(i) = v.as_i64() {
        return Ok(i);
    }
    if let Some(f) = v.as_f64() {
        if f == libm::trunc(f) && f.abs() < 9e18 {
            return Ok(f as i64);
        }
    }
    Err(format!("expected an integer, got {}", short(v)))
}

pub(crate) fn onum(v: &Value) -> SResult<Option<f64>> {
    if v.is_null() {
        Ok(None)
    } else {
        num(v).map(Some)
    }
}

pub(crate) fn arr(v: &Value) -> SResult<&Vec<Value>> {
    v.as_array()
        .ok_or_else(|| format!("expected a list, got {}", short(v)))
}

pub(crate) fn garr<'a>(v: &'a Value, k: &str) -> SResult<&'a Vec<Value>> {
    arr(get(v, k)?).map_err(|e| format!("{k}: {e}"))
}

pub(crate) fn nums(v: &Value) -> SResult<Vec<f64>> {
    arr(v)?.iter().map(num).collect()
}

pub(crate) fn gnums(v: &Value, k: &str) -> SResult<Vec<f64>> {
    nums(get(v, k)?).map_err(|e| format!("{k}: {e}"))
}

fn check_len(what: &str, got: usize, want: usize) -> SResult<()> {
    if got != want {
        return Err(format!("{what}: length {got}, this skater has {want}"));
    }
    Ok(())
}

/// `Dist.from_dict`: weights summing to one within 1e-9 are kept bit for bit.
pub fn dist_from_json(v: &Value) -> SResult<Dist> {
    let comps = garr(v, "components")?;
    let mut c = Vec::with_capacity(comps.len());
    for x in comps {
        let t = nums(x)?;
        if t.len() != 3 {
            return Err("a Dist component is [weight, mean, std]".into());
        }
        c.push((t[0], t[1], t[2]));
    }
    if c.is_empty() {
        return Err("a Dist needs at least one component".into());
    }
    if (fsum(c.iter().map(|x| x.0)) - 1.0).abs() <= 1e-9 {
        Ok(Dist { components: c })
    } else {
        Ok(Dist::new(c))
    }
}

pub fn pdist_from_json(v: &Value) -> SResult<PDist> {
    if v.get("spliced").and_then(Value::as_bool) == Some(true) {
        return Ok(PDist::Spliced(SplicedDist::new(
            dist_from_json(get(v, "body")?)?,
            gnum(v, "t_lo")?,
            gnum(v, "t_up")?,
            gnum(v, "zeta_lo")?,
            gnum(v, "zeta_up")?,
            gnum(v, "g_lo")?,
            gnum(v, "s_lo")?,
            gnum(v, "g_up")?,
            gnum(v, "s_up")?,
        )));
    }
    Ok(PDist::Mix(dist_from_json(v)?))
}

fn dists_from_json(v: &Value) -> SResult<Vec<Dist>> {
    arr(v)?.iter().map(dist_from_json).collect()
}

fn pdists_from_json(v: &Value) -> SResult<Vec<PDist>> {
    arr(v)?.iter().map(pdist_from_json).collect()
}

fn odist_from_json(v: &Value) -> SResult<Option<Dist>> {
    if v.is_null() {
        Ok(None)
    } else {
        dist_from_json(v).map(Some)
    }
}

fn opdist_from_json(v: &Value) -> SResult<Option<PDist>> {
    if v.is_null() {
        Ok(None)
    } else {
        pdist_from_json(v).map(Some)
    }
}

fn rv_from_json(v: &Value) -> SResult<RunningVar> {
    Ok(RunningVar {
        n: guint(v, "n")?,
        mean: gnum(v, "mean")?,
        m2: gnum(v, "m2")?,
    })
}

// ---------------------------------------------------------------------------
// transforms (the t_state of a conjugate)
// ---------------------------------------------------------------------------

impl State for Transform {
    fn is_fresh(&self) -> bool {
        match self {
            Transform::Difference(t) => !t.init,
            Transform::FracDiff(t) => t.buffer.is_empty(),
            Transform::Standardize(t) => !t.init,
            Transform::EmaT(t) => !t.init,
            Transform::Ou(t) => !t.init,
            Transform::Theta(t) => !t.init,
            Transform::Drift(t) => !t.init,
            Transform::Holt(t) => !t.init,
            Transform::Garch(t) => !t.init,
            Transform::Seasonal(t) => !t.init,
            Transform::SeasonalAnchor(t) => !t.init,
            Transform::Ar(t) => t.n == 0,
            Transform::GroupedAr(t) => t.n == 0,
            Transform::SeasonalScale(t) => !t.init,
            Transform::Gaussianize(t) => t.n == 0,
            // stateless: the state is {} once stepped, and nothing to tell
            Transform::Power(_) | Transform::YeoJohnson(_) | Transform::LogT(_) => false,
        }
    }

    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        match self {
            Transform::Difference(t) => obj(vec![("last", fv(t.last))]),
            Transform::FracDiff(t) => obj(vec![("buffer", fvs(&t.buffer))]),
            Transform::Standardize(t) => obj(vec![("mu", fv(t.mu)), ("var", fv(t.var))]),
            Transform::EmaT(t) => obj(vec![("level", fv(t.level))]),
            Transform::Ou(t) => obj(vec![("m", fv(t.m)), ("fc", fv(t.fc)), ("y", fv(t.y))]),
            Transform::Theta(t) => {
                let mut p = vec![
                    ("ses", fv(t.ses)),
                    ("t", iv(t.t)),
                    ("sum_t", fv(t.sum_t)),
                    ("sum_t2", fv(t.sum_t2)),
                    ("sum_y", fv(t.sum_y)),
                    ("sum_ty", fv(t.sum_ty)),
                ];
                // Python adds "slope" from the second observation on
                if t.t >= 2 {
                    p.push(("slope", fv(t.slope)));
                }
                obj(p)
            }
            Transform::Drift(t) => obj(vec![("last", fv(t.last)), ("mu", fv(t.mu))]),
            Transform::Holt(t) => obj(vec![("level", fv(t.level)), ("trend", fv(t.trend))]),
            Transform::Garch(t) => obj(vec![
                ("var", fv(t.var)),
                ("last_dev", fv(t.last_dev)),
                ("mu", fv(t.mu)),
            ]),
            Transform::Seasonal(t) => obj(vec![("buffer", fvs(&t.buffer))]),
            Transform::SeasonalAnchor(t) => obj(vec![
                ("ema", Value::Array(t.ema.iter().map(|&e| ofv(e)).collect())),
                ("buffer", fvs(&t.buffer)),
                ("n", iv(t.n as u64)),
            ]),
            Transform::Power(_) | Transform::YeoJohnson(_) | Transform::LogT(_) => {
                Value::Object(Map::new())
            }
            Transform::Ar(t) => obj(vec![
                ("buffer", fvs(&t.buffer)),
                ("phi", fvs(&t.phi)),
                ("phi_used", fvs(&t.phi_used)),
                ("P", fvs(&t.pmat)),
                ("n", iv(t.n)),
            ]),
            Transform::GroupedAr(t) => obj(vec![
                ("buffer", fvs(&t.buffer)),
                ("theta", fvs(&t.theta)),
                ("phi_used", fvs(&t.phi_used)),
                ("P", fvs(&t.pmat)),
                ("n", iv(t.n)),
            ]),
            Transform::SeasonalScale(t) => obj(vec![
                ("mu_g", fv(t.mu_g)),
                ("var_g", fv(t.var_g)),
                ("mu", fvs(&t.mu)),
                ("var", fvs(&t.var)),
                ("vis", Value::Array(t.vis.iter().map(|&x| iv(x)).collect())),
                ("n", iv(t.n)),
            ]),
            Transform::Gaussianize(t) => obj(vec![
                ("buf", fvs(&t.buf)),
                ("n", iv(t.n as u64)),
                ("mu", fv(t.mu)),
                ("m2", fv(t.m2)),
                (
                    "knots",
                    match &t.knots {
                        None => Value::Null,
                        Some(k) => Value::Array(vec![
                            fvs(&k.cs),
                            fvs(&k.zs),
                            k.ts.as_ref().map(|ts| fvs(ts)).unwrap_or(Value::Null),
                        ]),
                    },
                ),
            ]),
        }
    }

    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            reset_transform(self);
            return Ok(());
        }
        match self {
            Transform::Difference(t) => {
                t.last = gnum(v, "last")?;
                t.init = true;
            }
            Transform::FracDiff(t) => t.buffer = gnums(v, "buffer")?,
            Transform::Standardize(t) => {
                t.mu = gnum(v, "mu")?;
                t.var = gnum(v, "var")?;
                t.init = true;
            }
            Transform::EmaT(t) => {
                t.level = gnum(v, "level")?;
                t.init = true;
            }
            Transform::Ou(t) => {
                t.m = gnum(v, "m")?;
                t.fc = gnum(v, "fc")?;
                t.y = gnum(v, "y")?;
                t.init = true;
            }
            Transform::Theta(t) => {
                t.ses = gnum(v, "ses")?;
                t.t = guint(v, "t")?;
                t.sum_t = gnum(v, "sum_t")?;
                t.sum_t2 = gnum(v, "sum_t2")?;
                t.sum_y = gnum(v, "sum_y")?;
                t.sum_ty = gnum(v, "sum_ty")?;
                t.slope = match v.get("slope") {
                    Some(s) => num(s)?,
                    None => 0.0,
                };
                t.init = true;
            }
            Transform::Drift(t) => {
                t.last = gnum(v, "last")?;
                t.mu = gnum(v, "mu")?;
                t.init = true;
            }
            Transform::Holt(t) => {
                t.level = gnum(v, "level")?;
                t.trend = gnum(v, "trend")?;
                t.init = true;
            }
            Transform::Garch(t) => {
                t.var = gnum(v, "var")?;
                t.last_dev = gnum(v, "last_dev")?;
                t.mu = gnum(v, "mu")?;
                t.init = true;
            }
            Transform::Seasonal(t) => {
                t.buffer = gnums(v, "buffer")?;
                t.init = true;
            }
            Transform::SeasonalAnchor(t) => {
                let ema: Vec<Option<f64>> =
                    garr(v, "ema")?.iter().map(onum).collect::<SResult<_>>()?;
                check_len("seasonal_anchor ema", ema.len(), t.period)?;
                t.ema = ema;
                t.buffer = gnums(v, "buffer")?;
                t.n = guint(v, "n")? as usize;
                t.init = true;
            }
            Transform::Power(_) | Transform::YeoJohnson(_) | Transform::LogT(_) => {}
            Transform::Ar(t) => {
                t.buffer = gnums(v, "buffer")?;
                t.phi = gnums(v, "phi")?;
                check_len("ar phi", t.phi.len(), t.p)?;
                // a pre-#235 checkpoint has no phi_used: derived on first use
                t.phi_used = match v.get("phi_used") {
                    Some(x) => nums(x)?,
                    None => Vec::new(),
                };
                t.pmat = gnums(v, "P")?;
                check_len("ar P", t.pmat.len(), t.p * t.p)?;
                t.n = guint(v, "n")?;
            }
            Transform::GroupedAr(t) => {
                t.buffer = gnums(v, "buffer")?;
                t.theta = gnums(v, "theta")?;
                check_len("grouped_ar theta", t.theta.len(), t.n_groups)?;
                t.phi_used = match v.get("phi_used") {
                    Some(x) => nums(x)?,
                    None => Vec::new(),
                };
                t.pmat = gnums(v, "P")?;
                check_len("grouped_ar P", t.pmat.len(), t.n_groups * t.n_groups)?;
                t.n = guint(v, "n")?;
            }
            Transform::SeasonalScale(t) => {
                t.mu_g = gnum(v, "mu_g")?;
                t.var_g = gnum(v, "var_g")?;
                t.mu = gnums(v, "mu")?;
                t.var = gnums(v, "var")?;
                t.vis = garr(v, "vis")?.iter().map(uint).collect::<SResult<_>>()?;
                check_len("seasonal_scale mu", t.mu.len(), t.period)?;
                check_len("seasonal_scale var", t.var.len(), t.period)?;
                check_len("seasonal_scale vis", t.vis.len(), t.period)?;
                t.n = guint(v, "n")?;
                t.init = true;
            }
            Transform::Gaussianize(t) => {
                t.buf = gnums(v, "buf")?;
                t.n = guint(v, "n")? as usize;
                t.mu = gnum(v, "mu")?;
                t.m2 = gnum(v, "m2")?;
                let k = get(v, "knots")?;
                t.knots = if k.is_null() {
                    None
                } else {
                    let a = arr(k)?;
                    if a.len() != 3 {
                        return Err("gaussianize knots are [cs, zs, ts]".into());
                    }
                    Some(Knots {
                        cs: nums(&a[0])?,
                        zs: nums(&a[1])?,
                        ts: if a[2].is_null() {
                            None
                        } else {
                            Some(nums(&a[2])?)
                        },
                    })
                };
            }
        }
        Ok(())
    }
}

fn reset_transform(t: &mut Transform) {
    match t {
        Transform::Difference(t) => {
            t.last = 0.0;
            t.init = false;
        }
        Transform::FracDiff(t) => t.buffer.clear(),
        Transform::Standardize(t) => {
            t.mu = 0.0;
            t.var = 0.0;
            t.init = false;
        }
        Transform::EmaT(t) => {
            t.level = 0.0;
            t.init = false;
        }
        Transform::Ou(t) => {
            t.m = 0.0;
            t.fc = 0.0;
            t.y = 0.0;
            t.init = false;
        }
        Transform::Theta(t) => {
            t.ses = 0.0;
            t.t = 0;
            t.sum_t = 0.0;
            t.sum_t2 = 0.0;
            t.sum_y = 0.0;
            t.sum_ty = 0.0;
            t.slope = 0.0;
            t.init = false;
        }
        Transform::Drift(t) => {
            t.last = 0.0;
            t.mu = 0.0;
            t.init = false;
        }
        Transform::Holt(t) => {
            t.level = 0.0;
            t.trend = 0.0;
            t.init = false;
        }
        Transform::Garch(t) => {
            t.var = 0.0;
            t.last_dev = 0.0;
            t.mu = 0.0;
            t.init = false;
        }
        Transform::Seasonal(t) => {
            t.buffer.clear();
            t.init = false;
        }
        Transform::SeasonalAnchor(t) => {
            t.ema = vec![None; t.period];
            t.buffer.clear();
            t.n = 0;
            t.init = false;
        }
        Transform::Power(_) | Transform::YeoJohnson(_) | Transform::LogT(_) => {}
        Transform::Ar(t) => {
            t.buffer.clear();
            t.phi = vec![0.0; t.p];
            t.phi_used = vec![0.0; t.p];
            t.pmat = t.init_p();
            t.n = 0;
        }
        Transform::GroupedAr(t) => {
            let ng = t.n_groups;
            t.buffer.clear();
            t.theta = vec![0.0; ng];
            t.phi_used = vec![0.0; t.max_lag];
            t.pmat = vec![0.0; ng * ng];
            for i in 0..ng {
                t.pmat[i * ng + i] = t.ridge;
            }
            t.n = 0;
        }
        Transform::SeasonalScale(t) => {
            t.init = false;
            t.mu_g = 0.0;
            t.var_g = 0.0;
            t.mu = vec![0.0; t.period];
            t.var = vec![0.0; t.period];
            t.vis = vec![0; t.period];
            t.n = 0;
        }
        Transform::Gaussianize(t) => {
            t.buf.clear();
            t.n = 0;
            t.mu = 0.0;
            t.m2 = 0.0;
            t.knots = None;
        }
    }
}

// ---------------------------------------------------------------------------
// leaves
// ---------------------------------------------------------------------------

fn init_w(scales: &[f64]) -> Vec<f64> {
    let mut w = vec![1e-6; scales.len()];
    w[one_idx(scales)] = 1.0;
    w
}

impl State for Leaf {
    fn is_fresh(&self) -> bool {
        self.var.n == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![("var", rv_to_json(&self.var))])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        self.var = if v.is_null() {
            RunningVar::new()
        } else {
            rv_from_json(get(v, "var")?)?
        };
        Ok(())
    }
}

fn mix_leaf_to_json(v: f64, w: &[f64], n: u64) -> Value {
    obj(vec![("v", fv(v)), ("w", fvs(w)), ("n", iv(n))])
}

fn mix_leaf_from_json(val: &Value, scales: &[f64]) -> SResult<(f64, Vec<f64>, u64)> {
    if val.is_null() {
        return Ok((0.0, init_w(scales), 0));
    }
    let w = gnums(val, "w")?;
    check_len("leaf weights", w.len(), scales.len())?;
    Ok((gnum(val, "v")?, w, guint(val, "n")?))
}

impl State for ScaleMixLeaf {
    fn is_fresh(&self) -> bool {
        self.n == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        mix_leaf_to_json(self.v, &self.w, self.n)
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        let (vv, w, n) = mix_leaf_from_json(v, &self.scales)?;
        self.v = vv;
        self.w = w;
        self.n = n;
        Ok(())
    }
}

impl State for CrpsLeaf {
    fn is_fresh(&self) -> bool {
        self.n == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        mix_leaf_to_json(self.v, &self.w, self.n)
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        let (vv, w, n) = mix_leaf_from_json(v, &self.scales)?;
        self.v = vv;
        self.w = w;
        self.n = n;
        Ok(())
    }
}

impl State for GarchLeaf {
    fn is_fresh(&self) -> bool {
        self.n == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("h", fv(self.h)),
            ("s2", fv(self.s2)),
            ("n", iv(self.n)),
            ("omega", fv(self.omega)),
            ("alpha", fv(self.alpha)),
            ("beta", fv(self.beta)),
            ("buf", fvs(&self.buf)),
            ("w", fvs(&self.w)),
            ("last_r2", fv(self.last_r2)),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.h = 0.0;
            self.s2 = 0.0;
            self.n = 0;
            self.omega = 0.0;
            self.alpha = 0.05;
            self.beta = 0.90;
            self.buf.clear();
            self.w = init_w(&self.scales);
            self.last_r2 = 0.0;
            return Ok(());
        }
        self.h = gnum(v, "h")?;
        self.s2 = gnum(v, "s2")?;
        self.n = guint(v, "n")?;
        self.omega = gnum(v, "omega")?;
        self.alpha = gnum(v, "alpha")?;
        self.beta = gnum(v, "beta")?;
        self.buf = gnums(v, "buf")?.into();
        self.w = gnums(v, "w")?;
        check_len("garch_leaf weights", self.w.len(), self.scales.len())?;
        self.last_r2 = gnum(v, "last_r2")?;
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// combinators
// ---------------------------------------------------------------------------

fn conj_to_json(t: &Transform, inner: &dyn StateDyn) -> Value {
    if inner.fresh() {
        return Value::Null;
    }
    obj(vec![
        ("t_state", t.state_to_json()),
        ("s_state", inner.to_json()),
    ])
}

/// Object-safe view of State, so conjugate can wrap an Sk or a Forecaster.
trait StateDyn {
    fn fresh(&self) -> bool;
    fn to_json(&self) -> Value;
    fn load(&mut self, v: &Value) -> SResult<()>;
}

impl<T: State> StateDyn for T {
    fn fresh(&self) -> bool {
        self.is_fresh()
    }
    fn to_json(&self) -> Value {
        self.state_to_json()
    }
    fn load(&mut self, v: &Value) -> SResult<()> {
        self.load_state(v)
    }
}

fn conj_load(t: &mut Transform, inner: &mut dyn StateDyn, v: &Value) -> SResult<()> {
    if v.is_null() {
        t.load_state(&Value::Null)?;
        return inner.load(&Value::Null);
    }
    t.load_state(get(v, "t_state")?)
        .map_err(|e| format!("t_state: {e}"))?;
    inner.load(get(v, "s_state")?)
}

impl State for Conj {
    fn is_fresh(&self) -> bool {
        self.inner.is_fresh()
    }
    fn state_to_json(&self) -> Value {
        conj_to_json(&self.transform, &self.inner)
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        conj_load(&mut self.transform, &mut self.inner, v)
    }
}

impl State for FConj {
    fn is_fresh(&self) -> bool {
        self.inner.is_fresh()
    }
    fn state_to_json(&self) -> Value {
        if self.bare {
            return self.inner.state_to_json();
        }
        conj_to_json(&self.transform, &self.inner)
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if self.bare {
            return self.inner.load_state(v);
        }
        conj_load(&mut self.transform, &mut self.inner, v)
    }
}

fn subs_to_json(subs: &[Sk]) -> Value {
    Value::Array(subs.iter().map(|s| s.state_to_json()).collect())
}

fn subs_load(subs: &mut [Sk], v: &Value) -> SResult<()> {
    let a = arr(v)?;
    check_len("sub", a.len(), subs.len())?;
    for (i, (s, x)) in subs.iter_mut().zip(a.iter()).enumerate() {
        s.load_state(x).map_err(|e| format!("sub[{i}]: {e}"))?;
    }
    Ok(())
}

fn subs_reset(subs: &mut [Sk]) -> SResult<()> {
    for s in subs.iter_mut() {
        s.load_state(&Value::Null)?;
    }
    Ok(())
}

impl State for PwEnsemble {
    fn is_fresh(&self) -> bool {
        self.queues.iter().all(|q| q.iter().all(|x| x.is_empty()))
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("sub", subs_to_json(&self.subs)),
            (
                "queues",
                Value::Array(
                    self.queues
                        .iter()
                        .map(|qi| Value::Array(qi.iter().map(fvs).collect()))
                        .collect(),
                ),
            ),
            (
                "stats",
                Value::Array(
                    self.stats
                        .iter()
                        .map(|si| Value::Array(si.iter().map(rv_to_json).collect()))
                        .collect(),
                ),
            ),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        let (n, k) = (self.subs.len(), self.k);
        if v.is_null() {
            subs_reset(&mut self.subs)?;
            self.queues = vec![vec![VecDeque::new(); k]; n];
            self.stats = vec![vec![RunningVar::new(); k]; n];
            return Ok(());
        }
        subs_load(&mut self.subs, get(v, "sub")?)?;
        self.queues = per_model_horizon(garr(v, "queues")?, n, k, |x| Ok(nums(x)?.into()))?;
        self.stats = per_model_horizon(garr(v, "stats")?, n, k, rv_from_json)?;
        Ok(())
    }
}

fn per_model_horizon<T, F: Fn(&Value) -> SResult<T>>(
    a: &[Value],
    n: usize,
    k: usize,
    f: F,
) -> SResult<Vec<Vec<T>>> {
    check_len("per-model table", a.len(), n)?;
    a.iter()
        .map(|row| {
            let r = arr(row)?;
            check_len("per-horizon table", r.len(), k)?;
            r.iter().map(&f).collect()
        })
        .collect()
}

impl State for BayesEnsemble {
    fn is_fresh(&self) -> bool {
        self.n_obs == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("sub", subs_to_json(&self.subs)),
            (
                "queues",
                Value::Array(
                    self.queues
                        .iter()
                        .map(|qi| Value::Array(qi.iter().map(dists_to_json).collect()))
                        .collect(),
                ),
            ),
            ("log_w", Value::Array(self.log_w.iter().map(fvs).collect())),
            ("n_obs", iv(self.n_obs)),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        let (n, k) = (self.subs.len(), self.k);
        if v.is_null() {
            subs_reset(&mut self.subs)?;
            self.queues = vec![vec![VecDeque::new(); k]; n];
            self.log_w = vec![vec![0.0; k]; n];
            self.n_obs = 0;
            return Ok(());
        }
        subs_load(&mut self.subs, get(v, "sub")?)?;
        self.queues =
            per_model_horizon(garr(v, "queues")?, n, k, |x| Ok(dists_from_json(x)?.into()))?;
        self.log_w = per_model_horizon(garr(v, "log_w")?, n, k, num)?;
        self.n_obs = guint(v, "n_obs")?;
        Ok(())
    }
}

fn adapt_to_json(a: &Adapt) -> Value {
    obj(vec![
        ("log_eta", fv(a.log_eta)),
        ("pit_ewma", fv(a.pit_ewma)),
        ("loss_fast", ofv(a.loss_fast)),
        ("loss_slow", ofv(a.loss_slow)),
        ("pred_q", dists_to_json(&a.pred_q)),
    ])
}

fn adapt_from_json(v: &Value) -> SResult<Adapt> {
    Ok(Adapt {
        log_eta: gnum(v, "log_eta")?,
        pit_ewma: gnum(v, "pit_ewma")?,
        loss_fast: onum(get(v, "loss_fast")?)?,
        loss_slow: onum(get(v, "loss_slow")?)?,
        pred_q: dists_from_json(get(v, "pred_q")?)?.into(),
    })
}

impl State for TerminalEnsemble {
    fn is_fresh(&self) -> bool {
        self.qdist.iter().all(|q| q.is_empty())
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("sub", subs_to_json(&self.subs)),
            (
                "qdist",
                Value::Array(self.qdist.iter().map(dists_to_json).collect()),
            ),
            ("log_w", fvs(&self.log_w)),
            (
                "leaf_state",
                Value::Array(self.tleafs.iter().map(|l| l.state_to_json()).collect()),
            ),
            (
                "leaf_pred",
                Value::Array(self.leaf_pred.iter().map(odist_to_json).collect()),
            ),
            (
                "mean_q",
                Value::Array(self.mean_q.iter().map(fvs).collect()),
            ),
            (
                "adapt",
                self.adapt
                    .as_ref()
                    .map(adapt_to_json)
                    .unwrap_or(Value::Null),
            ),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        let (n, k) = (self.subs.len(), self.k);
        if v.is_null() {
            subs_reset(&mut self.subs)?;
            self.qdist = vec![VecDeque::new(); n];
            self.log_w = if self.prior_log_weights.len() == n {
                self.prior_log_weights.clone()
            } else {
                vec![0.0; n]
            };
            subs_reset(&mut self.tleafs)?;
            self.leaf_pred = vec![None; k];
            self.mean_q = vec![VecDeque::new(); k];
            self.adapt = if self.adaptive_temperature {
                Some(Adapt::new(self.learning_rate))
            } else {
                None
            };
            return Ok(());
        }
        subs_load(&mut self.subs, get(v, "sub")?)?;
        let q = garr(v, "qdist")?;
        check_len("qdist", q.len(), n)?;
        self.qdist = q
            .iter()
            .map(|x| Ok(dists_from_json(x)?.into()))
            .collect::<SResult<_>>()?;
        self.log_w = gnums(v, "log_w")?;
        check_len("log_w", self.log_w.len(), n)?;
        subs_load(&mut self.tleafs, get(v, "leaf_state")?)
            .map_err(|e| format!("leaf_state: {e}"))?;
        let lp = garr(v, "leaf_pred")?;
        check_len("leaf_pred", lp.len(), k)?;
        self.leaf_pred = lp.iter().map(odist_from_json).collect::<SResult<_>>()?;
        let mq = garr(v, "mean_q")?;
        check_len("mean_q", mq.len(), k)?;
        self.mean_q = mq
            .iter()
            .map(|x| Ok(nums(x)?.into()))
            .collect::<SResult<_>>()?;
        // an old JS checkpoint has no "adapt"; the ensemble starts it afresh
        let ad = v.get("adapt").unwrap_or(&Value::Null);
        self.adapt = if ad.is_null() {
            if self.adaptive_temperature {
                Some(Adapt::new(self.learning_rate))
            } else {
                None
            }
        } else {
            Some(adapt_from_json(ad)?)
        };
        Ok(())
    }
}

impl State for Multiscale {
    fn is_fresh(&self) -> bool {
        self.t == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        let mut phase = Map::new();
        let mut pending = Map::new();
        let mut latest = Map::new();
        let mut score = Map::new();
        for (si, &s) in self.scales.iter().enumerate() {
            let ks = s.to_string();
            phase.insert(
                ks.clone(),
                Value::Array(self.phase[si].iter().map(|p| p.state_to_json()).collect()),
            );
            pending.insert(
                ks.clone(),
                Value::Array(self.pending[si].iter().map(odist_to_json).collect()),
            );
            if let Some(l) = &self.latest[si] {
                latest.insert(ks.clone(), dists_to_json(l));
            }
            score.insert(ks, ofv(self.score[si]));
        }
        obj(vec![
            ("t", iv(self.t)),
            ("phase", Value::Object(phase)),
            ("pending", Value::Object(pending)),
            ("latest", Value::Object(latest)),
            ("score", Value::Object(score)),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        let ns = self.scales.len();
        if v.is_null() {
            for ph in self.phase.iter_mut() {
                subs_reset(ph)?;
            }
            self.pending = self.scales.iter().map(|&s| vec![None; s]).collect();
            self.latest = vec![None; ns];
            self.score = vec![None; ns];
            self.t = 0;
            return Ok(());
        }
        self.t = guint(v, "t")?;
        let (phase, pending, latest, score) = (
            get(v, "phase")?,
            get(v, "pending")?,
            get(v, "latest")?,
            get(v, "score")?,
        );
        for si in 0..ns {
            let ks = self.scales[si].to_string();
            subs_load(&mut self.phase[si], get(phase, &ks)?)
                .map_err(|e| format!("multiscale phase {ks}: {e}"))?;
            let p = arr(get(pending, &ks)?)?;
            check_len("multiscale pending", p.len(), self.scales[si])?;
            self.pending[si] = p.iter().map(odist_from_json).collect::<SResult<_>>()?;
            self.latest[si] = match latest.get(&ks) {
                None | Some(Value::Null) => None,
                Some(x) => Some(dists_from_json(x)?),
            };
            self.score[si] = onum(get(score, &ks)?)?;
        }
        Ok(())
    }
}

impl State for Sticky {
    fn is_fresh(&self) -> bool {
        self.counts.is_empty()
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("base", self.base.state_to_json()),
            (
                "counts",
                Value::Array(
                    self.counts
                        .iter()
                        .map(|&(v, w)| Value::Array(vec![fv(v), fv(w)]))
                        .collect(),
                ),
            ),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.counts.clear();
            return self.base.load_state(&Value::Null);
        }
        self.base.load_state(get(v, "base")?)?;
        let c = get(v, "counts")?;
        self.counts = match c {
            // a JS-era or hand-written table keyed by value
            Value::Object(m) => m
                .iter()
                .map(|(k, w)| {
                    Ok((
                        k.parse::<f64>()
                            .map_err(|_| format!("bad sticky key {k}"))?,
                        num(w)?,
                    ))
                })
                .collect::<SResult<_>>()?,
            _ => arr(c)?
                .iter()
                .map(|p| {
                    let t = nums(p)?;
                    if t.len() != 2 {
                        return Err("a sticky count is [value, weight]".to_string());
                    }
                    Ok((t[0], t[1]))
                })
                .collect::<SResult<_>>()?,
        };
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// search / dantzig and the period detector
// ---------------------------------------------------------------------------

impl State for PeriodDetector {
    fn is_fresh(&self) -> bool {
        self.n == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        let mut cross = Map::new();
        for (li, &lag) in self.lags.iter().enumerate() {
            cross.insert(lag.to_string(), fv(self.cross[li]));
        }
        obj(vec![
            ("buffer", fvs(&self.buffer)),
            ("n", iv(self.n)),
            ("mean", fv(self.mean)),
            ("var", fv(self.var)),
            ("cross", Value::Object(cross)),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.buffer.clear();
            self.n = 0;
            self.mean = 0.0;
            self.var = 0.0;
            self.cross = vec![0.0; self.lags.len()];
            return Ok(());
        }
        self.buffer = gnums(v, "buffer")?.into();
        self.n = guint(v, "n")?;
        self.mean = gnum(v, "mean")?;
        self.var = gnum(v, "var")?;
        let c = get(v, "cross")?;
        for (li, &lag) in self.lags.iter().enumerate() {
            self.cross[li] = gnum(c, &lag.to_string())?;
        }
        Ok(())
    }
}

fn grammar_for(detected: &[usize]) -> Vec<GrammarEntry> {
    let mut t = base_transforms();
    for &p in detected {
        t.push(GrammarEntry {
            name: format!("seas({p})"),
            op: GrammarOp::Seas(p),
            cost: 2.0,
        });
    }
    t
}

fn entry_to_json(e: &SearchEntry) -> Value {
    obj(vec![
        ("s", e.sk.state_to_json()),
        ("depth", iv(e.depth as u64)),
        (
            "recipe",
            Value::Array(e.recipe.iter().map(|r| Value::String(r.clone())).collect()),
        ),
        ("cost", fv(e.cost)),
        ("age", iv(e.age)),
        ("warmed", Value::Bool(e.warmed)),
        ("log_w", fvs(&e.log_w)),
        (
            "queues",
            Value::Array(e.queues.iter().map(dists_to_json).collect()),
        ),
        (
            "dists",
            if e.dists.is_empty() {
                Value::Null
            } else {
                dists_to_json(&e.dists)
            },
        ),
    ])
}

fn entry_from_json(v: &Value, k: usize, grammar: &[GrammarEntry]) -> SResult<SearchEntry> {
    let recipe: Vec<String> = garr(v, "recipe")?
        .iter()
        .map(|r| {
            r.as_str()
                .map(str::to_string)
                .ok_or_else(|| "a recipe is a list of transform names".to_string())
        })
        .collect::<SResult<_>>()?;
    for r in &recipe {
        if !grammar.iter().any(|g| &g.name == r) {
            return Err(format!("search recipe names unknown transform {r:?}"));
        }
    }
    let mut sk = build_from_recipe(&recipe, k, grammar);
    sk.load_state(get(v, "s")?)?;
    let log_w = gnums(v, "log_w")?;
    check_len("search log_w", log_w.len(), k)?;
    let q = garr(v, "queues")?;
    check_len("search queues", q.len(), k)?;
    let d = get(v, "dists")?;
    Ok(SearchEntry {
        sk,
        depth: guint(v, "depth")? as usize,
        recipe,
        cost: gnum(v, "cost")?,
        age: guint(v, "age")?,
        warmed: get(v, "warmed")?
            .as_bool()
            .ok_or("search warmed must be a bool")?,
        log_w,
        queues: q
            .iter()
            .map(|x| Ok(dists_from_json(x)?.into()))
            .collect::<SResult<_>>()?,
        dists: if d.is_null() {
            Vec::new()
        } else {
            dists_from_json(d)?
        },
    })
}

impl State for Search {
    fn is_fresh(&self) -> bool {
        self.n_obs == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            (
                "pool",
                Value::Array(self.pool.iter().map(entry_to_json).collect()),
            ),
            ("n_obs", iv(self.n_obs)),
            ("buffer", fvs(&self.buffer)),
            ("pd_state", self.pd.state_to_json()),
            (
                "detected_periods",
                Value::Array(
                    self.detected_periods
                        .iter()
                        .map(|&p| iv(p as u64))
                        .collect(),
                ),
            ),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.pool.clear();
            self.n_obs = 0;
            self.buffer.clear();
            self.pd.load_state(&Value::Null)?;
            self.detected_periods.clear();
            self.transforms = base_transforms();
            return Ok(());
        }
        self.detected_periods = garr(v, "detected_periods")?
            .iter()
            .map(|x| uint(x).map(|u| u as usize))
            .collect::<SResult<_>>()?;
        self.transforms = grammar_for(&self.detected_periods);
        self.pool = garr(v, "pool")?
            .iter()
            .enumerate()
            .map(|(i, e)| {
                entry_from_json(e, self.k, &self.transforms).map_err(|e| format!("pool[{i}]: {e}"))
            })
            .collect::<SResult<_>>()?;
        self.n_obs = guint(v, "n_obs")?;
        self.buffer = gnums(v, "buffer")?.into();
        self.pd.load_state(get(v, "pd_state")?)?;
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Sk
// ---------------------------------------------------------------------------

impl State for Sk {
    fn is_fresh(&self) -> bool {
        match self {
            Sk::Leaf(s) => s.is_fresh(),
            Sk::ScaleMix(s) => s.is_fresh(),
            Sk::Crps(s) => s.is_fresh(),
            Sk::GarchLeaf(s) => s.is_fresh(),
            Sk::Conj(s) => s.is_fresh(),
            Sk::Pw(s) => s.is_fresh(),
            Sk::Bayes(s) => s.is_fresh(),
            Sk::Terminal(s) => s.is_fresh(),
            Sk::Multiscale(s) => s.is_fresh(),
            Sk::Sticky(s) => s.is_fresh(),
            Sk::Search(s) => s.is_fresh(),
        }
    }
    fn state_to_json(&self) -> Value {
        match self {
            Sk::Leaf(s) => s.state_to_json(),
            Sk::ScaleMix(s) => s.state_to_json(),
            Sk::Crps(s) => s.state_to_json(),
            Sk::GarchLeaf(s) => s.state_to_json(),
            Sk::Conj(s) => s.state_to_json(),
            Sk::Pw(s) => s.state_to_json(),
            Sk::Bayes(s) => s.state_to_json(),
            Sk::Terminal(s) => s.state_to_json(),
            Sk::Multiscale(s) => s.state_to_json(),
            Sk::Sticky(s) => s.state_to_json(),
            Sk::Search(s) => s.state_to_json(),
        }
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        match self {
            Sk::Leaf(s) => s.load_state(v),
            Sk::ScaleMix(s) => s.load_state(v),
            Sk::Crps(s) => s.load_state(v),
            Sk::GarchLeaf(s) => s.load_state(v),
            Sk::Conj(s) => s.load_state(v),
            Sk::Pw(s) => s.load_state(v),
            Sk::Bayes(s) => s.load_state(v),
            Sk::Terminal(s) => s.load_state(v),
            Sk::Multiscale(s) => s.load_state(v),
            Sk::Sticky(s) => s.load_state(v),
            Sk::Search(s) => s.load_state(v),
        }
    }
}

// ---------------------------------------------------------------------------
// GPD tails and the parade
// ---------------------------------------------------------------------------

fn tail_to_json(t: &Tail) -> Value {
    obj(vec![
        ("t", ofv(t.t)),
        ("exc", fvs(&t.exc)),
        ("s1", fv(t.s1)),
        ("nx", iv(t.nx)),
        ("r", fv(t.r)),
        ("g", fv(t.g)),
        ("s", fv(t.s)),
        ("since", iv(t.since)),
        ("run", iv(t.run)),
    ])
}

fn tail_from_json(v: &Value) -> SResult<Tail> {
    Ok(Tail {
        t: onum(get(v, "t")?)?,
        exc: gnums(v, "exc")?,
        s1: gnum(v, "s1")?,
        nx: guint(v, "nx")?,
        r: gnum(v, "r")?,
        g: gnum(v, "g")?,
        s: gnum(v, "s")?,
        since: guint(v, "since")?,
        run: guint(v, "run")?,
    })
}

fn tail_fresh() -> Tail {
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

impl State for GpdTails {
    fn is_fresh(&self) -> bool {
        self.pending.is_empty()
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("base", self.base.state_to_json()),
            (
                "pending",
                Value::Array(self.pending.iter().map(|p| dists_to_json(p)).collect()),
            ),
            (
                "tails",
                Value::Array(
                    self.tails
                        .iter()
                        .map(|h| {
                            obj(vec![
                                ("up", tail_to_json(&h.up)),
                                ("lo", tail_to_json(&h.lo)),
                                ("warm", fvs(&h.warm)),
                                ("n", Value::from(h.n)),
                                ("skipped", iv(h.skipped as u64)),
                            ])
                        })
                        .collect(),
                ),
            ),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.pending.clear();
            for h in self.tails.iter_mut() {
                *h = HorizonTail {
                    up: tail_fresh(),
                    lo: tail_fresh(),
                    warm: Vec::new(),
                    n: 0,
                    skipped: 0,
                };
            }
            return self.base.load_state(&Value::Null);
        }
        self.base.load_state(get(v, "base")?)?;
        self.pending = garr(v, "pending")?
            .iter()
            .map(dists_from_json)
            .collect::<SResult<_>>()?;
        let t = garr(v, "tails")?;
        check_len("gpdtails tails", t.len(), self.k)?;
        self.tails = t
            .iter()
            .map(|h| {
                Ok(HorizonTail {
                    up: tail_from_json(get(h, "up")?)?,
                    lo: tail_from_json(get(h, "lo")?)?,
                    warm: gnums(h, "warm")?,
                    n: sint(get(h, "n")?)?,
                    skipped: match h.get("skipped") {
                        Some(x) => uint(x)? as usize,
                        None => 0,
                    },
                })
            })
            .collect::<SResult<_>>()?;
        Ok(())
    }
}

impl State for ParadeBase {
    fn is_fresh(&self) -> bool {
        match self {
            ParadeBase::Sk(s) => s.is_fresh(),
            ParadeBase::Gpd(g) => g.is_fresh(),
        }
    }
    fn state_to_json(&self) -> Value {
        match self {
            ParadeBase::Sk(s) => s.state_to_json(),
            ParadeBase::Gpd(g) => g.state_to_json(),
        }
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        match self {
            ParadeBase::Sk(s) => s.load_state(v),
            ParadeBase::Gpd(g) => g.load_state(v),
        }
    }
}

impl State for Parade {
    fn is_fresh(&self) -> bool {
        self.pending.is_empty() && self.skipped == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("base", self.base.state_to_json()),
            (
                "pending",
                Value::Array(self.pending.iter().map(|p| pdists_to_json(p)).collect()),
            ),
            (
                "pit",
                Value::Array(self.pit.iter().map(|&x| ofv(x)).collect()),
            ),
            ("z", Value::Array(self.z.iter().map(|&x| ofv(x)).collect())),
            ("skipped", iv(self.skipped)),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        let k = self.k;
        if v.is_null() {
            self.pending.clear();
            self.pit = vec![None; k];
            self.z = vec![None; k];
            self.skipped = 0;
            return self.base.load_state(&Value::Null);
        }
        self.base.load_state(get(v, "base")?)?;
        self.pending = garr(v, "pending")?
            .iter()
            .map(pdists_from_json)
            .collect::<SResult<_>>()?;
        self.pit = garr(v, "pit")?.iter().map(onum).collect::<SResult<_>>()?;
        self.z = garr(v, "z")?.iter().map(onum).collect::<SResult<_>>()?;
        check_len("parade pit", self.pit.len(), k)?;
        check_len("parade z", self.z.len(), k)?;
        self.skipped = match v.get("skipped") {
            Some(x) => uint(x)?,
            None => 0,
        };
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// homogenize and residual_transform
// ---------------------------------------------------------------------------

fn correction_to_json(c: &Correction) -> Value {
    obj(vec![
        ("weights", fvs(&c.weights)),
        ("scales", fvs(&c.scales)),
    ])
}

fn correction_from_json(v: &Value) -> SResult<Option<Correction>> {
    if v.is_null() {
        return Ok(None);
    }
    let c = Correction {
        weights: gnums(v, "weights")?,
        scales: gnums(v, "scales")?,
    };
    check_len("correction scales", c.scales.len(), c.weights.len())?;
    Ok(Some(c))
}

fn cell_to_json(c: &Cell) -> Value {
    obj(vec![
        (
            "dynamic",
            Value::Array(
                c.dynamic
                    .iter()
                    .map(|d| {
                        obj(vec![
                            ("q", fv(d.q)),
                            ("log_weight", fv(d.log_weight)),
                            ("guard_run", iv(d.guard_run)),
                        ])
                    })
                    .collect(),
            ),
        ),
        (
            "issued",
            c.issued
                .as_ref()
                .map(correction_to_json)
                .unwrap_or(Value::Null),
        ),
        ("n", iv(c.n)),
    ])
}

fn cell_from_json(v: &Value, n_cand: usize) -> SResult<Option<Cell>> {
    if v.is_null() {
        return Ok(None);
    }
    let d = garr(v, "dynamic")?;
    check_len("homogenize dynamic", d.len(), n_cand)?;
    Ok(Some(Cell {
        dynamic: d
            .iter()
            .map(|x| {
                Ok(CandState {
                    q: gnum(x, "q")?,
                    log_weight: gnum(x, "log_weight")?,
                    guard_run: guint(x, "guard_run")?,
                })
            })
            .collect::<SResult<_>>()?,
        issued: correction_from_json(v.get("issued").unwrap_or(&Value::Null))?,
        n: guint(v, "n")?,
    }))
}

impl State for Homogenize {
    fn is_fresh(&self) -> bool {
        self.pending.is_empty()
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("base", self.inner.state_to_json()),
            (
                "raw",
                self.raw.as_ref().map(pdist_to_json).unwrap_or(Value::Null),
            ),
            (
                "pending",
                Value::Array(self.pending.iter().map(|p| pdists_to_json(p)).collect()),
            ),
            (
                "cell",
                Value::Array(
                    self.cell
                        .iter()
                        .map(|c| c.as_ref().map(cell_to_json).unwrap_or(Value::Null))
                        .collect(),
                ),
            ),
            (
                "correction",
                Value::Array(
                    self.correction
                        .iter()
                        .map(|c| c.as_ref().map(correction_to_json).unwrap_or(Value::Null))
                        .collect(),
                ),
            ),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.reset();
            return self.inner.load_state(&Value::Null);
        }
        let k = self.k;
        let nc = self.candidates.len();
        self.inner.load_state(get(v, "base")?)?;
        self.raw = opdist_from_json(get(v, "raw")?)?;
        self.pending = garr(v, "pending")?
            .iter()
            .map(pdists_from_json)
            .collect::<SResult<_>>()?;
        let c = garr(v, "cell")?;
        check_len("homogenize cell", c.len(), k)?;
        self.cell = c
            .iter()
            .map(|x| cell_from_json(x, nc))
            .collect::<SResult<_>>()?;
        let c = garr(v, "correction")?;
        check_len("homogenize correction", c.len(), k)?;
        self.correction = c.iter().map(correction_from_json).collect::<SResult<_>>()?;
        Ok(())
    }
}

fn learner_to_json(l: &Learner) -> Value {
    let mut p = vec![
        ("ell", fv(l.ell)),
        ("a", fv(l.a)),
        ("c", fv(l.c)),
        ("ea", fv(l.ea)),
        ("ec", fv(l.ec)),
        ("g2a", fv(l.g2a)),
        ("g2c", fv(l.g2c)),
    ];
    if let (Some(b), Some(eb), Some(g2b)) = (l.b, l.eb, l.g2b) {
        p.push(("b", fv(b)));
        p.push(("eb", fv(eb)));
        p.push(("g2b", fv(g2b)));
    }
    obj(p)
}

fn learner_from_json(v: &Value, learn_b: bool) -> SResult<Learner> {
    let opt = |k: &str| -> SResult<Option<f64>> {
        match v.get(k) {
            Some(x) => num(x).map(Some),
            None if learn_b => Err(format!("state is missing key {k:?}")),
            None => Ok(None),
        }
    };
    Ok(Learner {
        ell: gnum(v, "ell")?,
        a: gnum(v, "a")?,
        c: gnum(v, "c")?,
        ea: gnum(v, "ea")?,
        ec: gnum(v, "ec")?,
        g2a: gnum(v, "g2a")?,
        g2c: gnum(v, "g2c")?,
        b: opt("b")?,
        eb: opt("eb")?,
        g2b: opt("g2b")?,
    })
}

fn theta_to_json(t: &ResidualTheta) -> Value {
    let mut p = vec![("m", fv(t.m)), ("ell", fv(t.ell))];
    if let Some(a) = t.a {
        p.push(("a", fv(a)));
    }
    if let Some(c) = t.c {
        p.push(("c", fv(c)));
    }
    if let Some(b) = t.b {
        p.push(("b", fv(b)));
    }
    obj(p)
}

impl State for ResidualTransform {
    fn is_fresh(&self) -> bool {
        self.raw.is_none()
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        obj(vec![
            ("base", self.inner.state_to_json()),
            (
                "raw",
                self.raw.as_ref().map(pdist_to_json).unwrap_or(Value::Null),
            ),
            ("z", ofv(self.z)),
            (
                "learner",
                self.learner
                    .as_ref()
                    .map(learner_to_json)
                    .unwrap_or(Value::Null),
            ),
            ("theta", theta_to_json(&self.theta)),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.reset_own();
            return self.inner.load_state(&Value::Null);
        }
        self.inner.load_state(get(v, "base")?)?;
        self.raw = opdist_from_json(get(v, "raw")?)?;
        self.z = onum(get(v, "z")?)?;
        let l = get(v, "learner")?;
        self.learner = if self.model == "m0" || l.is_null() {
            None
        } else {
            Some(learner_from_json(l, self.model == "m2")?)
        };
        // theta is derived from the learner; recomputed rather than read
        self.theta = theta_of(&self.model, self.learner.as_ref());
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Forecaster and granger
// ---------------------------------------------------------------------------

impl State for Forecaster {
    fn is_fresh(&self) -> bool {
        match self {
            Forecaster::Sk(s) => s.is_fresh(),
            Forecaster::Gpd(g) => g.is_fresh(),
            Forecaster::Parade(p) => p.is_fresh(),
            Forecaster::Conj(c) => c.is_fresh(),
            Forecaster::Homog(h) => h.is_fresh(),
            Forecaster::Residual(r) => r.is_fresh(),
        }
    }
    fn state_to_json(&self) -> Value {
        match self {
            Forecaster::Sk(s) => s.state_to_json(),
            Forecaster::Gpd(g) => g.state_to_json(),
            Forecaster::Parade(p) => p.state_to_json(),
            Forecaster::Conj(c) => c.state_to_json(),
            Forecaster::Homog(h) => h.state_to_json(),
            Forecaster::Residual(r) => r.state_to_json(),
        }
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        match self {
            Forecaster::Sk(s) => s.load_state(v),
            Forecaster::Gpd(g) => g.load_state(v),
            Forecaster::Parade(p) => p.load_state(v),
            Forecaster::Conj(c) => c.load_state(v),
            Forecaster::Homog(h) => h.load_state(v),
            Forecaster::Residual(r) => r.load_state(v),
        }
    }
}

impl State for Granger {
    fn is_fresh(&self) -> bool {
        self.t == 0
    }
    fn state_to_json(&self) -> Value {
        if self.is_fresh() {
            return Value::Null;
        }
        let pend = match &self.pend {
            None => Value::Array(vec![]),
            Some((a, b)) => Value::Array(vec![Value::Array(vec![
                Value::Array(vec![pdist_to_json(a)]),
                Value::Array(vec![pdist_to_json(b)]),
            ])]),
        };
        obj(vec![
            ("lap", self.lap.state_to_json()),
            ("learned", self.expert.state_to_json()),
            ("pend", pend),
            (
                "cum",
                Value::Array(vec![Value::Array(vec![fvs(&self.cum)])]),
            ),
            ("t", iv(self.t)),
            ("z", Value::Array(vec![ofv(self.z)])),
            ("repeat_frac", fv(self.repeat_frac)),
            ("abs_z_mean", fv(self.abs_z_mean)),
            ("n", iv(self.n)),
            ("last_y", ofv(self.last_y)),
        ])
    }
    fn load_state(&mut self, v: &Value) -> SResult<()> {
        if v.is_null() {
            self.lap.load_state(&Value::Null)?;
            self.expert.load_state(&Value::Null)?;
            self.pend = None;
            self.cum = [0.0, 0.0];
            self.t = 0;
            self.z = None;
            self.repeat_frac = 0.0;
            self.abs_z_mean = 0.0;
            self.n = 0;
            self.last_y = None;
            return Ok(());
        }
        self.lap.load_state(get(v, "lap")?)?;
        self.expert.load_state(get(v, "learned")?)?;
        let pend = garr(v, "pend")?;
        self.pend = match pend.last() {
            None => None,
            Some(p) => {
                let pair = arr(p)?;
                if pair.len() != 2 {
                    return Err("a granger pend entry is [laplace, learned]".into());
                }
                let a = pdists_from_json(&pair[0])?;
                let b = pdists_from_json(&pair[1])?;
                if a.is_empty() || b.is_empty() {
                    return Err("granger pend entries need one predictive per horizon".into());
                }
                Some((a[0].clone(), b[0].clone()))
            }
        };
        let cum = arr(&garr(v, "cum")?[0])?;
        let c = nums(&cum[0])?;
        check_len("granger cum", c.len(), 2)?;
        self.cum = [c[0], c[1]];
        self.t = guint(v, "t")?;
        let z = garr(v, "z")?;
        self.z = match z.first() {
            None => None,
            Some(x) => onum(x)?,
        };
        self.repeat_frac = gnum(v, "repeat_frac")?;
        self.abs_z_mean = gnum(v, "abs_z_mean")?;
        self.n = guint(v, "n")?;
        self.last_y = onum(get(v, "last_y")?)?;
        Ok(())
    }
}
