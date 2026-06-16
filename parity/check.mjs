// Parity checker: run the JS port on the same series Python used and compare.
//
// Usage: node parity/check.mjs   (after python parity/gen_vectors.py)
// Exits non-zero if any scenario diverges beyond tolerance.

import { readFileSync } from "fs";
import { buildScenarios } from "./scenarios.mjs";

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
  return [d.mean, d.std, d.logpdf(probe), d.cdf(probe), d.quantile(qLo), d.quantile(qHi)];
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

  const LABELS = ["mean", "std", "logpdf", "cdf", "qlo", "qhi"];
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
        for (let j = 0; j < 6; j++) {
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

  console.log(`\n${checked} values checked across ${Object.keys(vectors.scenarios).length} scenarios`);
  if (failures > 0) {
    console.error(`PARITY FAILED: ${failures} mismatches`);
    process.exit(1);
  }
  console.log("PARITY OK");
}

main();
