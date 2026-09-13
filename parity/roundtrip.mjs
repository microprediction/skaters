// State round-trip gate for the JS twin: a skater is a fold.
//
// For every exported skater, over a seeded series, the state must survive
//
//     stateFromJSON(JSON.parse(JSON.stringify(stateToJSON(state))))
//
// bit-exactly: at each checkpoint the restored copy is stepped alongside the
// original and both the predictive distributions and the states must
// JSON-serialise to identical bytes, on the restore step and on every step
// after it (so a sign-of-zero or a hidden closure cannot slip through). The
// walker also fails the gate if a function, Map, Set, typed array, foreign
// class, undefined, or non-finite number appears anywhere in a state.
//
// Run: node parity/roundtrip.mjs      (exits non-zero on any violation)

import { buildScenarios, buildRepeatScenarios } from "./scenarios.mjs";
import { stateToJSON, stateFromJSON, assertPlainState } from "../docs/js/skaters/state.mjs";
import { Dist } from "../docs/js/skaters/dist.mjs";
import { laplace } from "../docs/js/skaters/api.mjs";
import { parade } from "../docs/js/skaters/parade.mjs";
import { gpdtails } from "../docs/js/skaters/tails.mjs";
import { terminalLeafEnsemble } from "../docs/js/skaters/terminal.mjs";
import { conjugate } from "../docs/js/skaters/conjugate.mjs";
import { leaf } from "../docs/js/skaters/leaf.mjs";
import { ema } from "../docs/js/skaters/ema.mjs";
import { difference, emaTransform, seasonalAnchor } from "../docs/js/skaters/transform.mjs";
import { sticky } from "../docs/js/skaters/sticky.mjs";

const N = 620;          // long enough for the default GPD splice (warmup 500) to fire
const EVERY = 100;      // checkpoint cadence
const CONTINUE = 25;    // steps both copies run after each restore

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
function makeSeries(n, seed) {
  const rand = lcg(seed);
  const out = [];
  let lvl = 0.0;
  for (let t = 0; t < n; t++) {
    lvl += 0.3 * gauss(rand);
    out.push(lvl + 2.0 * Math.sin(2 * Math.PI * t / 7) + gauss(rand));
  }
  out[Math.floor(n / 2)] += 12.0;   // one spike, so the tails and sticky paths see abuse
  return out;
}
function makeRepeatSeries(n, seed) {
  const rand = lcg(seed);
  const out = [];
  let v = 1.0;
  for (let t = 0; t < n; t++) {
    if (rand() >= 0.7) v += [-0.25, 0.25, 0.5][Math.floor(rand() * 3)];
    out.push(v);
  }
  return out;
}

function enc(x) { return JSON.stringify(stateToJSON(x)); }

function firstDiff(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  const lo = Math.max(0, i - 60);
  return `at char ${i}\n    orig: ...${a.slice(lo, i + 60)}\n    back: ...${b.slice(lo, i + 60)}`;
}

let failures = 0;
function fail(msg) { failures += 1; console.error(`FAIL ${msg}`); }
let sawSpliced = false;   // the gate must have met a SplicedDist inside a state

function soak(name, f, series) {
  let state = null;
  let dists = null;
  for (let t = 0; t < series.length; t++) {
    try {
      [dists, state] = f(series[t], state);
      assertPlainState(state);
    } catch (e) {
      fail(`${name} t=${t}: ${e.message}`);
      return;
    }
    if ((t + 1) % EVERY !== 0 && t !== series.length - CONTINUE - 1) continue;

    // Checkpoint, restore, and hold the restored copy to the original.
    const textA = enc(state);
    if (textA.includes('"spliced":true')) sawSpliced = true;
    let restored;
    try {
      restored = stateFromJSON(JSON.parse(textA));
    } catch (e) {
      fail(`${name} t=${t}: restore threw: ${e.message}`);
      return;
    }
    const textB = enc(restored);
    if (textA !== textB) {
      fail(`${name} t=${t}: re-encoded restore differs ${firstDiff(textA, textB)}`);
      return;
    }
    let sA = state, sB = restored;
    for (let m = 1; m <= CONTINUE && t + m < series.length; m++) {
      const y = series[t + m];
      let dA, dB;
      [dA, sA] = f(y, sA);
      [dB, sB] = f(y, sB);
      const da = enc(dA), db = enc(dB);
      if (da !== db) {
        fail(`${name} t=${t} +${m}: predictive differs after restore ${firstDiff(da, db)}`);
        return;
      }
      const sa = enc(sA), sb = enc(sB);
      if (sa !== sb) {
        fail(`${name} t=${t} +${m}: state differs after restore ${firstDiff(sa, sb)}`);
        return;
      }
    }
    // The original copy carries on from where the fork left it.
    state = sA;
    t += Math.min(CONTINUE, series.length - 1 - t);
  }
}

