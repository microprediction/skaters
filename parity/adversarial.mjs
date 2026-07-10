// Adversarial release gate for the JS twin.
//
// Runs the deployed default (laplace, GPD tails) over the pathological
// streams a production deployment will eventually meet — constant series,
// lattice/repeats, a monster spike, scale collapse, vol whiplash on a trend
// — and asserts the contract: forecasts stay finite and well-formed, the
// cdf stays a cdf, quantiles stay ordered, and the detector recovers after
// the insult. Mirrors tests/test_tails_robustness.py; value parity is
// check.mjs's job, surviving abuse is this file's.
//
// Run: node parity/adversarial.mjs      (exits non-zero on any violation)

import { laplace } from "../docs/js/skaters/api.mjs";

// Deterministic RNG (no Math.random in a release gate).
function lcg(seed) {
  let s = seed >>> 0;
  return () => {
    s = (1664525 * s + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
function gauss(rand) {
  let u = 0, v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

let failures = 0;
function check(cond, label) {
  if (!cond) {
    failures += 1;
    console.error(`FAIL ${label}`);
  }
}

function assertWellformed(d, yNear, label) {
  const lp = d.logpdf(yNear);
  check(!Number.isNaN(lp), `${label}: logpdf NaN`);
  const c = d.cdf(yNear);
  check(c >= 0.0 && c <= 1.0, `${label}: cdf out of [0,1]`);
  const qs = [0.001, 0.25, 0.5, 0.75, 0.999].map((p) => d.quantile(p));
  check(qs.every(Number.isFinite), `${label}: non-finite quantile`);
  for (let i = 1; i < qs.length; i++) {
    check(qs[i] >= qs[i - 1] - 1e-9, `${label}: quantiles unordered`);
  }
  const probes = [qs[0] - 1.0, ...qs, qs[qs.length - 1] + 1.0];
  const cs = probes.map((x) => d.cdf(x));
  for (let i = 1; i < cs.length; i++) {
    check(cs[i] >= cs[i - 1] - 1e-9, `${label}: cdf not monotone`);
  }
}

function soak(ys, label) {
  const f = laplace(1);
  let state = null;
  let dists = null;
  for (let t = 0; t < ys.length; t++) {
    [dists, state] = f(ys[t], state);
    if (t > 0 && t % 997 === 0) assertWellformed(dists[0], ys[t], label);
  }
  assertWellformed(dists[0], ys[ys.length - 1], label);
  return state;
}

// 1. constant series
soak(new Array(4000).fill(3.7), "constant");

// 2. lattice / repeats
{
  const rand = lcg(17);
  let v = 1.0;
  const ys = [];
  for (let i = 0; i < 6000; i++) {
    if (rand() >= 0.7) v += [-0.25, 0.25, 0.5][Math.floor(rand() * 3)];
    ys.push(v);
  }
  soak(ys, "lattice");
}

// 3. monster spike, then recovery (no deafness, no permanent alarm)
{
  const rand = lcg(23);
  const f = laplace(1);
  let state = null, dists = null;
  for (let i = 0; i < 3000; i++) [dists, state] = f(gauss(rand), state);
  [dists, state] = f(1e9, state);
  assertWellformed(dists[0], 0.0, "spike:after");
  let alarms = 0, n = 0;
  for (let i = 0; i < 3000; i++) {
    const y = gauss(rand);
    [dists, state] = f(y, state);
    const z = state.z[0];
    if (i > 1000 && z !== null) {
      n += 1;
      if (Math.abs(z) > 2.5758) alarms += 1;     // ~1e-2 two-sided
    }
    if (i % 500 === 0) assertWellformed(dists[0], y, "spike:recovery");
  }
  check(n > 1500, "spike: too few matured ticks");
  check(alarms / n < 0.06, `spike: alarm rate ${(alarms / n).toFixed(4)} after recovery`);
}

// 3b. extreme finite tick: the input gate must keep the tree alive
{
  const rand = lcg(29);
  const f = laplace(1);
  let state = null, dists = null;
  for (let i = 0; i < 1500; i++) [dists, state] = f(gauss(rand), state);
  [dists, state] = f(1e300, state);            // near the double limit
  assertWellformed(dists[0], 0.0, "extreme:after");
  for (let i = 0; i < 1500; i++) {
    [dists, state] = f(gauss(rand), state);
    if (i % 500 === 0) assertWellformed(dists[0], 0.0, "extreme:recovery");
  }
}

// 4. scale collapse and recovery
{
  const rand = lcg(31);
  const ys = [];
  for (let i = 0; i < 2000; i++) ys.push(gauss(rand));
  for (let i = 0; i < 2000; i++) ys.push(0.0);
  for (let i = 0; i < 2000; i++) ys.push(gauss(rand));
  soak(ys, "collapse");
}

// 5. vol whiplash on a trend
{
  const rand = lcg(41);
  const ys = [];
  let lvl = 0.0;
  for (let t = 0; t < 8000; t++) {
    const vol = Math.floor(t / 700) % 2 ? 10.0 : 1.0;
    lvl += 0.05 + vol * gauss(rand);
    ys.push(lvl);
  }
  soak(ys, "whiplash");
}

if (failures > 0) {
  console.error(`ADVERSARIAL GATE: ${failures} violation(s)`);
  process.exit(1);
}
console.log("ADVERSARIAL GATE OK (constant, lattice, spike, collapse, whiplash)");
