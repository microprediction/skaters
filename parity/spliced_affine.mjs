// SplicedDist.affine, mirroring tests/test_spliced_affine.py. Conjugating
// laplace with an affine transform calls .affine on the predictive, which is a
// SplicedDist once the GPD tail splice is live. Execute directly or via pytest.
import assert from "node:assert/strict";
import { conjugate, laplace, standardize } from "../docs/js/skaters/index.mjs";
import { garch, emaTransform, difference, seasonalDifference, seasonalAnchor, ouTransform } from "../docs/js/skaters/transform.mjs";
import { SplicedDist } from "../docs/js/skaters/tails.mjs";

function series(n) {
  let seed = 3;
  const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const g = () => Math.sqrt(-2 * Math.log(Math.max(rnd(), 1e-12))) * Math.cos(2 * Math.PI * rnd());
  let x = 0;
  const out = [];
  for (let i = 0; i < n; i++) { x = 0.9 * x + g() * (1 + 0.5 * Math.sin(i / 7)); out.push(x); }
  return out;
}

function run(f) {
  let st = null, d = null;
  for (const y of series(1500)) [d, st] = f(y, st);
  return d[0];
}

const close = (x, y, rel, abs) => Math.abs(x - y) <= Math.max(abs, rel * Math.abs(y));

const d = run(laplace());
assert.ok(d instanceof SplicedDist, "laplace should be spliced after 1500 steps");
for (const [a, b] of [[2.5, -1.0], [0.1, 3.0], [-1.5, 0.7]]) {
  const e = d.affine(a, b);
  assert.ok(e instanceof SplicedDist);
  for (const p of [0.001, 0.05, 0.5, 0.95, 0.999]) {
    const want = a * d.quantile(a > 0 ? p : 1 - p) + b;
    assert.ok(close(e.quantile(p), want, 1e-6, 1e-9), `quantile a=${a} p=${p}`);
  }
  for (const x of [-2.0, 0.3, 4.0]) {
    const wantCdf = a > 0 ? d.cdf(x) : 1 - d.cdf(x);
    assert.ok(Math.abs(e.cdf(a * x + b) - wantCdf) <= 1e-9, `cdf a=${a} x=${x}`);
    assert.ok(Math.abs(e.logpdf(a * x + b) - (d.logpdf(x) - Math.log(Math.abs(a)))) <= 1e-6, `logpdf a=${a} x=${x}`);
  }
}
assert.throws(() => d.affine(0, 1));
for (const delta of [1.7, -0.3]) {
  const e = d.shift(delta);
  for (const p of [0.001, 0.5, 0.999]) assert.ok(close(e.quantile(p), d.quantile(p) + delta, 1e-6, 1e-9), `shift p=${p}`);
}
for (const g of [2.5, -0.4]) {
  const e = d.scale(g), f = d.affine(g, 0);
  for (const p of [0.001, 0.5, 0.999]) assert.ok(close(e.quantile(p), f.quantile(p), 1e-9, 1e-12), `scale g=${g}`);
}
assert.throws(() => d.scale(0));

for (const [name, t] of [["standardize", () => standardize(0.05)], ["garch", () => garch()], ["emaTransform", () => emaTransform(0.05)],
  ["difference", () => difference()], ["seasonalDifference", () => seasonalDifference(7)],
  ["seasonalAnchor", () => seasonalAnchor(7)], ["ouTransform", () => ouTransform()]]) {
  const p = run(conjugate(laplace(), t(), 1));
  assert.ok(Number.isFinite(p.logpdf(0.0)), `${name}: logpdf`);
  assert.ok(p.quantile(0.1) < p.quantile(0.9), `${name}: quantiles`);
}
console.log("spliced affine checks passed");
