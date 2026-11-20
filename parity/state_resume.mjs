// Cross-language resume, JS side. Driven by tests/test_js_state_resume.py.
//
//   node parity/state_resume.mjs <python checkpoints.json> <js checkpoints out.json>
//
// For the named skater: load each Python checkpoint with stateFromJSON, step
// `continue` observations, and match Python's probes to 1e-6. Then run the
// stream from scratch in JS: at each checkpoint the JS state must have exactly
// Python's key layout (docs/STATE.md), and its JSON plus the probes of the
// next outputs are written for Python to resume. Names must match the
// registry in tests/test_js_state_resume.py.

import { readFileSync, writeFileSync } from "node:fs";
import { buildScenarios, buildWrapperScenarios } from "./scenarios.mjs";
import { stateToJSON, stateFromJSON } from "../docs/js/skaters/state.mjs";
import {
  laplace, flesaker, dantzig, granger, loadGrangerParams, multiscale, parade, sticky, homogenize,
  residualTransform, conjugate, leaf, ema, precisionWeightedEnsemble, bayesianEnsemble,
  terminalLeafEnsemble, search, scaleMixtureLeaf, crpsLeaf, garchLeaf,
  emaTransform, difference, ar, powerTransform, logTransform,
} from "../docs/js/skaters/index.mjs";
import { seasonalAnchor } from "../docs/js/skaters/transform.mjs";
import { gpdtails } from "../docs/js/skaters/tails.mjs";

const ATOL = 1e-6, RTOL = 1e-6;

const c = (t, k = 1) => conjugate(leaf(k), t, k);

// A fresh instance of a parity scenario (scenarios.mjs), by name, or null.
function parityScenario(name) {
  for (const [n, , f] of [...buildScenarios(), ...buildWrapperScenarios()]) if (n === name) return f;
  return null;
}

async function registry(name) {
  if (parityScenario(name) !== null) return () => parityScenario(name);
  const grangerParams = name === "granger" ? await loadGrangerParams("monthly") : null;
  const extra = {
    conjugate_seasonal_anchor: () => c(seasonalAnchor(7)),
    conjugate_ar_default: () => c(ar(2)),
    conjugate_power_positive: () => c(powerTransform(0.5)),
    conjugate_log_transform: () => c(logTransform()),
    laplace: () => laplace(1),
    laplace_k3: () => laplace(3),
    laplace_likelihood: () => laplace(1, "likelihood"),
    laplace_gaussian_tails: () => laplace(1, "crps", true, null, 0.03, "gaussian"),
    laplace_scales: () => laplace(4, "crps", true, [1, 2]),
    laplace_garch_leaf: () => laplace(1, "crps", true, null, 0.03, "gpd", garchLeaf),
    laplace_repeat: () => laplace(1),
    laplace_gaps: () => laplace(1),
    laplace_k3_gaps: () => laplace(3),
    granger: () => granger(grangerParams, 1),
    flesaker: () => flesaker(1, -100.0),
    dantzig: () => dantzig(1, { expandInterval: 50 }),
    search_k2: () => search({ k: 2, expandInterval: 40, maxPool: 12 }),
    multiscale_k4: () => multiscale((kk) => c(emaTransform(0.1), kk), 4),
    parade_spliced: () => parade(gpdtails(c(emaTransform(0.1)), 1, 0.98, 50, 100), 1),
    sticky_ema_repeat: () => sticky(c(emaTransform(0.1)), 1),
    homogenize_laplace: () => homogenize(laplace(1)),
    residual_transform_laplace: () => residualTransform(laplace(1)),
    pw_ensemble_k2: () => precisionWeightedEnsemble([ema(0.05, 2), ema(0.2, 2)], 2),
    bayes_ensemble_k2: () => bayesianEnsemble([ema(0.05, 2), c(difference(), 2)],
      { k: 2, learningRate: 0.5, complexityPenalty: 0.0 }),
    terminal_k3: () => terminalLeafEnsemble([ema(0.05, 3), c(difference(), 3)],
      { k: 3, depths: [0, 1], forget: 0.99 }),
    scale_mixture_leaf_long: () => scaleMixtureLeaf(1),
    crps_leaf_long: () => crpsLeaf(1),
    garch_leaf_long: () => garchLeaf(1),
  };
  if (!(name in extra)) throw new Error(`no JS skater registered as ${name}`);
  return extra[name];
}

