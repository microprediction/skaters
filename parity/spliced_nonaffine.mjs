// Transforms that read mixture components, fed laplace's tail-spliced
// predictive, mirroring tests/test_spliced_nonaffine.py. The nonlinear
// inverses (powerTransform, yeoJohnson) emit the exact pushforward of the
// spliced law; the k>1 widening of emaTransform, seasonalDifference and
// seasonalAnchor widens the body and lets the splice follow it. gaussianize
// is not ported to JS.
//
// Optional argument: a JSON file written by tests/test_js_parity.py holding a
// Python SplicedDist (to_dict) and the Python outputs of the same transforms,
// which this script then matches to the port's 1e-6 contract. Quantiles agree
// to about 1e-12. Table-based queries (cdf, logpdf, crps) agree to about 1e-8:
// the table window comes from the 1e-6 quantiles, which clamp to a body
// quantile at 1e-12 where the JS erf and Python's differ by a few 1e-6 in x,
// and the knots move with it.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { conjugate, laplace } from "../docs/js/skaters/index.mjs";
import { emaTransform, powerTransform, seasonalAnchor, seasonalDifference, yeoJohnson } from "../docs/js/skaters/transform.mjs";
import { SplicedDist } from "../docs/js/skaters/tails.mjs";
import { PushforwardDist } from "../docs/js/skaters/pushforward.mjs";

function series(n) {
  let seed = 3;
  const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const g = () => Math.sqrt(-2 * Math.log(Math.max(rnd(), 1e-12))) * Math.cos(2 * Math.PI * rnd());
  let x = 0;
  const out = [];
  for (let i = 0; i < n; i++) { x = 0.9 * x + g() * (1 + 0.5 * Math.sin(i / 7)); out.push(x); }
  return out;
}

function run(f, n = 1500) {
  let st = null, d = null;
  for (const y of series(n)) [d, st] = f(y, st);
  return d;
}

const close = (x, y, rel, abs) => Math.abs(x - y) <= Math.max(abs, rel * Math.abs(y));

function sane(d, name) {
  assert.ok(Number.isFinite(d.logpdf(d.quantile(0.5))), `${name}: logpdf`);
  const qs = [0.001, 0.1, 0.5, 0.9, 0.999].map((p) => d.quantile(p));
  for (let i = 1; i < qs.length; i++) assert.ok(qs[i - 1] < qs[i], `${name}: quantiles increase`);
  assert.ok(Number.isFinite(d.mean) && d.std > 0, `${name}: moments`);
}

const d = run(laplace())[0];
assert.ok(d instanceof SplicedDist, "laplace should be spliced after 1500 steps");

// nonlinear inverses are the exact pushforward
const sq = (z) => Math.sign(z) * Math.abs(z) ** 2.0;
const yj0 = (z) => (z >= 0 ? Math.expm1(z) : 1.0 - Math.sqrt(1.0 - 2.0 * z));
for (const [name, make, inv] of [["powerTransform", () => powerTransform(0.5), sq],
  ["yeoJohnson", () => yeoJohnson(0.0), yj0]]) {
  const e = make().inverseK([d], {})[0];
  assert.ok(e instanceof PushforwardDist, `${name}: pushforward`);
  for (const p of [0.001, 0.05, 0.5, 0.95, 0.999]) {
    assert.ok(close(e.quantile(p), inv(d.quantile(p)), 1e-4, 1e-6), `${name}: quantile p=${p}`);
  }
  for (const z of [-1.0, 0.2, 1.5]) {
    assert.ok(Math.abs(e.cdf(inv(z)) - d.cdf(z)) <= 1e-3, `${name}: cdf z=${z}`);
  }
}

// widening moves the body and keeps the splice
{
  // widen is module-private; reach it through emaTransform's k>1 branch
  const level = 2.0, alpha = 0.05;
  const t = emaTransform(alpha);
  const [d0, d1] = t.inverseK([d, d], { level });
  assert.ok(d1 instanceof SplicedDist);
  for (const key of ["tLo", "tUp", "zetaLo", "zetaUp", "gLo", "sLo", "gUp", "sUp"]) {
    assert.equal(d1[key], d[key], `widen keeps ${key}`);
  }
  const add = alpha * alpha * d.var;
  assert.ok(close(d1.body.mean, d.body.mean + level, 1e-9, 1e-12), "widen moves the body mean");
  assert.ok(close(d1.body.var, d.body.var + add, 1e-9, 1e-12), "widen adds body variance");
  assert.ok(close(d0.quantile(0.5), d.quantile(0.5) + level, 1e-9, 1e-12), "h=1 is a shift");
}

// conjugated laplace runs once the splice is live
for (const [name, make, k] of [["powerTransform", () => powerTransform(0.5), 1],
  ["yeoJohnson", () => yeoJohnson(0.5), 1],
  ["emaTransform", () => emaTransform(0.05), 3],
  ["seasonalDifference", () => seasonalDifference(2), 3],
  ["seasonalAnchor", () => seasonalAnchor(2), 3]]) {
  const ds = run(conjugate(laplace(k), make(), k), 600);
  assert.equal(ds.length, k, `${name}: k`);
  ds.forEach((e, h) => sane(e, `${name} h=${h + 1}`));
}

// cross-language: the same spliced law through the JS transforms vs Python
if (process.argv[2]) {
  const ref = JSON.parse(readFileSync(process.argv[2], "utf8"));
  const sd = SplicedDist.fromDict(ref.dist);
  const makers = {
    power_transform: () => powerTransform(0.5),
    yeo_johnson_0: () => yeoJohnson(0.0),
    yeo_johnson_half: () => yeoJohnson(0.5),
  };
  let worst = 0.0;
  const cmp = (got, want, what) => {
    const err = Math.abs(got - want) / Math.max(1.0, Math.abs(want));
    worst = Math.max(worst, err);
    assert.ok(err <= 1e-6, `${what}: js ${got} py ${want}`);
  };
  for (const [key, want] of Object.entries(ref.pushforward)) {
    const e = makers[key]().inverseK([sd], {})[0];
    want.quantile.forEach(([p, v]) => cmp(e.quantile(p), v, `${key} quantile ${p}`));
    want.cdf.forEach(([x, v]) => cmp(e.cdf(x), v, `${key} cdf ${x}`));
    want.logpdf.forEach(([x, v]) => cmp(e.logpdf(x), v, `${key} logpdf ${x}`));
    want.crps.forEach(([x, v]) => cmp(e.crps(x), v, `${key} crps ${x}`));
    cmp(e.mean, want.mean, `${key} mean`);
    cmp(e.std, want.std, `${key} std`);
  }
  const w = ref.widen;
  const e = emaTransform(w.alpha).inverseK([sd, sd], { level: w.level })[1];
  w.quantile.forEach(([p, v]) => cmp(e.quantile(p), v, `widen quantile ${p}`));
  cmp(e.mean, w.mean, "widen mean");
  console.log(`python parity: worst relative difference ${worst.toExponential(2)}`);
}
console.log("spliced nonaffine checks passed");
