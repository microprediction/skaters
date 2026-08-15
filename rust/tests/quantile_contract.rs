//! `quantile` must invert `cdf` at every scale and for uneven mixtures.
//!
//! Rust mirror of `tests/test_quantile_inverse_contract.py`. Three regimes
//! broke the documented inverse-CDF contract:
//!
//! 1. tiny scales — the absolute tolerance exceeded the whole bracket, so
//!    bisection stopped after one halving (median of N(0, 1e-11) resolved
//!    to the ~0.003rd percentile);
//! 2. tiny-weight far components — the mixture-moment bracket excluded the
//!    answer, so bisection returned the bracket edge (~80 instead of
//!    1002.3263);
//! 3. astronomical separation beside a narrow component — bisecting the
//!    whole span needs ~133 halvings against max_iter = 100.
//!
//! The fix localizes before bisecting: sorted component +/- 8 sigma
//! endpoints are binary-searched for a gap containing p; the tolerance is
//! `tol` times the SMALLEST component sigma (which the narrow-inside-wide
//! case pins); termination stays in x-space (the deep-tail case pins this
//! — parade derives its z diagnostic through this function); and the
//! result is the `cdf >= p` endpoint rather than the midpoint.

use skaters_core::dist::Dist;

fn roundtrip_err(d: &Dist, p: f64) -> f64 {
    (d.cdf(d.quantile(p)) - p).abs()
}

#[test]
fn quantile_inverts_cdf_at_tiny_scale() {
    let d = Dist::new(vec![(1.0, 0.0, 1e-11)]);
    for p in [0.01, 0.5, 0.99] {
        assert!(roundtrip_err(&d, p) < 1e-6, "p={p} err={}", roundtrip_err(&d, p));
    }
    assert!((d.quantile(0.99) - 2.3263478740408408e-11).abs() < 1e-13);
}

#[test]
fn quantile_reaches_tiny_weight_far_component() {
    let d = Dist::new(vec![(0.9999, 0.0, 1.0), (1e-4, 1000.0, 1.0)]);
    let p = 1.0 - 1e-6;
    let q = d.quantile(p);
    assert!(q > 990.0, "quantile stuck at bracket edge: {q}");
    assert!(roundtrip_err(&d, p) < 1e-5);
}

#[test]
fn quantile_mixed_scales_narrow_inside_wide() {
    let d = Dist::new(vec![(0.5, 0.0, 1e-11), (0.5, 1000.0, 1.0)]);
    let q = d.quantile(0.25);
    assert!(roundtrip_err(&d, 0.25) < 1e-6, "q={q} cdf={}", d.cdf(q));
    assert!(q.abs() < 1e-9, "p=0.25 lives at the narrow component median, got {q}");
}

#[test]
fn quantile_astronomical_separation_with_narrow_component() {
    // Bisecting the GLOBAL span needs ~133 halvings to reach the narrow
    // component's scale, against max_iter = 100. Localizing to the endpoint
    // gap that contains p keeps the search where the tolerance can resolve.
    for sep in [1e20_f64, 1e40, 1e80] {
        let d = Dist::new(vec![(0.5, 0.0, 1e-11), (0.5, sep, 1.0)]);
        for p in [0.25_f64, 0.75] {
            let e = roundtrip_err(&d, p);
            assert!(e < 1e-6, "sep={sep} p={p} err={e} q={}", d.quantile(p));
        }
    }
}

#[test]
fn quantile_preserves_deep_tail_diagnostic() {
    // parade derives z = Phi^-1(pit) through this call; the clamp lands at
    // ~7.03 and a probability-space exit would blunt it to ~6.0 — that gap
    // is what this pins. Tolerance is 1e-4, not 1e-6: the Rust erf differs
    // from the Python reference by ~1.9e-6 in x at |z| ~ 7 (Python
    // 7.034481104929, Rust 7.034483039286). That difference is inherited
    // from erf and is IDENTICAL on pristine main — it is not introduced by
    // the bracket/tolerance change.
    let d = Dist::new(vec![(1.0, 0.0, 1.0)]);
    let z = d.quantile(1.0 - 1e-12);
    assert!((z - 7.034481104929).abs() < 1e-4, "deep-tail z was {z}");
    assert!(z > 6.5, "probability-space exit would have blunted this to ~6.0");
}

#[test]
fn quantile_unit_scale_unchanged() {
    let d = Dist::new(vec![(0.6, 0.0, 1.0), (0.4, 3.0, 2.0)]);
    for p in [0.1, 0.5, 0.9] {
        assert!(roundtrip_err(&d, p) < 1e-6);
    }
}
