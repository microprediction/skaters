//! Symbolic specification for skater pipelines. Port of src/skaters/spec.py.
//!
//! A spec is plain data that fully describes how to build a skater. It
//! serializes to the same JSON shape as the Python dicts (an "op" tag),
//! hashes, compares, and materializes into a live skater via `build`.
//!
//! Grammar:
//!
//! ```text
//! spec := leaf(k) | ema(alpha, k) | ensemble(k, skaters) | conjugate(skater, transform)
//! transform_spec := diff | frac(d, window) | std(alpha) | ema_t(alpha)
//! ```

use crate::leaf::Leaf;
use crate::skater::{conjugate, ema, precision_weighted_ensemble, Sk};
use crate::transform::{difference, ema_transform, fractional_difference, standardize, Transform};
use serde::{Deserialize, Serialize};

fn default_window() -> usize {
    50
}

fn default_std_alpha() -> f64 {
    0.05
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "op")]
pub enum Spec {
    #[serde(rename = "leaf")]
    Leaf { k: usize },
    #[serde(rename = "ema")]
    Ema { alpha: f64, k: usize },
    #[serde(rename = "ensemble")]
    Ensemble {
        k: usize,
        skaters: Vec<Spec>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        floor: Option<f64>,
    },
    #[serde(rename = "conjugate")]
    Conjugate {
        skater: Box<Spec>,
        transform: TransformSpec,
    },
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "op")]
pub enum TransformSpec {
    #[serde(rename = "diff")]
    Diff,
    #[serde(rename = "frac")]
    Frac {
        d: f64,
        #[serde(default = "default_window")]
        window: usize,
    },
    #[serde(rename = "std")]
    Std {
        #[serde(default = "default_std_alpha")]
        alpha: f64,
    },
    #[serde(rename = "ema_t")]
    EmaT { alpha: f64 },
}

// ---------------------------------------------------------------------------
// Build: spec -> live skater
// ---------------------------------------------------------------------------

/// Materialize a spec into a live skater.
pub fn build(spec: &Spec) -> Sk {
    match spec {
        Spec::Leaf { k } => Sk::Leaf(Leaf::new(*k)),
        Spec::Ema { alpha, k } => ema(*alpha, *k),
        Spec::Ensemble { k, skaters, floor } => {
            let subs: Vec<Sk> = skaters.iter().map(build).collect();
            let mut f = precision_weighted_ensemble(subs, *k);
            if let (Sk::Pw(pw), Some(fl)) = (&mut f, floor) {
                pw.floor = *fl;
            }
            f
        }
        Spec::Conjugate { skater, transform } => {
            let inner = build(skater);
            let t = build_transform(transform);
            conjugate(inner, t, infer_k(skater))
        }
    }
}

fn build_transform(spec: &TransformSpec) -> Transform {
    match spec {
        TransformSpec::Diff => difference(),
        TransformSpec::Frac { d, window } => fractional_difference(*d, *window),
        TransformSpec::Std { alpha } => standardize(*alpha, 1e-8),
        TransformSpec::EmaT { alpha } => ema_transform(*alpha),
    }
}

/// Walk the spec tree to find k.
pub fn infer_k(spec: &Spec) -> usize {
    match spec {
        Spec::Leaf { k } | Spec::Ema { k, .. } | Spec::Ensemble { k, .. } => *k,
        Spec::Conjugate { skater, .. } => infer_k(skater),
    }
}

// ---------------------------------------------------------------------------
// Name: spec -> canonical string
// ---------------------------------------------------------------------------

/// Derive a canonical, deterministic name from a spec.
pub fn name(spec: &Spec) -> String {
    match spec {
        Spec::Leaf { .. } => "leaf".to_string(),
        Spec::Ema { alpha, .. } => format!("ema({})", fmt_num(*alpha)),
        Spec::Ensemble { skaters, .. } => {
            let inner: Vec<String> = skaters.iter().map(name).collect();
            format!("ensemble({})", inner.join(","))
        }
        Spec::Conjugate { skater, transform } => {
            format!("{}|{}", transform_name(transform), name(skater))
        }
    }
}

