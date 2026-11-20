//! Scenario builders shared by the parity and resume gates. Every name in
//! parity/gen_vectors.py's scenario blocks (`build_scenarios`,
//! `build_wave2_scenarios`, the repeat and gap blocks, and the wrapper
//! scenarios of the JS state branch) builds here, configured exactly as the
//! Python factory call that names it.

#![allow(dead_code)]

use serde_json::Value;
use skaters::api::{conjugate_f, dantzig_f, flesaker, laplace, laplace_with_leaf, Forecaster};
use skaters::homogenize::{homogenize, make_candidates, DELTA_MAX};
use skaters::leaf::{CrpsLeaf, GarchLeaf, Leaf, ScaleMixLeaf};
use skaters::residual::residual_transform;
use skaters::search::search;
use skaters::skater::{
    bayesian_ensemble, conjugate, ema, multiscale, precision_weighted_ensemble, sticky,
    terminal_leaf_ensemble, with_adaptive_temperature, Sk,
};
use skaters::spec;
use skaters::tails::gpdtails;
use skaters::transform::{
    ar, ar_default, difference, drift, ema_transform, fractional_difference, garch_default,
    gaussianize, gaussianize_default, grouped_ar, holt_linear, log_transform, ou_transform,
    power_transform, power_transform_exact, seasonal_anchor, seasonal_difference, seasonal_scale,
    standardize, theta, yeo_johnson, yeo_johnson_exact,
};

pub const PROBE: f64 = 0.3;
pub const Q_LO: f64 = 0.1;
pub const Q_HI: f64 = 0.9;

pub fn leaf(k: usize) -> Sk {
    Sk::Leaf(Leaf::new(k))
}

/// The fast-warm-up GPD splice the gpd_tails scenario uses, at horizon k.
fn spliced(k: usize) -> Forecaster {
    Forecaster::Gpd(Box::new(gpdtails(
        conjugate(leaf(k), ema_transform(0.1), k),
        k,
        0.9,
        50,
        100,
    )))
}

fn ema_c(k: usize) -> Forecaster {
    Forecaster::Sk(conjugate(leaf(k), ema_transform(0.1), k))
}

/// terminal_leaf_ensemble([ema(0.05), conjugate(leaf, difference())], k,
/// learning_rate=0.5, depths, forget, adaptive_temperature=True, temp_rho).
fn terminal_adaptive(k: usize, depths: Vec<f64>, forget: f64, temp_rho: f64) -> Forecaster {
    let subs = vec![ema(0.05, k), conjugate(leaf(k), difference(), k)];
    let tleafs: Vec<Sk> = (0..k)
        .map(|_| Sk::Crps(CrpsLeaf::new(1, 1.0, 0.01)))
        .collect();
    let t = terminal_leaf_ensemble(subs, tleafs, k, 0.5, 0.0, depths, 20, forget);
    Forecaster::Sk(with_adaptive_temperature(t, temp_rho, 3.0))
}

