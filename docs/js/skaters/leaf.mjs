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
