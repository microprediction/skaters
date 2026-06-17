// Sticky (zero-inflation) wrapper — JS port of skaters/sticky.py.
// Lattice-aware, mean-preserving repetition atom: gate p = EWMA(exact repeat)
// decides whether to fire; location = recency-weighted modal value (the lattice
// attractor). The continuous part is recentered so the atom never moves the
// ensemble mean. Still a plain Dist. Uses a Map for numeric-key insertion order
// matching Python's dict (so the argmax tie-break matches).

import { Dist } from "./dist.mjs";

export function sticky(base, k = 1, propensityAlpha = 0.05, spikeFrac = 0.005, pruneEps = 1e-6) {
  function _skater(y, state) {
    if (state === null || state === undefined) {
      state = { base: null, last: null, p: 0.0, n: 0, counts: new Map() };
    }
    const [dists, baseState] = base(y, state.base);
    state.base = baseState;
    state.n += 1;

    // gate: recency-weighted probability that the value repeats exactly.
    if (state.last !== null) {
      const a = propensityAlpha > 1.0 / state.n ? propensityAlpha : 1.0 / state.n;
      const repeat = y === state.last ? 1.0 : 0.0;
      state.p = (1 - a) * state.p + a * repeat;
    }

    // location: recency-weighted modal value (the lattice attractor).
    const c = state.counts;
    const drop = [];
    for (const key of c.keys()) {
      const v = c.get(key) * (1.0 - propensityAlpha);
      if (v < pruneEps) drop.push(key);
      else c.set(key, v);
    }
    for (const key of drop) c.delete(key);
    c.set(y, (c.get(y) || 0.0) + propensityAlpha);
    let mode = null, best = -Infinity;
    for (const [key, v] of c) {
      if (v > best) { best = v; mode = key; }   // first max in insertion order
    }

    const p = state.p;
    const pc = 1.0 - p;
    const out = [];
    for (const d of dists) {
      if (p <= 1e-6) {
        out.push(d);
        continue;
      }
      const spikeStd = Math.max(spikeFrac * d.std, 1e-9);
      if (pc <= 1e-9) {
        out.push(new Dist([[1.0, mode, spikeStd]]));
        continue;
      }
      const mu = d.mean;
      const delta = (p * (mu - mode)) / pc;
      const comps = [[p, mode, spikeStd]];
      for (const [w, m, s] of d.components) comps.push([pc * w, m + delta, s]);
      out.push(new Dist(comps));
    }
    state.last = y;
    return [out, state];
  }
  _skater.skaterName = `sticky(${base.skaterName || "?"})`;
  return _skater;
}
