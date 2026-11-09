//! Time per update: laplace(1) against granger (monthly parameters), warm.
use skaters::{laplace, Granger};
use std::time::Instant;

fn main() {
    let mut s: u64 = 7;
    let mut rnd = move || {
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        (s as f64 / u64::MAX as f64) - 0.5
    };
    let ys: Vec<f64> = (0..3000).map(|_| rnd() + rnd() + rnd()).collect();
    let mut f = laplace(1);
    let t = Instant::now();
    for y in &ys { f.step(*y); }
    let lap = t.elapsed().as_secs_f64() / ys.len() as f64 * 1e6;
    let mut g = Granger::shipped("monthly").unwrap();
    let t = Instant::now();
    for y in &ys { g.step(*y); }
    let gr = t.elapsed().as_secs_f64() / ys.len() as f64 * 1e6;
    println!("laplace {lap:.1} us/update, granger {gr:.1} us/update, ratio {:.2}", gr / lap);
}
