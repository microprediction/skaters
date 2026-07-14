//! Deployment robustness and portability contracts for the Rust core.
//! Mirrors the Python/JS adversarial gates (constant, lattice, monster
//! spike, extreme tick, scale collapse, vol whiplash) plus the two
//! contracts a backend must keep: bitwise determinism and serde
//! checkpoint-resume equivalence.

use skaters_core::api::{laplace, Forecaster};
use skaters_core::tails::PDist;

// Deterministic LCG + Box-Muller-free gaussian via sum of uniforms is NOT
// used; mirror adversarial.mjs exactly: LCG + Box-Muller with libm.
struct Lcg(u32);
impl Lcg {
    fn next(&mut self) -> f64 {
        self.0 = self.0.wrapping_mul(1664525).wrapping_add(1013904223);
        self.0 as f64 / 4294967296.0
    }
    fn gauss(&mut self) -> f64 {
        let mut u = 0.0;
        while u == 0.0 { u = self.next(); }
        let mut v = 0.0;
        while v == 0.0 { v = self.next(); }
        libm::sqrt(-2.0 * libm::log(u)) * libm::cos(2.0 * core::f64::consts::PI * v)
    }
}

fn assert_wellformed(d: &PDist, y_near: f64, label: &str) {
    let lp = d.logpdf(y_near);
    assert!(!lp.is_nan(), "{label}: logpdf NaN");
    let c = d.cdf(y_near);
    assert!((0.0..=1.0).contains(&c), "{label}: cdf out of range");
    let qs: Vec<f64> = [0.001, 0.25, 0.5, 0.75, 0.999]
        .iter().map(|p| d.quantile(*p)).collect();
    assert!(qs.iter().all(|q| q.is_finite()), "{label}: non-finite quantile");
    for w in qs.windows(2) {
        assert!(w[1] >= w[0] - 1e-9, "{label}: quantiles unordered");
    }
}

fn soak(ys: &[f64], label: &str) {
    let mut f = laplace(1);
    let mut last = Vec::new();
    for (t, y) in ys.iter().enumerate() {
        last = f.step(*y);
        if t > 0 && t % 997 == 0 {
            assert_wellformed(&last[0], *y, label);
        }
    }
    assert_wellformed(&last[0], *ys.last().unwrap(), label);
}

#[test]
fn constant_series() {
    soak(&vec![3.7; 4000], "constant");
}

#[test]
fn lattice_series() {
    let mut r = Lcg(17);
    let mut v = 1.0;
    let mut ys = Vec::new();
    for _ in 0..6000 {
        if r.next() >= 0.7 {
            let step = [-0.25, 0.25, 0.5][(r.next() * 3.0) as usize % 3];
            v += step;
        }
        ys.push(v);
    }
    soak(&ys, "lattice");
}

#[test]
fn monster_spike_then_recovery() {
    let mut r = Lcg(23);
    let mut f = laplace(1);
    for _ in 0..3000 { f.step(r.gauss()); }
    let d = f.step(1e9);
    assert_wellformed(&d[0], 0.0, "spike:after");
    let mut alarms = 0usize;
    let mut n = 0usize;
    for i in 0..3000 {
        let y = r.gauss();
        let d = f.step(y);
        if i > 1000 {
            n += 1;
            // ~1e-2 two-sided via the spliced cdf
            let u = d[0].cdf(y);
            if !(0.005..=0.995).contains(&u) { alarms += 1; }
        }
        if i % 500 == 0 { assert_wellformed(&d[0], y, "spike:recovery"); }
    }
    assert!(n > 1500);
    assert!((alarms as f64) / (n as f64) < 0.06, "no recovery: {alarms}/{n}");
}

#[test]
fn extreme_finite_tick() {
    let mut r = Lcg(29);
    let mut f = laplace(1);
    for _ in 0..1500 { f.step(r.gauss()); }
    let d = f.step(1e300);
    assert_wellformed(&d[0], 0.0, "extreme:after");
    for i in 0..1500 {
        let d = f.step(r.gauss());
        if i % 500 == 0 { assert_wellformed(&d[0], 0.0, "extreme:recovery"); }
    }
}

#[test]
fn scale_collapse_and_recovery() {
    let mut r = Lcg(31);
    let mut ys = Vec::new();
    for _ in 0..2000 { ys.push(r.gauss()); }
    for _ in 0..2000 { ys.push(0.0); }
    for _ in 0..2000 { ys.push(r.gauss()); }
    soak(&ys, "collapse");
}

#[test]
fn vol_whiplash_on_trend() {
    let mut r = Lcg(41);
    let mut lvl = 0.0;
    let mut ys = Vec::new();
    for t in 0..8000 {
        let vol = if (t / 700) % 2 == 1 { 10.0 } else { 1.0 };
        lvl += 0.05 + vol * r.gauss();
        ys.push(lvl);
    }
    soak(&ys, "whiplash");
}

#[test]
fn bitwise_determinism() {
    let run = || {
        let mut r = Lcg(7);
        let mut f = laplace(1);
        let mut acc: u64 = 0xcbf29ce484222325;
        for t in 0..900 {
            let d = f.step(r.gauss());
            if t % 97 == 0 {
                for v in [d[0].logpdf(0.3), d[0].cdf(0.3), d[0].quantile(0.1)] {
                    acc ^= v.to_bits();
                    acc = acc.wrapping_mul(0x100000001b3);
                }
            }
        }
        acc
    };
    assert_eq!(run(), run(), "two identical runs diverged");
}

#[test]
fn serde_checkpoint_resume_bit_exact() {
    let mut r = Lcg(13);
    let ys: Vec<f64> = (0..900).map(|_| r.gauss()).collect();
    let mut straight = laplace(1);
    for y in &ys[..700] { straight.step(*y); }
    let json = serde_json::to_string(&straight).expect("serialize");
    let mut resumed: Forecaster = serde_json::from_str(&json).expect("deserialize");
    for y in &ys[700..] {
        let a = straight.step(*y);
        let b = resumed.step(*y);
        assert_eq!(a[0].logpdf(0.3).to_bits(), b[0].logpdf(0.3).to_bits(),
                   "resume diverged");
    }
}

#[test]
fn search_checkpoint_resume_bit_exact() {
    // The search state (pool of live Sk values plus recipes) is plain data:
    // checkpoint past an expansion (n_obs 100) and resume bit-exactly, with
    // the infinite cost budget surviving the JSON round trip.
    use skaters_core::search::search;
    use skaters_core::skater::Sk;
    let mut r = Lcg(19);
    let ys: Vec<f64> = (0..300).map(|_| r.gauss()).collect();
    let mut straight = Sk::Search(Box::new(search(1)));
    for y in &ys[..150] { straight.step(*y); }
    let json = serde_json::to_string(&straight).expect("serialize");
    let mut resumed: Sk = serde_json::from_str(&json).expect("deserialize");
    for y in &ys[150..] {
        let a = straight.step(*y);
        let b = resumed.step(*y);
        assert_eq!(a[0].logpdf(0.3).to_bits(), b[0].logpdf(0.3).to_bits(),
                   "search resume diverged");
    }
}
