// PushforwardDist.affine/shift/scale, mirroring tests/test_pushforward_affine.py:
// the law of a*Y + b, for a table-built and an analytic pushforward.
import assert from "node:assert/strict";
import { Dist } from "../docs/js/skaters/dist.mjs";
import { PushforwardDist } from "../docs/js/skaters/pushforward.mjs";
import { logTransform, yeoJohnson } from "../docs/js/skaters/transform.mjs";

const approx = (x, y, rel, abs) => Math.abs(x - y) <= Math.max(abs, rel * Math.abs(y));
const inner = new Dist([[0.6, 0.2, 0.7], [0.4, -0.5, 1.3]]);
const kinds = {
  table: yeoJohnson(0.0, true).inverseK([inner], {})[0],
  analytic: logTransform().inverseK([inner], {})[0],
};
for (const [kind, d] of Object.entries(kinds)) {
  for (const [a, b] of [[2.5, -1.0], [0.3, 4.0], [-1.7, 0.5]]) {
    const e = d.affine(a, b);
    const tag = `${kind} a=${a}`;
    assert.ok(e instanceof PushforwardDist, tag);
    for (const p of [0.01, 0.2, 0.5, 0.8, 0.99]) {
      assert.ok(approx(e.quantile(p), a * d.quantile(a > 0 ? p : 1 - p) + b, 1e-7, 1e-9), `${tag} q${p}`);
    }
    for (const p of [0.05, 0.4, 0.9]) {
      const x = d.quantile(p), y = a * x + b;
      const wantCdf = a > 0 ? d.cdf(x) : 1 - d.cdf(x);
      assert.ok(Math.abs(e.cdf(y) - wantCdf) <= 1e-7, `${tag} cdf`);
      assert.ok(Math.abs(e.logpdf(y) - (d.logpdf(x) - Math.log(Math.abs(a)))) <= 1e-4, `${tag} logpdf`);
    }
    assert.ok(approx(e.mean, a * d.mean + b, 1e-6, 1e-9), `${tag} mean`);
    assert.ok(approx(e.std, Math.abs(a) * d.std, 1e-6, 0), `${tag} std`);
    const x3 = d.quantile(0.3);
    assert.ok(approx(e.crps(a * x3 + b), Math.abs(a) * d.crps(x3), 1e-3, 0), `${tag} crps`);
  }
}
const d = kinds.table;
assert.ok(approx(d.shift(1.5).quantile(0.3), d.quantile(0.3) + 1.5, 1e-12, 1e-12));
assert.ok(approx(d.scale(-2.0).quantile(0.3), -2.0 * d.quantile(0.7), 1e-9, 1e-12));
assert.throws(() => d.scale(0.0));
assert.throws(() => d.affine(0.0, 1.0));
console.log("pushforward affine checks passed");