function distRoundTrip() {
  // Dist.fromDict(toDict()) must be the identity on normalised weights, bit for bit.
  const rand = lcg(7);
  for (let trial = 0; trial < 500; trial++) {
    const n = 1 + Math.floor(rand() * 9);
    const comps = [];
    for (let i = 0; i < n; i++) comps.push([rand() + 1e-3, 4 * gauss(rand), 0.1 + rand()]);
    const d = new Dist(comps);
    const back = Dist.fromDict(JSON.parse(JSON.stringify(d.toDict())));
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < 3; j++) {
        if (!Object.is(back.components[i][j], d.components[i][j])) {
          fail(`Dist round trip moved bits: trial ${trial} component ${i} field ${j}`);
          return;
        }
      }
    }
  }
  // ...and still normalises a hand-written dict whose weights do not sum to one.
  const loose = Dist.fromDict({ components: [[1.0, 0.0, 1.0], [3.0, 1.0, 1.0]] });
  if (loose.components[0][0] !== 0.25) fail("Dist.fromDict did not normalise unnormalised weights");
}

function main() {
  distRoundTrip();

  const series = makeSeries(N, 12345);
  const repeat = makeRepeatSeries(N, 99);

  const scenarios = buildScenarios().map(([name, , f]) => [name, f, series]);
  for (const [name, , f] of buildRepeatScenarios()) scenarios.push([name, f, repeat]);

  // Paths the parity roster does not cover but a checkpoint will meet.
  const fastTails = (k) => gpdtails(conjugate(leaf(k), emaTransform(0.1), k), k, 0.9, 50, 100);
  scenarios.push(["parade_laplace", parade(laplace(1), 1), series]);           // SplicedDist in pending after warmup 500
  scenarios.push(["parade_laplace_k3", parade(laplace(3), 3), series]);
  scenarios.push(["parade_fast_tails", parade(fastTails(1), 1), series]);      // SplicedDist in pending from t~100
  scenarios.push(["parade_fast_tails_k3", parade(fastTails(3), 3), series]);
  scenarios.push(["laplace_gaussian_tails", laplace(1, "crps", true, null, 0.03, "gaussian"), series]);
  scenarios.push(["laplace_likelihood", laplace(1, "likelihood"), series]);
  scenarios.push(["terminal_leaf", terminalLeafEnsemble(
    [ema(0.05, 1), conjugate(leaf(1), difference(), 1)], { k: 1, depths: [0, 1] }), series]);
  scenarios.push(["terminal_leaf_k3", terminalLeafEnsemble(
    [ema(0.05, 3), conjugate(leaf(3), difference(), 3)], { k: 3, depths: [0, 1], forget: 0.99 }), series]);
  scenarios.push(["seasonal_anchor", conjugate(leaf(1), seasonalAnchor(7), 1), series]);
  scenarios.push(["sticky_laplace_repeat", laplace(1), repeat]);
  scenarios.push(["sticky_ema_series", sticky(conjugate(leaf(1), emaTransform(0.1), 1), 1), series]);

  const t0 = Date.now();
  for (const [name, f, ys] of scenarios) soak(name, f, ys);
  const secs = ((Date.now() - t0) / 1000).toFixed(1);

  if (!sawSpliced) fail("no checkpoint contained a SplicedDist: the spliced restore path went untested");

  if (failures > 0) {
    console.error(`ROUND-TRIP GATE FAILED: ${failures} violation(s) across ${scenarios.length} skaters`);
    process.exit(1);
  }
  console.log(`ROUND-TRIP GATE OK: ${scenarios.length} skaters, ${N} steps each, checkpoint every ${EVERY}, ${secs}s`);
}

main();
