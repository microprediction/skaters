//! The gate: replay every scenario over the embedded series and compare the
//! seven probes (mean, std, logpdf@0.3, cdf@0.3, q0.1, q0.9, crps@0.3)
//! against parity/vectors.json at atol = rtol = 1e-6, plus the cov and
//! periodicity blocks. Full library coverage: nothing is skipped.

use serde_json::Value;

static DIGEST: std::sync::atomic::AtomicU64 =
    std::sync::atomic::AtomicU64::new(0xcbf2_9ce4_8422_2325);

/// Fold one computed value into the FNV-1a bit digest.
///
/// NaN is canonicalized first. IEEE-754 fixes the bits of zeros, normals and
/// both infinities, but leaves a NaN's sign and payload unspecified, and
/// platforms differ: x86 and aarch64 propagate different payloads, and wasm
/// canonicalizes its own way. Probes can legitimately be NaN (gen_vectors.py has
/// a "nan" sentinel for exactly that), so folding raw NaN bits made this digest
/// report a platform divergence that is not one. Presence of a NaN is still
/// recorded, since every NaN maps to one fixed pattern.
fn digest_push(v: f64) {
    let bits = if v.is_nan() {
        0x7ff8_0000_0000_0000
    } else {
        v.to_bits()
    };
    let cur = DIGEST.load(std::sync::atomic::Ordering::Relaxed);
    DIGEST.store(
        (cur ^ bits).wrapping_mul(0x0000_0100_0000_01b3),
        std::sync::atomic::Ordering::Relaxed,
    );
}

mod common;

use common::{build_scenario, parse_val, probes, same_bits};
use skaters::api::Forecaster;
use skaters::cov::{EmaCov, LedoitWolfCov, RunningCov};
use skaters::periodicity::PeriodDetector;
use skaters::spec;
use skaters::state::State;

const ATOL: f64 = 1e-6;
const RTOL: f64 = 1e-6;

