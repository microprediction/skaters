// Online conformal recalibration — JS port of skaters/conformal.py.
//
// Replaces a skater's predictive *shape* with the empirical distribution of
// recent standardized residuals (split conformal on a rolling window),
// keeping the base's location and scale. Returns a calibrated Dist.

import { Dist } from "./dist.mjs";

export function conformal(base, k = 1, window = 250, minObs = 30, nPoints = 40, bandwidth = 1.0) {
  function _skater(y, state) {
    if (state === null || state === undefined) {
      state = { base: null, z: [], pending: null };
    }

    if (state.pending !== null) {
      const [muPrev, sigmaPrev] = state.pending;
      if (sigmaPrev > 0) {
        state.z.push((y - muPrev) / sigmaPrev);
        if (state.z.length > window) state.z.shift();
      }
    }

    const [dists, baseState] = base(y, state.base);
    state.base = baseState;

    const d1 = dists[0];
    state.pending = [d1.mean, d1.std];

    const z = state.z;
    if (z.length < minObs) return [dists, state];

    const n = z.length;
    let zmean = 0.0;
    for (const v of z) zmean += v;
    zmean /= n;
    let zvar = 0.0;
    for (const v of z) zvar += (v - zmean) * (v - zmean);
    zvar /= n;
    const zstd = zvar > 0 ? Math.sqrt(zvar) : 1.0;
    const h = bandwidth * 0.9 * zstd * Math.pow(n, -0.2);

    const zs = z.slice().sort((a, b) => a - b);
    const out = [];
    for (const d of dists) {
      const mu = d.mean;
      const sigma = d.std;
      if (sigma <= 0) {
        out.push(d);
        continue;
      }
      const comps = [];
      for (let j = 0; j < nPoints; j++) {
        const q = (j + 0.5) / nPoints;
        const zq = zs[Math.min(Math.floor(q * n), n - 1)];
        comps.push([1.0 / nPoints, mu + sigma * zq, sigma * h]);
      }
      out.push(new Dist(comps));
    }
    return [out, state];
  }
  _skater.skaterName = `conformal(${base.skaterName || "?"})`;
  return _skater;
}
