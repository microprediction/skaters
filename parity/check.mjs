// Parity checker: run the JS port on the same series Python used and compare.
//
// Usage: node parity/check.mjs   (after python parity/gen_vectors.py)
// Exits non-zero if any scenario diverges beyond tolerance.

import { readFileSync } from "fs";
import { buildScenarios } from "./scenarios.mjs";
import { periodDetector } from "../docs/js/skaters/periodicity.mjs";
import { runningCov, emaCov, ledoitWolfCov } from "../docs/js/skaters/cov.mjs";

const ATOL = 1e-6;
const RTOL = 1e-6;

function decode(x) {
  if (x === "inf") return Infinity;
  if (x === "-inf") return -Infinity;
  if (x === "nan") return NaN;
  return x;
}

function close(actual, expectedRaw) {
  const expected = decode(expectedRaw);
  if (Number.isNaN(actual) && Number.isNaN(expected)) return true;
  if (!Number.isFinite(actual) || !Number.isFinite(expected)) return actual === expected;
  return Math.abs(actual - expected) <= ATOL + RTOL * Math.abs(expected);
}

function probeDist(d, probe, qLo, qHi) {
  return [d.mean, d.std, d.logpdf(probe), d.cdf(probe), d.quantile(qLo), d.quantile(qHi), d.crps(probe)];
}

function runScenario(skater, series, burn, probe, qLo, qHi) {
  let state = null;
  const out = [];
  for (let i = 0; i < series.length; i++) {
    const [dists, st] = skater(series[i], state);
    state = st;
    if (i >= burn) out.push(dists.map((d) => probeDist(d, probe, qLo, qHi)));
  }
  return out;
}

function main() {
  const vectors = JSON.parse(readFileSync(new URL("./vectors.json", import.meta.url)));
  const { series, burn, probe, q_lo: qLo, q_hi: qHi } = vectors;
  const scenarios = new Map(buildScenarios().map(([name, k, skater]) => [name, { k, skater }]));

  const LABELS = ["mean", "std", "logpdf", "cdf", "qlo", "qhi", "crps"];
  let failures = 0;
  let checked = 0;
  const missing = [];

  for (const [name, expected] of Object.entries(vectors.scenarios)) {
    const sc = scenarios.get(name);
    if (!sc) {
      missing.push(name);
      continue;
    }
    const got = runScenario(sc.skater, series, burn, probe, qLo, qHi);
    const expOut = expected.out;
    let scenarioFails = 0;
    for (let step = 0; step < expOut.length; step++) {
      for (let h = 0; h < expOut[step].length; h++) {
        for (let j = 0; j < 7; j++) {
          checked++;
          if (!close(got[step][h][j], expOut[step][h][j])) {
            scenarioFails++;
            if (scenarioFails <= 3) {
              console.error(
                `  MISMATCH ${name} step=${step + burn} h=${h} ${LABELS[j]}: ` +
                  `js=${got[step][h][j]} py=${decode(expOut[step][h][j])}`
              );
            }
          }
        }
      }
    }
    if (scenarioFails > 0) {
      failures += scenarioFails;
      console.error(`FAIL ${name}: ${scenarioFails} mismatches`);
    } else {
      console.log(`ok   ${name}`);
    }
  }

  if (missing.length) {
    console.error(`\nScenarios in vectors but missing from JS registry: ${missing.join(", ")}`);
    failures += missing.length;
  }

  // --- periodicity ---
  if (vectors.periodicity) {
    const pd = periodDetector();
    let pdState = null;
    const got = [];
    for (let i = 0; i < series.length; i++) {
      const [scores, st] = pd(series[i], pdState);
      pdState = st;
      if (i >= burn) got.push(scores);
    }
    let pdFails = 0;
    for (let step = 0; step < vectors.periodicity.length; step++) {
      const exp = vectors.periodicity[step];
      const g = got[step];
      if (g.length !== exp.length) {
        pdFails++;
        continue;
      }
      for (let r = 0; r < exp.length; r++) {
        checked += 2;
        if (g[r][0] !== exp[r][0] || !close(g[r][1], exp[r][1])) pdFails++;
      }
    }
    if (pdFails) {
      failures += pdFails;
      console.error(`FAIL periodicity: ${pdFails} mismatches`);
    } else console.log("ok   periodicity");
  }

  // --- covariance estimators ---
  if (vectors.cov) {
    const vec = vectors.vec_series;
    const estimators = {
      running: (y, st) => runningCov(y, st),
      ema: (y, st) => emaCov(y, st),
      ledoit: (y, st) => ledoitWolfCov(y, st),
    };
    for (const [nm, fn] of Object.entries(estimators)) {
      const exp = vectors.cov[nm];
      let st = null;
      const got = [];
      for (let i = 0; i < vec.length; i++) {
        const [mean, cmat, s2] = fn(vec[i], st);
        st = s2;
        if (i >= burn) got.push([mean, cmat]);
      }
      let covFails = 0;
      for (let step = 0; step < exp.length; step++) {
        for (let part = 0; part < 2; part++) {
          for (let j = 0; j < exp[step][part].length; j++) {
            checked++;
            if (!close(got[step][part][j], exp[step][part][j])) covFails++;
          }
        }
      }
      if (covFails) {
        failures += covFails;
        console.error(`FAIL cov:${nm}: ${covFails} mismatches`);
      } else console.log(`ok   cov:${nm}`);
    }
  }

  console.log(`\n${checked} values checked across ${Object.keys(vectors.scenarios).length} scenarios`);
  if (failures > 0) {
    console.error(`PARITY FAILED: ${failures} mismatches`);
    process.exit(1);
  }
  console.log("PARITY OK");
}

main();