/// Base scenarios: the name without its `_k3` suffix, at horizon k.
fn build_base(name: &str, k: usize) -> Forecaster {
    let f = |sk: Sk| Forecaster::Sk(sk);
    match name {
        "leaf" => f(leaf(k)),
        "diff" => f(conjugate(leaf(k), difference(), k)),
        "ema_t" => f(conjugate(leaf(k), ema_transform(0.1), k)),
        "standardize" => f(conjugate(leaf(k), standardize(0.05, 1e-8), k)),
        "theta" => f(conjugate(leaf(k), theta(0.1), k)),
        "drift" => f(conjugate(leaf(k), drift(0.05, 0.01), k)),
        "holt" => f(conjugate(leaf(k), holt_linear(0.1, 0.05), k)),
        "garch" => f(conjugate(leaf(k), garch_default(), k)),
        "seasonal" => f(conjugate(leaf(k), seasonal_difference(7), k)),
        "power" => f(conjugate(leaf(k), power_transform(0.5), k)),
        "ar1" => f(conjugate(leaf(k), ar_default(1), k)),
        "ar2" => f(conjugate(leaf(k), ar(2, 0.99, 1.0, 1.0), k)),
        "frac" => f(conjugate(leaf(k), fractional_difference(0.4, 30), k)),
        "grouped_ar" => f(conjugate(leaf(k), grouped_ar(8, 0.99, 1.0), k)),
        "yeojohnson_log" => f(conjugate(leaf(k), yeo_johnson(0.0), k)),
        "yeojohnson_half" => f(conjugate(leaf(k), yeo_johnson(0.5), k)),
        "ou" => f(conjugate(leaf(k), ou_transform(0.1, 0.02), k)),
        "ou_sqrt" => f(conjugate(
            conjugate(leaf(k), ou_transform(0.1, 0.02), k),
            yeo_johnson(0.5),
            k,
        )),
        "seasonal_scale" => f(conjugate(leaf(k), seasonal_scale(7, 0.05, false, 1e-8), k)),
        "seasonal_scale_c" => f(conjugate(leaf(k), seasonal_scale(7, 0.1, true, 1e-8), k)),
        "power_exact" => conjugate_f(f(leaf(k)), power_transform_exact(0.5, true), k),
        "yeojohnson_exact" => conjugate_f(f(leaf(k)), yeo_johnson_exact(0.5, true), k),
        "log_lower" => conjugate_f(f(leaf(k)), log_transform(Some(-15.0), None), k),
        "log_upper" => conjugate_f(f(leaf(k)), log_transform(None, Some(15.0)), k),
        "gaussianize" => f(conjugate(leaf(k), gaussianize_default(), k)),
        "gaussianize_smooth" => f(conjugate(
            leaf(k),
            gaussianize(39, 30, 9, true, 20.0, 8.0, "move"),
            k,
        )),
        "gaussianize_delete" => f(conjugate(
            leaf(k),
            gaussianize(15, 30, 9, false, 1.5, 8.0, "delete"),
            k,
        )),
        "gaussianize_emin" => f(conjugate(
            leaf(k),
            gaussianize(15, 30, 9, false, 1.5, 8.0, "emin"),
            k,
        )),
        "spliced_power" => conjugate_f(spliced(k), power_transform(0.5), k),
        "spliced_yeojohnson" => conjugate_f(spliced(k), yeo_johnson(0.5), k),
        "spliced_gaussianize" => conjugate_f(spliced(k), gaussianize_default(), k),
        "spliced_log" => conjugate_f(spliced(k), log_transform(Some(-15.0), None), k),
        "spliced_ema_t" => conjugate_f(spliced(k), ema_transform(0.1), k),
        "spliced_seasonal" => conjugate_f(spliced(k), seasonal_difference(2), k),
        "spliced_anchor" => conjugate_f(spliced(k), seasonal_anchor(2, 0.2, 0.5), k),
        "spliced_sscale" => conjugate_f(spliced(k), seasonal_scale(7, 0.05, false, 1e-8), k),
        "pf_affine_yj" => conjugate_f(
            conjugate_f(f(leaf(k)), yeo_johnson_exact(0.0, true), k),
            standardize(0.05, 1e-8),
            k,
        ),
        "pf_affine_log" => conjugate_f(
            conjugate_f(f(leaf(k)), log_transform(None, Some(200.0)), k),
            seasonal_scale(7, 0.1, true, 1e-8),
            k,
        ),
        "pol_flesaker" => flesaker(1, Some(-15.0), None),
        "ema_skater" => f(ema(0.05, k)),
        "pw_ensemble" => f(precision_weighted_ensemble(
            vec![ema(0.05, k), ema(0.2, k)],
            k,
        )),
        "multiscale" => f(multiscale(
            |kk| conjugate(leaf(kk), ema_transform(0.1), kk),
            k,
            None,
        )),
        "bayes_ensemble" => f(bayesian_ensemble(
            vec![ema(0.05, k), conjugate(leaf(k), difference(), k)],
            k,
            0.5,
            0.02,
            vec![1.0, 1.0],
        )),
        "pol_laplace" => laplace(k),
        "gpd_tails" => spliced(1),
        "scale_mixture_leaf" => f(Sk::ScaleMix(ScaleMixLeaf::new(1, 0.02, 0.01))),
        "crps_leaf" => f(Sk::Crps(CrpsLeaf::new(1, 1.0, 0.01))),
        "garch_leaf" => f(Sk::GarchLeaf(GarchLeaf::new(1))),
        "scalemix_ema" => f(conjugate(
            Sk::ScaleMix(ScaleMixLeaf::new(1, 0.02, 0.01)),
            ema_transform(0.1),
            1,
        )),
        "sticky_ema" => f(sticky(conjugate(leaf(1), ema_transform(0.1), 1), 1)),
        "spec_diff_ensemble" => f(spec::build(&spec::conjugate_spec(
            spec::ensemble_spec(vec![spec::ema_spec(0.01, 1), spec::ema_spec(0.1, 1)], 1),
            spec::diff_spec(),
        ))),
        "spec_ema" => f(spec::build(&spec::ema_spec(0.05, 1))),
        "search_default" => {
            // Python: adaptive_search(k=1, expand_interval=50)
            let mut s = search(1);
            s.expand_interval = 50;
            f(Sk::Search(Box::new(s)))
        }
        _ => panic!("unknown scenario {name}"),
    }
}

