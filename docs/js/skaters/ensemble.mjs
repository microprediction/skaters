// Precision-weighted ensemble — JS port of skaters/ensemble.py.

import { Dist } from "./dist.mjs";
import { runningVarInit, runningVarUpdate, runningMseGet } from "./runstats.mjs";

export function precisionWeightedEnsemble(skaters, k = 1, floor = 1e-6) {
  const n = skaters.length;
  if (n <= 0) throw new Error("ensemble needs at least one skater");

  function _skater(y, state) {
    if (state === null || state === undefined) {
      state = {
        sub: new Array(n).fill(null),
        queues: Array.from({ length: n }, () => Array.from({ length: k }, () => [])),
        stats: Array.from({ length: n }, () =>
          Array.from({ length: k }, () => runningVarInit())
        ),
      };
    }

    const allDists = [];
    for (let i = 0; i < n; i++) {
      const [distsI, sub] = skaters[i](y, state.sub[i]);
      state.sub[i] = sub;
      allDists.push(distsI);
    }

    for (let i = 0; i < n; i++) {
      for (let h = 0; h < k; h++) {
        const q = state.queues[i][h];
        if (q.length) {
          const predMean = q.shift();
          const error = y - predMean;
          state.stats[i][h] = runningVarUpdate(state.stats[i][h], error);
        }
        state.queues[i][h].push(allDists[i][h].mean);
      }
    }

    const combined = [];
    for (let h = 0; h < k; h++) {
      const weights = [];
      for (let i = 0; i < n; i++) {
        const mse = runningMseGet(state.stats[i][h]);
        let w = Number.isFinite(mse) && mse > 0 ? 1.0 / mse : floor;
        weights.push(Math.max(w, floor));
      }
      const horizonDists = [];
      for (let i = 0; i < n; i++) horizonDists.push(allDists[i][h]);
      combined.push(Dist.combine(horizonDists, weights));
    }
    return [combined, state];
  }
  _skater.skaterName = `precision_weighted_ensemble(n=${n}, k=${k})`;
  return _skater;
}
