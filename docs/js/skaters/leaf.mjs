// Residual distribution estimator (the leaf) — JS port of skaters/leaf.py.

import { Dist } from "./dist.mjs";
import { runningVarInit, runningVarUpdate, runningVarGet } from "./runstats.mjs";

// A skater is a function (y, state) -> [dists, state].
// state is null on the first call.

export function leaf(k = 1) {
  function _leaf(y, state) {
    if (state === null || state === undefined) {
      state = { var: runningVarInit() };
    }
    state.var = runningVarUpdate(state.var, y);
    const [, varr] = runningVarGet(state.var);

    let std;
    if (Number.isFinite(varr) && varr > 0) {
      std = Math.sqrt(varr);
    } else {
      // Bootstrap: use |y| as a rough scale until we have data.
      std = Math.max(Math.abs(y), 1e-8);
    }

    const d = Dist.gaussian(0.0, std);
    const dists = new Array(k).fill(d);
    return [dists, state];
  }
  _leaf.skaterName = `leaf(k=${k})`;
  return _leaf;
}

export function heavyLeaf(k = 1, excessKurtosis = 6.0) {
  // Heavy-tailed residual model: variance-matched 2-component scale mixture.
  const C = 3.0;
  const p = Math.min(Math.max(excessKurtosis / 192.0, 0.0), 0.45);
  const varAdj = 1.0 / (1.0 + (C * C - 1.0) * p);

  function _leaf(y, state) {
    if (state === null || state === undefined) state = { var: runningVarInit() };
    state.var = runningVarUpdate(state.var, y);
    const [, varr] = runningVarGet(state.var);
    let v;
    if (Number.isFinite(varr) && varr > 0) v = varr;
    else v = Math.max(Math.abs(y), 1e-8) ** 2;

    let d;
    if (p <= 0.0) {
      d = Dist.gaussian(0.0, Math.sqrt(v));
    } else {
      const sigma1 = Math.sqrt(v * varAdj);
      d = new Dist([[1.0 - p, 0.0, sigma1], [p, 0.0, C * sigma1]]);
    }
    return [new Array(k).fill(d), state];
  }
  _leaf.skaterName = `heavy_leaf(k=${k},ek=${excessKurtosis})`;
  return _leaf;
}
