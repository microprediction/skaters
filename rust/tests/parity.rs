//! The gate: replay every implemented scenario over the embedded series and
//! compare the seven probes (mean, std, logpdf@0.3, cdf@0.3, q0.1, q0.9,
//! crps@0.3) against parity/vectors.json at atol = rtol = 1e-6.
//!
//! Out of scope: search_default, spec_diff_ensemble, spec_ema.

use serde_json::Value;

static DIGEST: std::sync::atomic::AtomicU64 =
    std::sync::atomic::AtomicU64::new(0xcbf2_9ce4_8422_2325);

/// Fold one computed value into the FNV-1a bit digest.
fn digest_push(v: f64) {
    let cur = DIGEST.load(std::sync::atomic::Ordering::Relaxed);
    DIGEST.store(
        (cur ^ v.to_bits()).wrapping_mul(0x0000_0100_0000_01b3),
        std::sync::atomic::Ordering::Relaxed,
    );
}

use skaters_core::api::{laplace, Forecaster};
use skaters_core::cov::{EmaCov, LedoitWolfCov, RunningCov};
use skaters_core::periodicity::PeriodDetector;
use skaters_core::leaf::{CrpsLeaf, GarchLeaf, Leaf, ScaleMixLeaf};
use skaters_core::skater::{
    bayesian_ensemble, conjugate, ema, multiscale, precision_weighted_ensemble, sticky, Sk,
};
use skaters_core::tails::gpdtails;
use skaters_core::transform::{
    ar, ar_default, difference, drift, ema_transform, fractional_difference, garch_default,
    grouped_ar, holt_linear, ou_transform, power_transform, seasonal_difference, standardize,
    theta, yeo_johnson,
};

const ATOL: f64 = 1e-6;
const RTOL: f64 = 1e-6;
const PROBE: f64 = 0.3;
const Q_LO: f64 = 0.1;
const Q_HI: f64 = 0.9;

fn leaf(k: usize) -> Sk {
    Sk::Leaf(Leaf::new(k))
}

fn parse_val(v: &Value) -> f64 {
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

/// Compare a computed flat vector against an expected JSON array, folding
/// every computed value into the digest.
fn check_vec(
    label: &str,
    got: &[f64],
    exp: &Value,
    checked: &mut u64,
    failures: &mut Vec<String>,
) {
    let exp: Vec<f64> = exp.as_array().unwrap().iter().map(parse_val).collect();
    assert_eq!(exp.len(), got.len(), "{label}: length mismatch");
    for (p, (&g, &e)) in got.iter().zip(exp.iter()).enumerate() {
        digest_push(g);
        *checked += 1;
        if !close(g, e) && failures.len() < 20 {
            failures.push(format!(
                "{label}[{p}]: got {g:.12e} expected {e:.12e}"
            ));
        }
    }
}

fn close(a: f64, b: f64) -> bool {
    if a.is_nan() && b.is_nan() {
        return true;
    }
    if a == b {
        return true; // covers equal infinities
    }
    (a - b).abs() <= ATOL + RTOL * b.abs()
}

fn build(name: &str, k: usize) -> Forecaster {
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
        "gpd_tails" => Forecaster::Gpd(Box::new(gpdtails(
            conjugate(leaf(1), ema_transform(0.1), 1),
            1,
            0.9,
            50,
            100,
        ))),
        "scale_mixture_leaf" => f(Sk::ScaleMix(ScaleMixLeaf::new(1, 0.02, 0.01))),
        "crps_leaf" => f(Sk::Crps(CrpsLeaf::new(1, 1.0, 0.01))),
        "garch_leaf" => f(Sk::GarchLeaf(GarchLeaf::new(1))),
        "scalemix_ema" => f(conjugate(
            Sk::ScaleMix(ScaleMixLeaf::new(1, 0.02, 0.01)),
            ema_transform(0.1),
            1,
        )),
        "sticky_ema" => f(sticky(conjugate(leaf(1), ema_transform(0.1), 1), 1)),
        _ => panic!("unknown scenario {name}"),
    }
}

