//! Portable math helpers. All transcendentals route through `libm` (pure Rust)
//! so results are bit-identical across x86 / ARM / wasm32. `sqrt` is IEEE-exact
//! and may use the std method.

pub const SQRT2: f64 = 1.4142135623730951;
pub const SQRT2PI: f64 = 2.5066282746310002;
pub const LOG_SQRT2PI: f64 = 0.9189385332046727;

/// Neumaier-compensated sum, matching CPython 3.12+'s built-in `sum()` on
/// floats. The Python reference uses `sum()` for Dist normalisation, moments
/// and several dot products; the port must reproduce it or pruning tie-breaks
/// diverge. (Same routine as `fsum` in the JS twin, docs/js/skaters/dist.mjs.)
pub fn fsum<I: IntoIterator<Item = f64>>(values: I) -> f64 {
    let mut s = 0.0_f64;
    let mut c = 0.0_f64;
    for x in values {
        let t = s + x;
        if s.abs() >= x.abs() {
            c += (s - t) + x;
        } else {
            c += (x - t) + s;
        }
        s = t;
    }
    s + c
}

pub fn gaussian_pdf(x: f64, mean: f64, std: f64) -> f64 {
    if std <= 0.0 {
        return if x == mean { f64::INFINITY } else { 0.0 };
    }
    let z = (x - mean) / std;
    libm::exp(-0.5 * z * z) / (std * SQRT2PI)
}

pub fn gaussian_cdf(x: f64, mean: f64, std: f64) -> f64 {
    if std <= 0.0 {
        return if x >= mean { 1.0 } else { 0.0 };
    }
    0.5 * (1.0 + libm::erf((x - mean) / (std * SQRT2)))
}

/// E|N(m, s^2)| = m(2*Phi(m/s) - 1) + 2s*phi(m/s). (Used by CRPS.)
pub fn abs_expectation(m: f64, s: f64) -> f64 {
    if s <= 0.0 {
        return m.abs();
    }
    let z = m / s;
    m * (2.0 * gaussian_cdf(z, 0.0, 1.0) - 1.0) + 2.0 * s * gaussian_pdf(z, 0.0, 1.0)
}
