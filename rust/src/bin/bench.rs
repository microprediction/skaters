//! Timing loop: microseconds per tick for laplace(1) over 5000 ticks.
//! The input series is the parity vectors' embedded series, tiled — fully
//! deterministic, no RNG dependency.

use skaters_core::api::laplace;
use std::time::Instant;

fn main() {
    let raw = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/parity/vectors.json"
    ))
    .expect("parity/vectors.json");
    let v: serde_json::Value = serde_json::from_str(&raw).unwrap();
    let series: Vec<f64> = v["series"]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_f64().unwrap())
        .collect();

    let n = 5000usize;
    let ticks: Vec<f64> = (0..n).map(|i| series[i % series.len()]).collect();

    // Warm-up pass (allocator, caches), then the timed pass on a fresh skater.
    let mut warm = laplace(1);
    for &y in ticks.iter().take(500) {
        let _ = warm.step(y);
    }

    // Step-only cost: consume each tick's predictive with a cheap query (cdf),
    // so the optimizer cannot drop the work but no numeric-grid moment of the
    // tail-spliced predictive is triggered.
    let mut f = laplace(1);
    let mut acc = 0.0_f64;
    let start = Instant::now();
    for &y in &ticks {
        let dists = f.step(y);
        acc += dists[0].cdf(y);
    }
    let elapsed = start.elapsed();
    let us_step = elapsed.as_secs_f64() * 1e6 / n as f64;
    println!(
        "laplace(1) step:        {n} ticks in {:.3} s -> {us_step:.1} us/tick (checksum {acc:.6})",
        elapsed.as_secs_f64()
    );

    // Step plus a mean read per tick. Once the GPD tails activate the mean of
    // a spliced predictive is a 65-node quantile grid, so this is the
    // expensive-probe variant.
    let mut f2 = laplace(1);
    let mut acc2 = 0.0_f64;
    let start2 = Instant::now();
    for &y in &ticks {
        let dists = f2.step(y);
        acc2 += dists[0].mean();
    }
    let elapsed2 = start2.elapsed();
    let us_mean = elapsed2.as_secs_f64() * 1e6 / n as f64;
    println!(
        "laplace(1) step + mean: {n} ticks in {:.3} s -> {us_mean:.1} us/tick (checksum {acc2:.6})",
        elapsed2.as_secs_f64()
    );
}