fn scenario_name(full: &str) -> Option<(&str, usize)> {
    // returns (base_name, k) for names we implement; None to skip.
    let skipped = ["search_default", "spec_diff_ensemble", "spec_ema"];
    if skipped.contains(&full) {
        return None;
    }
    if full == "pol_laplace" {
        return Some(("pol_laplace", 1));
    }
    if full == "pol_laplace_k3" {
        return Some(("pol_laplace", 3));
    }
    if let Some(base) = full.strip_suffix("_k3") {
        return Some((base, 3));
    }
    Some((full, 1))
}

fn run_scenario(
    name: &str,
    mut skater: Forecaster,
    series: &[f64],
    burn: usize,
    expected: &Value,
    checked: &mut u64,
    failures: &mut Vec<String>,
) {
    let out = expected.as_array().unwrap();
    let mut oi = 0usize;
    for (i, &y) in series.iter().enumerate() {
        let dists = skater.step(y);
        if i < burn {
            continue;
        }
        let step_exp = out[oi].as_array().unwrap();
        assert_eq!(
            step_exp.len(),
            dists.len(),
            "{name}: horizon count mismatch at step {i}"
        );
        for (h, d) in dists.iter().enumerate() {
            let got = [
                d.mean(),
                d.std(),
                d.logpdf(PROBE),
                d.cdf(PROBE),
                d.quantile(Q_LO),
                d.quantile(Q_HI),
                d.crps(PROBE),
            ];
            for v in got.iter() {
                digest_push(*v);
            }
            let exp: Vec<f64> = step_exp[h]
                .as_array()
                .unwrap()
                .iter()
                .map(parse_val)
                .collect();
            const LABELS: [&str; 7] =
                ["mean", "std", "logpdf", "cdf", "q_lo", "q_hi", "crps"];
            for p in 0..7 {
                *checked += 1;
                if !close(got[p], exp[p]) && failures.len() < 20 {
                    failures.push(format!(
                        "{name} step {i} horizon {h} {}: got {:.12e} expected {:.12e}",
                        LABELS[p], got[p], exp[p]
                    ));
                }
            }
        }
        oi += 1;
    }
    assert_eq!(oi, out.len(), "{name}: scored-step count mismatch");
}