/// Wave-2 and wrapper scenarios, by full name. None for any other name.
fn build_wrapper(full: &str) -> Option<(Forecaster, usize)> {
    let r = match full {
        // gen_vectors.build_wave2_scenarios
        "homogenize" => (homogenize(ema_c(1), None, 1, "none", 0.25), 1),
        "homogenize_k3" => (homogenize(ema_c(3), None, 3, "none", 0.25), 3),
        "homogenize_weights_k3" => (homogenize(ema_c(3), None, 3, "weights", 0.25), 3),
        "homogenize_state_k3" => (homogenize(ema_c(3), None, 3, "state", 0.25), 3),
        "homogenize_shared_k3" => (homogenize(ema_c(3), None, 3, "shared", 0.25), 3),
        "residual_m0" => (residual_transform(ema_c(1), "m0", 0.01), 1),
        "residual_m1" => (residual_transform(ema_c(1), "m1", 0.01), 1),
        "residual_m2" => (residual_transform(ema_c(1), "m2", 0.01), 1),
        "terminal_adapt" => (terminal_adaptive(1, vec![0.0, 0.0], 1.0, 0.03), 1),
        "terminal_adapt_k3" => (terminal_adaptive(3, vec![0.0, 0.0], 1.0, 0.03), 3),
        "dantzig" | "pol_dantzig" => (dantzig_f(1, 50), 1),
        // the JS state branch's build_wrapper_scenarios
        "homogenize_k2_weights" => (homogenize(ema_c(2), None, 2, "weights", 0.25), 2),
        "homogenize_k2_state" => (homogenize(ema_c(2), None, 2, "state", 0.5), 2),
        "homogenize_k2_shared" => (homogenize(ema_c(2), None, 2, "shared", 0.25), 2),
        "homogenize_small_grid" => {
            let c = make_candidates(&[0.0, 0.9], &[0.1], &[0.0, 0.5], DELTA_MAX).unwrap();
            (homogenize(ema_c(1), Some(c), 1, "none", 0.25), 1)
        }
        "residual_transform_m0" => (residual_transform(ema_c(1), "m0", 0.01), 1),
        "residual_transform_m1" => (residual_transform(ema_c(1), "m1", 0.01), 1),
        "residual_transform_m2" => (residual_transform(ema_c(1), "m2", 0.01), 1),
        "residual_transform_m2_lr" => (residual_transform(ema_c(1), "m2", 0.05), 1),
        "terminal_adaptive" => (terminal_adaptive(1, vec![0.0, 1.0], 1.0, 0.1), 1),
        "terminal_adaptive_k3" => (terminal_adaptive(3, vec![0.0, 1.0], 0.99, 0.03), 3),
        "pol_laplace_garch_leaf" => (laplace_with_leaf(1, || Sk::GarchLeaf(GarchLeaf::new(1))), 1),
        _ => return None,
    };
    Some(r)
}

