//! granger parity against the pure-Python reference (parity/granger_vectors.json):
//! the issued mixture's log density at the next observation, mean, spread,
//! laplace's mixture weight and two quantiles, every step, every shipped set.
use skaters::Granger;
use std::collections::BTreeMap;

// The repo gate (laplace Rust vs Python, parity/vectors.json) is atol = rtol = 1e-6;
// granger cannot be tighter than the laplace it contains.
const ATOL: f64 = 1e-6;
const RTOL: f64 = 1e-6;

#[derive(serde::Deserialize)]
struct Stream {
    ys: Vec<Option<f64>>, // null = a missing observation
    rows: Vec<Vec<Option<f64>>>,
}

#[test]
fn granger_matches_python() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../parity/granger_vectors.json"
    );
    let s = std::fs::read_to_string(path).expect("run parity/gen_granger_vectors.py first");
    let all: BTreeMap<String, Stream> = serde_json::from_str(&s).unwrap();
    let mut worst = 0.0f64;
    for (key, st) in &all {
        let freq = key.split('/').next().unwrap();
        let mut g = Granger::shipped(freq).expect("shipped set");
        let ys: Vec<f64> = st.ys.iter().map(|v| v.unwrap_or(f64::NAN)).collect();
        for (t, y) in ys[..ys.len() - 1].iter().enumerate() {
            let m = g.step(*y);
            let got = [
                m.logpdf(ys[t + 1]),
                m.mean(),
                m.std(),
                m.w[0],
                m.quantile(0.1),
                m.quantile(0.9),
            ];
            for (a, b) in got.iter().zip(st.rows[t].iter()) {
                let Some(b) = b else { continue }; // no score at a missing next value
                let dev = (a - b).abs();
                worst = worst.max(dev / b.abs().max(1.0));
                assert!(
                    dev <= ATOL + RTOL * b.abs(),
                    "{key} step {t}: rust {a} python {b}"
                );
            }
        }
    }
    eprintln!("granger parity worst relative deviation {worst:.2e}");
}

mod common;

/// Cross-language resume for granger (parity/granger_resume.json, written by
/// `PYTHONPATH=src python3 parity/gen_granger_resume.py`): load each Python
/// checkpoint into a granger built from the same shipped parameters, step,
/// and match Python's rows to 1e-6. The loaded state must write back exactly
/// as Python wrote it, and Rust's own state after the same observations must
/// have Python's layout. Rust's own checkpoints are written to
/// parity/resume_granger_rust.json for the reverse check in
/// tests/test_rust_resume.py.
#[test]
fn granger_resume_from_python() {
    use serde_json::{Map, Value};
    use skaters::state::State;
    let path = common::repo_file("parity/granger_resume.json");
    let Ok(raw) = std::fs::read_to_string(&path) else {
        println!("SKIP granger resume: run parity/gen_granger_resume.py first");
        return;
    };
    let all: Map<String, Value> = serde_json::from_str(&raw).unwrap();
    let mut failures = Vec::new();
    let mut rust_out = Map::new();
    let mut checked = 0u64;
    for (key, st) in &all {
        let freq = key.split('/').next().unwrap();
        let ys: Vec<f64> = st["ys"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_f64().unwrap_or(f64::NAN))
            .collect();
        let mut own = Granger::shipped(freq).unwrap();
        let mut t_own = 0usize;
        let mut cps_out = Map::new();
        let cps = st["checkpoints"].as_object().unwrap();
        let mut times: Vec<usize> = cps.keys().map(|t| t.parse().unwrap()).collect();
        times.sort_unstable();
        for t in times {
            let cp = &cps[&t.to_string()];
            let mut g = Granger::shipped(freq).unwrap();
            g.load_state(&cp["state"])
                .unwrap_or_else(|e| panic!("{key}@{t}: load failed: {e}"));
            if let Some(d) = common::state_diff(&g.state_to_json(), &cp["state"], 0.0, "$") {
                failures.push(format!(
                    "{key}@{t}: loaded state writes back differently: {d}"
                ));
            }
            while t_own < t {
                own.step(ys[t_own]);
                t_own += 1;
            }
            let own_state = own.state_to_json();
            if let Some(d) = common::state_diff(&own_state, &cp["state"], 1e-4, "$") {
                failures.push(format!("{key}@{t}: Rust's own state differs: {d}"));
            }
            cps_out.insert(t.to_string(), own_state);
            for (j, row) in cp["rows"].as_array().unwrap().iter().enumerate() {
                let m = g.step(ys[t + j]);
                let nxt = ys[t + j + 1];
                let got = [
                    m.logpdf(nxt),
                    m.mean(),
                    m.std(),
                    m.w[0],
                    m.quantile(0.1),
                    m.quantile(0.9),
                ];
                for (a, b) in got.iter().zip(row.as_array().unwrap()) {
                    let Some(b) = b.as_f64() else { continue };
                    checked += 1;
                    if (a - b).abs() > ATOL + RTOL * b.abs() {
                        failures.push(format!("{key}@{t} step {j}: rust {a} python {b}"));
                    }
                }
            }
        }
        rust_out.insert(key.clone(), Value::Object(cps_out));
    }
    let out = common::repo_file("parity/resume_granger_rust.json");
    std::fs::write(
        &out,
        serde_json::to_string(&Value::Object(rust_out)).unwrap(),
    )
    .unwrap();
    eprintln!(
        "granger resume: {} streams, {checked} values checked",
        all.len()
    );
    assert!(
        failures.is_empty(),
        "granger resume failures:\n{}",
        failures.join("\n")
    );
}