#[test]
fn parity_vectors() {
    // Inside the main skaters repo the canonical vectors live one level up
    // (single source of truth); standalone checkouts fall back to the local
    // copy. SKATERS_VECTORS overrides both.
    let path = std::env::var("SKATERS_VECTORS").unwrap_or_else(|_| {
        let repo = concat!(env!("CARGO_MANIFEST_DIR"), "/../parity/vectors.json");
        if std::path::Path::new(repo).exists() {
            repo.to_string()
        } else {
            concat!(env!("CARGO_MANIFEST_DIR"), "/parity/vectors.json").to_string()
        }
    });
    let raw = std::fs::read_to_string(&path).expect("vectors.json");
    let v: Value = serde_json::from_str(&raw).unwrap();
    let series: Vec<f64> = v["series"]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_f64().unwrap())
        .collect();
    let repeat_series: Vec<f64> = v["repeat_series"]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_f64().unwrap())
        .collect();
    let burn = v["burn"].as_u64().unwrap() as usize;

    let mut checked: u64 = 0;
    let mut failures: Vec<String> = Vec::new();
    let mut n_scenarios = 0;

    let scenarios = v["scenarios"].as_object().unwrap();
    for (full, sc) in scenarios {
        let Some((base, k)) = scenario_name(full) else {
            continue;
        };
        assert_eq!(sc["k"].as_u64().unwrap() as usize, k, "{full}: k mismatch");
        let skater = build(base, k);
        run_scenario(
            full,
            skater,
            &series,
            burn,
            &sc["out"],
            &mut checked,
            &mut failures,
        );
        n_scenarios += 1;
    }

    let rep = v["repeat_scenarios"].as_object().unwrap();
    for (full, sc) in rep {
        let k = sc["k"].as_u64().unwrap() as usize;
        let skater = build(full, k);
        run_scenario(
            full,
            skater,
            &repeat_series,
            burn,
            &sc["out"],
            &mut checked,
            &mut failures,
        );
        n_scenarios += 1;
    }

    // Covariance estimators on the fixed multivariate series (cov block).
    let vec_series: Vec<Vec<f64>> = v["vec_series"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| {
            row.as_array()
                .unwrap()
                .iter()
                .map(|x| x.as_f64().unwrap())
                .collect()
        })
        .collect();
    let cov_block = v["cov"].as_object().unwrap();
    let mut cov_ests: Vec<(&str, Box<dyn FnMut(&[f64]) -> (Vec<f64>, Vec<f64>)>)> = vec![
        ("running", {
            let mut e = RunningCov::new();
            Box::new(move |y: &[f64]| e.update(y))
        }),
        ("ema", {
            let mut e = EmaCov::new();
            Box::new(move |y: &[f64]| e.update(y))
        }),
        ("ledoit", {
            let mut e = LedoitWolfCov::new();
            Box::new(move |y: &[f64]| e.update(y))
        }),
    ];
    for (nm, est) in cov_ests.iter_mut() {
        let out = cov_block[*nm].as_array().unwrap();
        let mut oi = 0usize;
        for (i, y) in vec_series.iter().enumerate() {
            let (mean, cmat) = est(y);
            if i < burn {
                continue;
            }
            let step = out[oi].as_array().unwrap();
            check_vec(
                &format!("cov/{nm} step {i} mean"),
                &mean,
                &step[0],
                &mut checked,
                &mut failures,
            );
            check_vec(
                &format!("cov/{nm} step {i} cov"),
                &cmat,
                &step[1],
                &mut checked,
                &mut failures,
            );
            oi += 1;
        }
        assert_eq!(oi, out.len(), "cov/{nm}: scored-step count mismatch");
        n_scenarios += 1;
    }

    // Periodicity detector: ranked (lag, acf) block on the main series.
    {
        let out = v["periodicity"].as_array().unwrap();
        let mut pd = PeriodDetector::new();
        let mut oi = 0usize;
        for (i, &y) in series.iter().enumerate() {
            let scores = pd.step(y);
            if i < burn {
                continue;
            }
            let step_exp = out[oi].as_array().unwrap();
            assert_eq!(
                step_exp.len(),
                scores.len(),
                "periodicity: score count mismatch at step {i}"
            );
            for (r, &(lag, acf)) in scores.iter().enumerate() {
                let pair = step_exp[r].as_array().unwrap();
                let exp_lag = pair[0].as_u64().unwrap() as usize;
                let exp_acf = parse_val(&pair[1]);
                digest_push(lag as f64);
                digest_push(acf);
                checked += 2;
                if lag != exp_lag && failures.len() < 20 {
                    failures.push(format!(
                        "periodicity step {i} rank {r}: got lag {lag} expected {exp_lag}"
                    ));
                }
                if !close(acf, exp_acf) && failures.len() < 20 {
                    failures.push(format!(
                        "periodicity step {i} rank {r} acf: got {acf:.12e} expected {exp_acf:.12e}"
                    ));
                }
            }
            oi += 1;
        }
        assert_eq!(oi, out.len(), "periodicity: scored-step count mismatch");
        n_scenarios += 1;
    }

    println!("parity: {n_scenarios} scenarios, {checked} values checked");
    // Bit digest: FNV-1a over the bit patterns of every computed probe.
    // Identical across platforms iff the portable-math claim holds.
    println!("PARITY_DIGEST={:016x}", DIGEST.load(std::sync::atomic::Ordering::Relaxed));
    if !failures.is_empty() {
        panic!(
            "parity failures ({} shown):\n{}",
            failures.len(),
            failures.join("\n")
        );
    }
}
