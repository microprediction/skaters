//! State compatibility within Rust: the native serde layout (which older
//! skaters-fast checkpoints use) still loads, including from before the fields
//! this release added; the canonical layout round-trips bit for bit; `null`
//! is a fresh state; an old JS checkpoint without the terminal ensemble's
//! `adapt` still loads.

mod common;

use common::{build_scenario, probes, same_bits};
use serde_json::Value;
use skaters::api::{laplace, Forecaster};
use skaters::state::State;

fn series(n: usize) -> Vec<f64> {
    (0..n)
        .map(|t| (t as f64 / 3.0).sin() * 2.0 + ((t * 7919) % 101) as f64 / 50.0 - 1.0)
        .collect()
}

fn assert_same_run(a: &mut Forecaster, b: &mut Forecaster, ys: &[f64], label: &str) {
    for &y in ys {
        let (da, db) = (a.step(y), b.step(y));
        for (x, z) in da.iter().zip(db.iter()) {
            let (pa, pb) = (probes(x), probes(z));
            assert!(
                pa.iter().zip(pb.iter()).all(|(p, q)| same_bits(*p, *q)),
                "{label}: resumed run differs"
            );
        }
    }
}

/// Remove keys this release added to the native layout, recursively.
fn strip_new_keys(v: &mut Value) {
    match v {
        Value::Object(m) => {
            for k in [
                "prior_log_weights",
                "adaptive_temperature",
                "temp_rho",
                "temp_band",
                "adapt",
                "bare",
            ] {
                m.remove(k);
            }
            for x in m.values_mut() {
                strip_new_keys(x);
            }
        }
        Value::Array(a) => a.iter_mut().for_each(strip_new_keys),
        _ => {}
    }
}

#[test]
fn native_serde_layout_still_loads() {
    let ys = series(260);
    for k in [1, 3] {
        let mut f = laplace(k);
        for &y in &ys[..220] {
            f.step(y);
        }
        let mut v = serde_json::to_value(&f).unwrap();
        strip_new_keys(&mut v);
        let text = serde_json::to_string(&v).unwrap();
        let mut g: Forecaster = serde_json::from_str(&text).unwrap();
        assert_same_run(&mut f, &mut g, &ys[220..], "native");
    }
}

#[test]
fn canonical_roundtrip_and_null() {
    let ys = series(120);
    for name in [
        "pol_laplace_k3",
        "terminal_adapt_k3",
        "homogenize_state_k3",
        "residual_m2",
        "dantzig",
    ] {
        let (mut f, _) = build_scenario(name);
        let (fresh, _) = build_scenario(name);
        assert!(
            fresh.state_to_json().is_null(),
            "{name}: a fresh state is null"
        );
        for &y in &ys[..80] {
            f.step(y);
        }
        let text = serde_json::to_string(&f.state_to_json()).unwrap();
        let (mut g, _) = build_scenario(name);
        g.load_state(&serde_json::from_str(&text).unwrap()).unwrap();
        assert_eq!(serde_json::to_string(&g.state_to_json()).unwrap(), text);
        assert_same_run(&mut f, &mut g, &ys[80..], name);
        // loading null resets a used skater to fresh
        g.load_state(&Value::Null).unwrap();
        let (mut h, _) = build_scenario(name);
        assert!(g.state_to_json().is_null());
        assert_same_run(&mut g, &mut h, &ys[..40], "null reset");
    }
}

#[test]
fn old_js_terminal_without_adapt_loads() {
    let ys = series(60);
    let (mut t, _) = build_scenario("terminal_adapt");
    for &y in &ys[..30] {
        t.step(y);
    }
    let mut v = t.state_to_json();
    v.as_object_mut().unwrap().remove("adapt");
    let (mut g, _) = build_scenario("terminal_adapt");
    g.load_state(&v).unwrap();
    assert!(
        !g.state_to_json()["adapt"].is_null(),
        "adapt restarts fresh"
    );
    g.step(ys[30]);
}