/// Build the scenario named `full` (any block). Returns the skater and its k.
pub fn build_scenario(full: &str) -> (Forecaster, usize) {
    if let Some(r) = build_wrapper(full) {
        return r;
    }
    if full == "pol_laplace" {
        return (laplace(1), 1);
    }
    if full == "pol_laplace_k3" {
        return (laplace(3), 3);
    }
    if let Some(base) = full.strip_suffix("_k3") {
        return (build_base(base, 3), 3);
    }
    (build_base(full, 1), 1)
}

pub fn parse_val(v: &Value) -> f64 {
    match v {
        Value::Number(n) => n.as_f64().unwrap(),
        Value::String(s) => match s.as_str() {
            "inf" => f64::INFINITY,
            "-inf" => f64::NEG_INFINITY,
            "nan" => f64::NAN,
            _ => panic!("bad sentinel {s}"),
        },
        _ => panic!("bad probe value {v:?}"),
    }
}

/// The seven probes of gen_vectors.probe_dist.
pub fn probes(d: &skaters::tails::PDist) -> [f64; 7] {
    [
        d.mean(),
        d.std(),
        d.logpdf(PROBE),
        d.cdf(PROBE),
        d.quantile(Q_LO),
        d.quantile(Q_HI),
        d.crps(PROBE),
    ]
}

pub fn close(a: f64, b: f64, atol: f64, rtol: f64) -> bool {
    if a.is_nan() && b.is_nan() {
        return true;
    }
    if a == b {
        return true;
    }
    (a - b).abs() <= atol + rtol * b.abs()
}

/// Bitwise equality, with every NaN equal to every NaN.
pub fn same_bits(a: f64, b: f64) -> bool {
    (a.is_nan() && b.is_nan()) || a.to_bits() == b.to_bits()
}

/// Read a repo file one level above the crate (parity/...), if present.
pub fn repo_file(rel: &str) -> String {
    format!("{}/../{}", env!("CARGO_MANIFEST_DIR"), rel)
}

/// Compare two canonical states: same keys, list lengths, nulls, booleans,
/// strings and number kinds (JSON integer or float), numbers within `tol`.
/// Returns the first difference.
pub fn state_diff(a: &Value, b: &Value, tol: f64, path: &str) -> Option<String> {
    match (a, b) {
        (Value::Null, Value::Null) => None,
        (Value::Bool(x), Value::Bool(y)) if x == y => None,
        (Value::String(x), Value::String(y)) if x == y => None,
        (Value::Number(x), Value::Number(y)) => {
            let int_a = x.is_u64() || x.is_i64();
            let int_b = y.is_u64() || y.is_i64();
            if int_a != int_b {
                return Some(format!("{path}: integer/float kind differs ({x} vs {y})"));
            }
            let (fa, fb) = (x.as_f64().unwrap(), y.as_f64().unwrap());
            if close(fa, fb, tol, tol) {
                None
            } else {
                Some(format!("{path}: {fa} vs {fb}"))
            }
        }
        (Value::Array(x), Value::Array(y)) => {
            if x.len() != y.len() {
                return Some(format!("{path}: list length {} vs {}", x.len(), y.len()));
            }
            x.iter()
                .zip(y.iter())
                .enumerate()
                .find_map(|(i, (p, q))| state_diff(p, q, tol, &format!("{path}[{i}]")))
        }
        (Value::Object(x), Value::Object(y)) => {
            let ka: Vec<&String> = x.keys().collect();
            let kb: Vec<&String> = y.keys().collect();
            let mut sa = ka.clone();
            let mut sb = kb.clone();
            sa.sort();
            sb.sort();
            if sa != sb {
                return Some(format!("{path}: keys {sa:?} vs {sb:?}"));
            }
            x.iter()
                .find_map(|(k, p)| state_diff(p, &y[k], tol, &format!("{path}.{k}")))
        }
        _ => Some(format!("{path}: {} vs {}", short(a), short(b))),
    }
}

fn short(v: &Value) -> String {
    let s = v.to_string();
    s.chars().take(80).collect()
}
