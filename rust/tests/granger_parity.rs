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
    ys: Vec<Option<f64>>,    // null = a missing observation
    rows: Vec<Vec<Option<f64>>>,
}

#[test]
fn granger_matches_python() {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../parity/granger_vectors.json");
    let s = std::fs::read_to_string(path).expect("run parity/gen_granger_vectors.py first");
    let all: BTreeMap<String, Stream> = serde_json::from_str(&s).unwrap();
    let mut worst = 0.0f64;
    for (key, st) in &all {
        let freq = key.split('/').next().unwrap();
        let mut g = Granger::shipped(freq).expect("shipped set");
        let ys: Vec<f64> = st.ys.iter().map(|v| v.unwrap_or(f64::NAN)).collect();
        for (t, y) in ys[..ys.len() - 1].iter().enumerate() {
            let m = g.step(*y);
            let got = [m.logpdf(ys[t + 1]), m.mean(), m.std(), m.w[0], m.quantile(0.1), m.quantile(0.9)];
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
