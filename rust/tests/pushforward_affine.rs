//! PushforwardDist::affine/shift/scale, mirroring tests/test_pushforward_affine.py:
//! the law of a*Y + b, for a table-built and an analytic pushforward.

use skaters::tails::PDist;
use skaters::transform::{log_transform, yeo_johnson_exact};
use skaters::Dist;

fn approx(x: f64, y: f64, rel: f64, abs: f64) -> bool {
    (x - y).abs() <= abs.max(rel * y.abs())
}

fn kinds() -> Vec<(&'static str, PDist)> {
    let inner = PDist::Mix(Dist::new(vec![(0.6, 0.2, 0.7), (0.4, -0.5, 1.3)]));
    let table = yeo_johnson_exact(0.0, true)
        .inverse_k_p(&[inner.clone()])
        .remove(0);
    let analytic = log_transform(None, None).inverse_k_p(&[inner]).remove(0);
    vec![("table", table), ("analytic", analytic)]
}

#[test]
fn affine_is_the_change_of_variables() {
    for (kind, d) in kinds() {
        for (a, b) in [(2.5, -1.0), (0.3, 4.0), (-1.7, 0.5)] {
            let e = d.affine(a, b);
            assert!(matches!(e, PDist::Push(_)), "{kind}");
            for p in [0.01, 0.2, 0.5, 0.8, 0.99] {
                let want = a * d.quantile(if a > 0.0 { p } else { 1.0 - p }) + b;
                assert!(approx(e.quantile(p), want, 1e-7, 1e-9), "{kind} a={a} q{p}");
            }
            for p in [0.05, 0.4, 0.9] {
                let x = d.quantile(p);
                let y = a * x + b;
                let want_cdf = if a > 0.0 { d.cdf(x) } else { 1.0 - d.cdf(x) };
                assert!((e.cdf(y) - want_cdf).abs() <= 1e-7, "{kind} a={a} cdf");
                let want_lp = d.logpdf(x) - a.abs().ln();
                assert!((e.logpdf(y) - want_lp).abs() <= 1e-4, "{kind} a={a} logpdf");
            }
            assert!(
                approx(e.mean(), a * d.mean() + b, 1e-6, 1e-9),
                "{kind} a={a} mean"
            );
            assert!(
                approx(e.std(), a.abs() * d.std(), 1e-6, 0.0),
                "{kind} a={a} std"
            );
            let x3 = d.quantile(0.3);
            assert!(
                approx(e.crps(a * x3 + b), a.abs() * d.crps(x3), 1e-3, 0.0),
                "{kind} crps"
            );
        }
    }
}

#[test]
fn shift_and_scale() {
    let d = kinds().remove(0).1;
    assert!(approx(
        d.shift(1.5).quantile(0.3),
        d.quantile(0.3) + 1.5,
        1e-12,
        1e-12
    ));
    assert!(approx(
        d.scale(-2.0).quantile(0.3),
        -2.0 * d.quantile(0.7),
        1e-9,
        1e-12
    ));
    assert!(std::panic::catch_unwind(|| d.scale(0.0)).is_err());
    assert!(std::panic::catch_unwind(|| d.affine(0.0, 1.0)).is_err());
}