/// Compare a computed flat vector against an expected JSON array, folding
/// every computed value into the digest.
fn check_vec(label: &str, got: &[f64], exp: &Value, checked: &mut u64, failures: &mut Vec<String>) {
    let exp: Vec<f64> = exp.as_array().unwrap().iter().map(parse_val).collect();
    assert_eq!(exp.len(), got.len(), "{label}: length mismatch");
    for (p, (&g, &e)) in got.iter().zip(exp.iter()).enumerate() {
        digest_push(g);
        *checked += 1;
        if !close(g, e) && failures.len() < 20 {
            failures.push(format!("{label}[{p}]: got {g:.12e} expected {e:.12e}"));
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

/// Run a scenario over the series and compare the seven probes. At the
/// burn-in step the state is checkpointed in the canonical JSON layout
/// (docs/STATE.md), written to a string, and loaded into a freshly built
/// twin, which then steps beside the original for the rest of the series:
/// every probe of the twin must equal the original's bit for bit, and so must
/// the final states. This is the restore leg gen_vectors.py runs in Python.
#[allow(clippy::too_many_arguments)]
fn run_scenario(
    name: &str,
    mut skater: Forecaster,
    fresh: &dyn Fn() -> Forecaster,
    series: &[f64],
    burn: usize,
    expected: &Value,
    checked: &mut u64,
    failures: &mut Vec<String>,
) {
    let out = expected.as_array().unwrap();
    let mut oi = 0usize;
    let mut twin: Option<Forecaster> = None;
    for (i, &y) in series.iter().enumerate() {
        let dists = skater.step(y);
        if let Some(t) = twin.as_mut() {
            let td = t.step(y);
            assert_eq!(td.len(), dists.len(), "{name}: restored twin horizon count");
            for (a, b) in dists.iter().zip(td.iter()) {
                let (pa, pb) = (probes(a), probes(b));
                if !pa.iter().zip(pb.iter()).all(|(x, y)| same_bits(*x, *y)) && failures.len() < 20
                {
                    failures.push(format!(
                        "{name} step {i}: the JSON-restored twin differs: {pa:?} vs {pb:?}"
                    ));
                }
            }
        }
        if i + 1 == burn {
            let text = serde_json::to_string(&skater.state_to_json()).unwrap();
            let mut t = fresh();
            t.load_state(&serde_json::from_str(&text).unwrap())
                .unwrap_or_else(|e| panic!("{name}: canonical restore failed: {e}"));
            twin = Some(t);
        }
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
            let got = probes(d);
            for v in got.iter() {
                digest_push(*v);
            }
            let exp: Vec<f64> = step_exp[h]
                .as_array()
                .unwrap()
                .iter()
                .map(parse_val)
                .collect();
            const LABELS: [&str; 7] = ["mean", "std", "logpdf", "cdf", "q_lo", "q_hi", "crps"];
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
    if let Some(t) = twin {
        if skater.state_to_json() != t.state_to_json() && failures.len() < 20 {
            failures.push(format!(
                "{name}: the JSON-restored twin's final state differs"
            ));
        }
    }
}

/// Run every scenario of a block (name -> {k, out}) on a series.
fn run_block(
    label: &str,
    block: &serde_json::Map<String, Value>,
    series: &[f64],
    burn: usize,
    checked: &mut u64,
    failures: &mut Vec<String>,
) -> usize {
    for (full, sc) in block {
        let (skater, k) = build_scenario(full);
        assert_eq!(sc["k"].as_u64().unwrap() as usize, k, "{full}: k mismatch");
        let name = if label.is_empty() {
            full.clone()
        } else {
            format!("{label}:{full}")
        };
        let f = full.clone();
        run_scenario(
            &name,
            skater,
            &move || build_scenario(&f).0,
            series,
            burn,
            &sc["out"],
            checked,
            failures,
        );
    }
    block.len()
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
    // The vectors are GENERATED, not shipped: they are absent from the
    // published crate, so a consumer running `cargo test` has nothing to check
    // against. Skip rather than fail -- this gate is meaningful only against a
    // reference regenerated from the Python source of truth, and a stale or
    // missing copy must never read as a pass or as a spurious failure.
    let raw = match std::fs::read_to_string(&path) {
        Ok(raw) => raw,
        Err(_) => {
            println!(
                "SKIP parity: no vectors at {path}. Regenerate in the skaters repo with\n  \
                 PYTHONPATH=src python parity/gen_vectors.py\n\
                 or point SKATERS_VECTORS at a copy."
            );
            return;
        }
    };
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

    n_scenarios += run_block(
        "",
        v["scenarios"].as_object().unwrap(),
        &series,
        burn,
        &mut checked,
        &mut failures,
    );
    n_scenarios += run_block(
        "",
        v["repeat_scenarios"].as_object().unwrap(),
        &repeat_series,
        burn,
        &mut checked,
        &mut failures,
    );
    // Missing observations: the parade's non-finite tick rule (skip the update,
    // age the fan). The series carries the same "nan" sentinel the outputs use,
    // since JSON has no NaN literal.
    if let Some(gap) = v["gap_scenarios"].as_object() {
        let gap_series: Vec<f64> = v["gap_series"]
            .as_array()
            .unwrap()
            .iter()
            .map(parse_val)
            .collect();
        n_scenarios += run_block("gap", gap, &gap_series, burn, &mut checked, &mut failures);
    }
    // The second-wave surface (homogenize, residual_transform, the adaptive
    // temperature, dantzig) and the wrapper block of the JS state branch.
    for blk in ["wave2_scenarios", "wrapper_scenarios"] {
        if let Some(b) = v[blk].as_object() {
            n_scenarios += run_block(blk, b, &series, burn, &mut checked, &mut failures);
        }
    }
    // Spec JSON: from_json then to_json must give back the string exactly, and
    // the canonical name must match Python's.
    if let Some(specs) = v["spec_json"].as_array() {
        for ex in specs {
            let text = ex["json"].as_str().unwrap();
            let want = ex["name"].as_str().unwrap();
            let sp = spec::from_json(text).unwrap_or_else(|e| panic!("spec {text}: {e}"));
            checked += 2;
            if spec::to_json(&sp) != text {
                failures.push(format!(
                    "spec_json: {text} wrote back as {}",
                    spec::to_json(&sp)
                ));
            }
            if spec::name(&sp) != want {
                failures.push(format!(
                    "spec_json: {text} named {} want {want}",
                    spec::name(&sp)
                ));
            }
            let _ = spec::build(&sp);
        }
        n_scenarios += specs.len();
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

    // Structure: the candidate population itself, not its numbers. Numeric
    // probes cannot see a port missing a candidate -- the R port ran 57 against
    // Python's 60 while every individual transform still matched to 1e-6. The
    // depth vector also pins ORDER, since the ensemble aligns depths by index.
    if let Some(structure) = v["structure"].as_object() {
        for (kname, want) in structure {
            let kk: usize = kname.parse().expect("structure key must be an integer k");
            let (cands, depths) = skaters::api::build_candidates(kk);
            let want_n = want["n_candidates"].as_u64().unwrap() as usize;
            if cands.len() != want_n {
                failures.push(format!(
                    "structure k={kk}: {} candidates, want {want_n}",
                    cands.len()
                ));
            }
            let want_d: Vec<f64> = want["depths"]
                .as_array()
                .unwrap()
                .iter()
                .map(|x| x.as_f64().unwrap())
                .collect();
            if depths != want_d {
                failures.push(format!("structure k={kk}: depth vector differs"));
            }
            if cands.len() == want_n && depths == want_d {
                println!("ok   structure k={kk}   {} candidates", cands.len());
            }
        }
    }

    println!("parity: {n_scenarios} scenarios, {checked} values checked");
    // Bit digest: FNV-1a over the bit patterns of every computed probe.
    // Identical across platforms iff the portable-math claim holds.
    println!(
        "PARITY_DIGEST={:016x}",
        DIGEST.load(std::sync::atomic::Ordering::Relaxed)
    );
    if !failures.is_empty() {
        panic!(
            "parity failures ({} shown):\n{}",
            failures.len(),
            failures.join("\n")
        );
    }
}
