// Same numeric contracts as Python/Rust; execute directly or via pytest.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Dist } from "../docs/js/skaters/dist.mjs";
const cases = JSON.parse(readFileSync(new URL("./quantile_contract.json", import.meta.url)));
for (const c of cases) {
  const d = new Dist(c.components), q = d.quantile(c.p);
  assert.ok("expected" in c ? Math.abs(q-c.expected) <= c.atol : c.lower < q && q < c.upper, `${c.name}: q=${q}`);
  if ("cdf_tol" in c) assert.ok(Math.abs(d.cdf(q)-c.p) <= c.cdf_tol, `${c.name}: cdf=${d.cdf(q)}`);
}
const d = new Dist([[1, 0, 1e-11]]);
assert.ok(Math.abs((d.quantile(.99)-d.quantile(.01))-4.6526957480816816e-11) < 2e-20);
console.log(`${cases.length} quantile cases and tiny-scale spread passed`);

const normal = new Dist([[1,0,1]]);
assert.equal(normal.quantile(.5, 1e-9, 0), 0);
assert.equal(normal.quantile(.5, 1e-9, 1), -4);
for (const tol of [0, -1]) {
  const q = normal.quantile(.5, tol);
  assert.ok(Math.abs(q) < 1e-15 && normal.cdf(q) >= .5);
}
assert.throws(() => new Dist([[.5,-1e155,1],[.5,1e155,1]]).quantile(.5), /finite mixture variance/);