fn transform_name(spec: &TransformSpec) -> String {
    match spec {
        TransformSpec::Diff => "diff".to_string(),
        TransformSpec::Frac { d, window } => {
            if *window == 50 {
                format!("frac({})", fmt_num(*d))
            } else {
                format!("frac({},w={})", fmt_num(*d), window)
            }
        }
        TransformSpec::Std { alpha } => format!("std({})", fmt_num(*alpha)),
        TransformSpec::EmaT { alpha } => format!("ema_t({})", fmt_num(*alpha)),
    }
}

/// Format a float compactly: integers plain, otherwise Python's `%.6g`.
fn fmt_num(x: f64) -> String {
    if x == libm::trunc(x) && x.abs() < 9.0e15 {
        return format!("{}", x as i64);
    }
    fmt_g6(x)
}

/// Python `f"{x:.6g}"`: 6 significant digits, trailing zeros stripped,
/// scientific notation when the decimal exponent is < -4 or >= 6.
fn fmt_g6(x: f64) -> String {
    let sci = format!("{:.5e}", x);
    let (mant, exp) = sci.split_once('e').expect("exponent");
    let exp: i32 = exp.parse().expect("exponent parse");
    if !(-4..6).contains(&exp) {
        let mant = mant.trim_end_matches('0').trim_end_matches('.');
        format!("{}e{}{:02}", mant, if exp < 0 { "-" } else { "+" }, exp.abs())
    } else {
        let prec = (5 - exp).max(0) as usize;
        let fixed = format!("{:.*}", prec, x);
        if fixed.contains('.') {
            fixed.trim_end_matches('0').trim_end_matches('.').to_string()
        } else {
            fixed
        }
    }
}

// ---------------------------------------------------------------------------
// Serialization
// ---------------------------------------------------------------------------

/// Serialize a spec to compact JSON (same separators as Python).
pub fn to_json(spec: &Spec) -> String {
    serde_json::to_string(spec).expect("spec serializes")
}

/// Deserialize a spec from JSON.
pub fn from_json(s: &str) -> Result<Spec, serde_json::Error> {
    serde_json::from_str(s)
}

// ---------------------------------------------------------------------------
// Spec constructors (convenience)
// ---------------------------------------------------------------------------

pub fn leaf_spec(k: usize) -> Spec {
    Spec::Leaf { k }
}

pub fn ema_spec(alpha: f64, k: usize) -> Spec {
    Spec::Ema { alpha, k }
}

pub fn ensemble_spec(skaters: Vec<Spec>, k: usize) -> Spec {
    Spec::Ensemble {
        k,
        skaters,
        floor: None,
    }
}

pub fn conjugate_spec(skater: Spec, transform: TransformSpec) -> Spec {
    Spec::Conjugate {
        skater: Box::new(skater),
        transform,
    }
}

pub fn diff_spec() -> TransformSpec {
    TransformSpec::Diff
}

pub fn frac_spec(d: f64, window: usize) -> TransformSpec {
    TransformSpec::Frac { d, window }
}

pub fn std_spec(alpha: f64) -> TransformSpec {
    TransformSpec::Std { alpha }
}

pub fn ema_t_spec(alpha: f64) -> TransformSpec {
    TransformSpec::EmaT { alpha }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_names() {
        let spec = conjugate_spec(
            ensemble_spec(vec![ema_spec(0.01, 1), ema_spec(0.1, 1)], 1),
            diff_spec(),
        );
        assert_eq!(name(&spec), "diff|ensemble(ema(0.01),ema(0.1))");
        assert_eq!(name(&ema_spec(0.05, 1)), "ema(0.05)");
        assert_eq!(
            name(&conjugate_spec(leaf_spec(1), frac_spec(0.4, 30))),
            "frac(0.4,w=30)|leaf"
        );
        assert_eq!(
            name(&conjugate_spec(leaf_spec(1), std_spec(0.05))),
            "std(0.05)|leaf"
        );
        // %.6g cases as CPython renders them
        assert_eq!(fmt_g6(0.0000001), "1e-07");
        assert_eq!(fmt_g6(1234560.0), "1.23456e+06");
        assert_eq!(fmt_g6(0.123456789), "0.123457");
    }

    #[test]
    fn json_roundtrip() {
        let spec = conjugate_spec(
            ensemble_spec(vec![ema_spec(0.01, 1), ema_spec(0.1, 1)], 1),
            diff_spec(),
        );
        let s = to_json(&spec);
        assert_eq!(from_json(&s).unwrap(), spec);
        assert!(s.starts_with("{\"op\":\"conjugate\""));
    }
}
