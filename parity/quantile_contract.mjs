// Inverse-CDF contract gate for the JS twin.
//
// `quantile` is documented as the inverse of `cdf`. Four mixture geometries
// broke that round-trip before the localized-bracket fix, and each one killed
// a different candidate repair:
//
//   1. tiny scale          — an ABSOLUTE stopping tolerance exceeds the whole
//                            bracket, so bisection stops after one halving;
//   2. far low-weight      — a mixture-moment bracket excludes the component
//      component            that owns the quantile, so it returns its own edge;
//   3. narrow inside wide  — a tolerance scaled to the MIXTURE sigma is too
//                            coarse for the narrow component;
//   4. astronomical        — bisecting the global span needs ~133 halvings
//      separation           against max_iter = 100.
//
// Mirrors tests/test_quantile_inverse_contract.py and
// rust/tests/quantile_contract.rs: the same numbers must hold in every port.
//
// Run: node parity/quantile_contract.mjs      (exits non-zero on any violation)

import { Dist } from "../docs/js/skaters/dist.mjs";

let failures = 0;

function check(name, ok, detail) {
  if (ok) {
    console.log(`ok   ${name}`);
  } else {
    console.log(`FAIL ${name}: ${detail}`);
    failures += 1;
  }
}

function roundtripErr(d, p) {
  return Math.abs(d.cdf(d.quantile(p)) - p);
}

// 1. tiny scale
{
  const d = new Dist([[1.0, 0.0, 1e-11]]);
  for (const p of [0.01, 0.5, 0.99]) {
    const e = roundtripErr(d, p);
    check(`tiny_scale p=${p}`, e < 1e-6, `roundtrip err ${e}`);
  }
  const q = d.quantile(0.99);
  check("tiny_scale value", Math.abs(q - 2.3263478740408408e-11) < 1e-13, `got ${q}`);
}

// 2. far low-weight component
{
  const d = new Dist([[0.9999, 0.0, 1.0], [1e-4, 1000.0, 1.0]]);
  const p = 1 - 1e-6;
  const q = d.quantile(p);
  check("far_component reaches it", q > 990.0, `stuck at bracket edge: ${q}`);
  check("far_component roundtrip", roundtripErr(d, p) < 1e-5, `err ${roundtripErr(d, p)}`);
}

// 3. narrow component inside a wide mixture
{
  const d = new Dist([[0.5, 0.0, 1e-11], [0.5, 1000.0, 1.0]]);
  const q = d.quantile(0.25);
  check("narrow_inside_wide roundtrip", roundtripErr(d, 0.25) < 1e-6, `err ${roundtripErr(d, 0.25)}`);
  check("narrow_inside_wide value", Math.abs(q) < 1e-9, `p=0.25 sits at the narrow median, got ${q}`);
}

// 4. astronomical separation beside a narrow component
for (const sep of [1e20, 1e40, 1e80]) {
  const d = new Dist([[0.5, 0.0, 1e-11], [0.5, sep, 1.0]]);
  for (const p of [0.25, 0.75]) {
    const e = roundtripErr(d, p);
    check(`astronomical sep=${sep} p=${p}`, e < 1e-6, `roundtrip err ${e}, q=${d.quantile(p)}`);
  }
}

// 5. deep tail: parade derives z through this call, so termination stays in
//    x-space. A probability-space exit blunts this from ~7.03 to ~6.0.
{
  const d = new Dist([[1.0, 0.0, 1.0]]);
  const z = d.quantile(1 - 1e-12);
  check("deep_tail diagnostic", Math.abs(z - 7.034481104929) < 1e-4, `got ${z}`);
}

// 6. unit scale must be untouched by the localization
{
  const d = new Dist([[0.6, 0.0, 1.0], [0.4, 3.0, 2.0]]);
  for (const p of [0.1, 0.5, 0.9]) {
    check(`unit_scale p=${p}`, roundtripErr(d, p) < 1e-6, `err ${roundtripErr(d, p)}`);
  }
}

if (failures > 0) {
  console.log(`\n${failures} inverse-CDF contract violation(s)`);
  process.exit(1);
}
console.log("\nall inverse-CDF contract checks passed");
