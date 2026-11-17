//! Shared numeric contracts, including the two regressions from #176.
use skaters::dist::Dist;

#[test]
fn inverse_contract() {
    let cases: Vec<serde_json::Value> =
        serde_json::from_str(include_str!("../../parity/quantile_contract.json")).unwrap();
    for c in cases {
        let components: Vec<(f64, f64, f64)> =
            serde_json::from_value(c["components"].clone()).unwrap();
        let d = Dist::new(components);
        let p = c["p"].as_f64().unwrap();
        let q = d.quantile(p);
        let ok = if let Some(x) = c["expected"].as_f64() {
            (q - x).abs() <= c["atol"].as_f64().unwrap()
        } else {
            c["lower"].as_f64().unwrap() < q && q < c["upper"].as_f64().unwrap()
        };
        assert!(ok, "{}: q={q}", c["name"]);
        if let Some(t) = c["cdf_tol"].as_f64() {
            assert!(
                (d.cdf(q) - p).abs() <= t,
                "{}: q={q}, cdf={}",
                c["name"],
                d.cdf(q)
            );
        }
    }
}

#[test]
fn tiny_spread_is_preserved() {
    let d = Dist::new(vec![(1.0, 0.0, 1e-11)]);
    assert!(((d.quantile(0.99) - d.quantile(0.01)) - 4.6526957480816816e-11).abs() < 2e-20);
}

#[test]
fn explicit_budget_and_resolution_stop() {
    let d = Dist::new(vec![(1.0, 0.0, 1.0)]);
    assert_eq!(d.quantile_tol(0.5, 1e-9, 0), 0.0);
    assert_eq!(d.quantile_tol(0.5, 1e-9, 1), -4.0);
    for tol in [0.0, -1.0] {
        let q = d.quantile_tol(0.5, tol, 2100);
        assert!(q.abs() < 1e-15 && d.cdf(q) >= 0.5);
    }
}
#[test]
#[cfg(not(target_arch = "wasm32"))]
#[should_panic(expected = "finite mixture variance")]
fn variance_overflow_is_explicit() {
    Dist::new(vec![(0.5, -1e155, 1.0), (0.5, 1e155, 1.0)]).quantile(0.5);
}
