// Sticky (zero-inflation) wrapper — JS port of skaters/sticky.py.
// Blends a near-Dirac spike at the last value (weight p = online repeat
// probability) with the base skater's Dist. Still a plain Dist.

import { Dist } from "./dist.mjs";

export function sticky(base, k = 1, propensityAlpha = 0.05, spikeFrac = 0.005) {
  function _skater(y, state) {
    if (state === null || state === undefined) {
      state = { base: null, last: null, p: 0.0, n: 0 };
    }
    const [dists, baseState] = base(y, state.base);
    state.base = baseState;
    state.n += 1;
    if (state.last !== null) {
      const a = propensityAlpha > 1.0 / state.n ? propensityAlpha : 1.0 / state.n;
      const repeat = y === state.last ? 1.0 : 0.0;
      state.p = (1 - a) * state.p + a * repeat;
    }
    const p = state.p;
    const spikeAt = y;

    const out = [];
    for (const d of dists) {
      if (p > 1e-6) {
        const spikeStd = Math.max(spikeFrac * d.std, 1e-9);
        const comps = [[p, spikeAt, spikeStd]];
        for (const [w, m, s] of d.components) comps.push([(1 - p) * w, m, s]);
        out.push(new Dist(comps));
      } else {
        out.push(d);
      }
    }
    state.last = y;
    return [out, state];
  }
  _skater.skaterName = `sticky(${base.skaterName || "?"})`;
  return _skater;
}