function decode(x) {
  if (x === "nan") return NaN;
  if (x === "inf") return Infinity;
  if (x === "-inf") return -Infinity;
  return x;
}
function clean(x) {
  if (Number.isNaN(x)) return "nan";
  if (x === Infinity) return "inf";
  if (x === -Infinity) return "-inf";
  return x;
}
function close(a, b) {
  a = decode(a); b = decode(b);
  if (Number.isNaN(a) && Number.isNaN(b)) return true;
  if (!Number.isFinite(a) || !Number.isFinite(b)) return a === b;
  return Math.abs(a - b) <= ATOL + RTOL * Math.abs(b);
}
function probe(dists, p) {
  return dists.map((d) => [d.mean, d.std, d.logpdf(p), d.cdf(p), d.quantile(0.1), d.quantile(0.9), d.crps(p)].map(clean));
}

// Key paths of a JSON state, arrays flattened, with the kind of each leaf.
// Python ints and floats are both numbers here.
function layout(o, path, acc) {
  if (Array.isArray(o)) { for (const x of o) layout(x, `${path}[]`, acc); return acc; }
  if (o !== null && typeof o === "object") {
    for (const k of Object.keys(o)) { acc.add(`${path}.${k}`); layout(o[k], `${path}.${k}`, acc); }
    return acc;
  }
  acc.add(`${path}:${o === null ? "null" : typeof o}`);
  return acc;
}

async function main() {
  const [pyPath, outPath] = process.argv.slice(2);
  const py = JSON.parse(readFileSync(pyPath, "utf8"));
  const { name, probe: p } = py;
  const nCont = py.continue;
  const series = py.series.map(decode);
  const make = await registry(name);
  const fails = [];

  // 1. Resume each Python checkpoint.
  for (const cp of py.checkpoints) {
    const f = make();
    let state = stateFromJSON(cp.state);
    for (let m = 0; m < nCont; m++) {
      let d;
      [d, state] = f(series[cp.t + 1 + m], state);
      const got = probe(d, p), want = cp.probes[m];
      if (got.length !== want.length) { fails.push(`t=${cp.t} +${m + 1}: ${got.length} horizons, want ${want.length}`); continue; }
      for (let h = 0; h < want.length; h++) {
        for (let j = 0; j < 7; j++) {
          if (!close(got[h][j], want[h][j])) {
            fails.push(`t=${cp.t} +${m + 1} h=${h} probe${j}: js-from-python ${got[h][j]} python ${want[h][j]}`);
          }
        }
      }
    }
  }

  // 2. Run the stream in JS; check the layout; write JS checkpoints.
  const ts = new Set(py.checkpoints.map((cp) => cp.t));
  const pyByT = new Map(py.checkpoints.map((cp) => [cp.t, cp]));
  const f = make();
  let state = null;
  const out = [];
  const last = Math.max(...ts);
  for (let t = 0; t <= last; t++) {
    [, state] = f(series[t], state);
    if (!ts.has(t)) continue;
    const plain = stateToJSON(state);
    const text = JSON.stringify(plain);
    const a = layout(JSON.parse(text), "", new Set()), b = layout(pyByT.get(t).state, "", new Set());
    const onlyJs = [...a].filter((x) => !b.has(x)), onlyPy = [...b].filter((x) => !a.has(x));
    if (onlyJs.length || onlyPy.length) {
      fails.push(`t=${t}: JS state layout differs from Python's\n    js only: ${onlyJs.slice(0, 8).join("  ")}\n    py only: ${onlyPy.slice(0, 8).join("  ")}`);
    }
    // probes of the next outputs, from a copy so the stream itself carries on
    const g = make();
    let s2 = stateFromJSON(JSON.parse(text));
    const probes = [];
    for (let m = 0; m < nCont; m++) {
      let d;
      [d, s2] = g(series[t + 1 + m], s2);
      probes.push(probe(d, p));
    }
    out.push({ t, state: JSON.parse(text), probes });
  }
  writeFileSync(outPath, JSON.stringify({ name, checkpoints: out }));

  if (fails.length) {
    console.error(`FAIL ${name}: ${fails.length} problem(s)`);
    for (const m of fails.slice(0, 10)) console.error(`  ${m}`);
    process.exit(1);
  }
  console.log(`ok   ${name}: ${py.checkpoints.length} Python checkpoint(s) resumed, layout matches`);
}

main();
