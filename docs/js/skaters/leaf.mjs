// Residual distribution estimator (the leaf) — JS port of skaters/leaf.py.

import { Dist, erf } from "./dist.mjs";
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

const SCALE_BASIS = [0.7, 1.0, 1.6, 3.0, 6.0];

// Fixed Gaussian scale mixture, online-EM weights + EWMA scale — the
// "discrepancy from N(0,1)" leaf. JS port of scale_mixture_leaf.
export function scaleMixtureLeaf(k = 1, gamma = 0.02, scaleAlpha = 0.01, scales = SCALE_BASIS) {
  const C = scales.slice();
  const K = C.length;
  let oneIdx = 0;
  let best = Infinity;
  for (let i = 0; i < K; i++) {
    const dd = Math.abs(C[i] - 1.0);
    if (dd < best) { best = dd; oneIdx = i; }
  }

  function _leaf(y, state) {
    if (state === null || state === undefined) {
      const w = new Array(K).fill(1e-6);
      w[oneIdx] = 1.0;
      state = { v: 0.0, w, n: 0 };
    }
    state.n += 1;
    const a = scaleAlpha > 1.0 / state.n ? scaleAlpha : 1.0 / state.n;
    state.v = (1 - a) * state.v + a * y * y;
    const varr = state.v;
    const sigma = Number.isFinite(varr) && varr > 0 ? Math.sqrt(varr) : Math.max(Math.abs(y), 1e-8);
    const z = y / sigma;
    const w = state.w;
    const dens = new Array(K);
    let total = 0.0;
    for (let i = 0; i < K; i++) {
      dens[i] = w[i] * Math.exp(-0.5 * z * z / (C[i] * C[i])) / C[i];
      total += dens[i];
    }
    if (total > 0) {
      const g = gamma > 1.0 / state.n ? gamma : 1.0 / state.n;
      state.w = w.map((wi, i) => (1 - g) * wi + g * dens[i] / total);
    }
    const comps = C.map((c, i) => [state.w[i], 0.0, c * sigma]);
    const d = new Dist(comps);
    return [new Array(k).fill(d), state];
  }
  _leaf.skaterName = `scale_mixture_leaf(k=${k})`;
  return _leaf;
}

// CRPS leaf — JS port of skaters/leaf.py:crps_leaf. Same scale-mixture form,
// weights fit by online CRPS-gradient (exponentiated gradient on the simplex).
const S2 = Math.sqrt(2.0);
const INV = 1.0 / Math.sqrt(2.0 * Math.PI);
const A0 = 2.0 * INV;
const FINE = [0.4, 0.512, 0.6554, 0.8389, 1.0737, 1.3744, 1.7592, 2.2518, 2.8823, 3.6893, 4.7224, 6.0446, 7.7371, 9.9035, 12.6765];

function phiStd(x) { return Math.exp(-0.5 * x * x) * INV; }
function PhiStd(x) { return 0.5 * (1.0 + erf(x / S2)); }
function absNormal(m, s) {
  if (s <= 0) return Math.abs(m);
  const z = m / s;
  return m * (2.0 * PhiStd(z) - 1.0) + 2.0 * s * phiStd(z);
}

export function crpsLeaf(k = 1, eta = 1.0, scaleAlpha = 0.01, scales = FINE) {
  const C = scales.slice();
  const K = C.length;
  const B = C.map((ca) => C.map((cb) => Math.sqrt(ca * ca + cb * cb) * A0));
  let oneIdx = 0, best = Infinity;
  for (let i = 0; i < K; i++) { const d = Math.abs(C[i] - 1.0); if (d < best) { best = d; oneIdx = i; } }

  function _leaf(y, state) {
    if (state === null || state === undefined) {
      const w = new Array(K).fill(1e-6); w[oneIdx] = 1.0;
      state = { v: 0.0, w, n: 0 };
    }
    state.n += 1;
    const a = scaleAlpha > 1.0 / state.n ? scaleAlpha : 1.0 / state.n;
    state.v = (1 - a) * state.v + a * y * y;
    const sig = Number.isFinite(state.v) && state.v > 0 ? Math.sqrt(state.v) : Math.max(Math.abs(y), 1e-8);
    const z = y / sig;
    const w = state.w;
    const g = new Array(K);
    for (let c = 0; c < K; c++) {
      let dot = 0.0;
      for (let j = 0; j < K; j++) dot += w[j] * B[c][j];
      g[c] = absNormal(-z, C[c]) - dot;
    }
    let gm = 0.0; for (let c = 0; c < K; c++) gm += g[c]; gm /= K;
    const nw = new Array(K);
    let Z = 0.0;
    for (let c = 0; c < K; c++) { nw[c] = w[c] * Math.exp(-eta * (g[c] - gm)); Z += nw[c]; }
    state.w = nw.map((x) => x / Z);
    const comps = C.map((c, i) => [state.w[i], 0.0, c * sig]);
    return [new Array(k).fill(new Dist(comps)), state];
  }
  _leaf.skaterName = `crps_leaf(k=${k}, eta=${eta})`;
  return _leaf;
}
