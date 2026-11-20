//! Cross-language resume, both directions, on parity/resume_vectors.json
//! (written by `PYTHONPATH=src python3 parity/gen_resume.py`).
//!
//! Python to Rust: for every scenario and checkpoint, build the same-named
//! skater, load Python's canonical state, step the next observations and
//! match Python's probes to 1e-6. Along the way the loaded state must write
//! back exactly as Python wrote it, and the state Rust reaches on its own
//! after the same observations must have Python's layout field by field (the
//! same keys, list lengths, nulls and integer/float kinds) with every number
//! within 1e-4 (see OWN_TOL).
//!
//! Rust to Python: `write_resume_rust` writes Rust's own checkpoints of the
//! same scenarios to parity/resume_rust.json, which
//! `PYTHONPATH=src python3 parity/check_resume.py parity/resume_rust.json`
//! resumes in Python.

mod common;

use common::{build_scenario, close, parse_val, probes, repo_file, state_diff};
use serde_json::{Map, Value};
use skaters::state::State;

const TOL: f64 = 1e-6;
/// Tolerance for Rust's own state, run from scratch, against Python's. The
/// probes are held to 1e-6; a state field is a running sum over hundreds of
/// steps (homogenize's discounted log weights, for one), so the ports'
/// last-bit differences in erf, exp and log accumulate in it to a few 1e-6.
const OWN_TOL: f64 = 1e-4;

fn load_vectors() -> Option<Value> {
    let path = std::env::var("SKATERS_RESUME_VECTORS")
        .unwrap_or_else(|_| repo_file("parity/resume_vectors.json"));
    match std::fs::read_to_string(&path) {
        Ok(raw) => Some(serde_json::from_str(&raw).unwrap()),
        Err(_) => {
            println!(
                "SKIP resume: no vectors at {path}. Generate them with\n  \
                 PYTHONPATH=src python3 parity/gen_resume.py"
            );
            None
        }
    }
}

fn series_of(v: &Value) -> Vec<f64> {
    v["series"]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_f64().unwrap())
        .collect()
}

#[test]
fn resume_from_python() {
    let Some(v) = load_vectors() else { return };
    let series = series_of(&v);
    let steps = v["steps"].as_u64().unwrap() as usize;
    let times: Vec<usize> = v["times"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t.as_u64().unwrap() as usize)
        .collect();
    let scenarios = v["scenarios"].as_object().unwrap();
    let mut failures: Vec<String> = Vec::new();
    let (mut checked, mut n_cp) = (0u64, 0usize);
    for (name, sc) in scenarios {
        let (_, k) = build_scenario(name);
        assert_eq!(sc["k"].as_u64().unwrap() as usize, k, "{name}: k mismatch");
        // Rust's own run, for the field-by-field layout check
        let (mut own, _) = build_scenario(name);
        let mut t_own = 0usize;
        for t in &times {
            let cp = &sc["checkpoints"][t.to_string()];
            let py_state = &cp["state"];
            let (mut sk, _) = build_scenario(name);
            if let Err(e) = sk.load_state(py_state) {
                failures.push(format!("{name}@{t}: load failed: {e}"));
                continue;
            }
            n_cp += 1;
            // the loaded state writes back exactly as Python wrote it
            if let Some(d) = state_diff(&sk.state_to_json(), py_state, 0.0, "$") {
                failures.push(format!(
                    "{name}@{t}: loaded state writes back differently: {d}"
                ));
            }
            // Rust's own state after the same observations, field by field
            while t_own < *t {
                own.step(series[t_own]);
                t_own += 1;
            }
            if let Some(d) = state_diff(&own.state_to_json(), py_state, OWN_TOL, "$") {
                failures.push(format!(
                    "{name}@{t}: Rust's own state differs from Python's: {d}"
                ));
            }
            for (j, &y) in series[*t..*t + steps].iter().enumerate() {
                let dists = sk.step(y);
                let exp = cp["out"][j].as_array().unwrap();
                assert_eq!(exp.len(), dists.len(), "{name}@{t}: horizon count");
                for (h, d) in dists.iter().enumerate() {
                    let got = probes(d);
                    for (p, e) in exp[h].as_array().unwrap().iter().enumerate() {
                        checked += 1;
                        let e = parse_val(e);
                        if !close(got[p], e, TOL, TOL) {
                            failures.push(format!(
                                "{name}@{t} step {j} h {h} probe {p}: got {:.12e} expected {e:.12e}",
                                got[p]
                            ));
                        }
                    }
                }
            }
        }
    }
    println!(
        "resume Python -> Rust: {} scenarios, {n_cp} checkpoints, {checked} values checked",
        scenarios.len()
    );
    if !failures.is_empty() {
        let n = failures.len();
        failures.truncate(30);
        panic!("resume failures ({n}):\n{}", failures.join("\n"));
    }
}

#[test]
fn write_resume_rust() {
    let Some(v) = load_vectors() else { return };
    let series = series_of(&v);
    let times: Vec<usize> = v["times"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t.as_u64().unwrap() as usize)
        .collect();
    let mut out = Map::new();
    for name in v["scenarios"].as_object().unwrap().keys() {
        let (mut sk, _) = build_scenario(name);
        let mut cps = Map::new();
        let mut t0 = 0usize;
        for &t in &times {
            while t0 < t {
                sk.step(series[t0]);
                t0 += 1;
            }
            cps.insert(t.to_string(), sk.state_to_json());
        }
        out.insert(name.clone(), Value::Object(cps));
    }
    let mut root = Map::new();
    root.insert("scenarios".into(), Value::Object(out));
    let path = std::env::var("SKATERS_RESUME_OUT")
        .unwrap_or_else(|_| repo_file("parity/resume_rust.json"));
    std::fs::write(&path, serde_json::to_string(&Value::Object(root)).unwrap()).unwrap();
    println!("wrote {path}");
}
