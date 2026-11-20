// Online homogenized scale-mixture correction: JS port of skaters/homogenize.py.
//
// A small Bayesian-hedged pool of two-point Gaussian scale-mixture hypotheses
// for a skater's own PIT residual stream z_t = Phi^-1(F_{t-1}(y_t)). Each
// candidate (rho, gain, delta) carries a fixed-gain, Huber-capped filter q on
// H_2(z) = z^2 - 1, with a changepoint escape, and a discounted Bayesian
// log-weight. The pooled correction is the union of every candidate's
// (scale, weight) pairs and reshapes the base predictive as
//
//     F~(y) = H(Phi^-1(F(y))),   Q~(p) = F.quantile(Phi(H.quantile(p)))
//
// Apply it explicitly: homogenize(laplace(1)). State is plain data in the
// canonical layout of docs/STATE.md: base, raw, pending, cell, correction.

import { Dist } from "./dist.mjs";

const STD_NORMAL = Dist.gaussian(0.0, 1.0);
const EPS = 1e-12;
const LOG_SQRT2PI = Math.log(Math.sqrt(2.0 * Math.PI));

const V_MIN = 0.25, V_MAX = 9.0;
const DELTA_MAX = 0.8;
const INNOVATION_CAP = 8.0;
const ADAPT_AFTER = 10;

const WEIGHT_DECAY = 0.9999;
const LEARNING_RATE = 0.1;
const SCORE_CAP = 20.0;

function clip(x, lo, hi) {
  return x < lo ? lo : (x > hi ? hi : x);
}

function clamp01(u) {
  return Math.min(Math.max(u, EPS), 1.0 - EPS);
}

function phiInv(p) {
  return STD_NORMAL.quantile(p);
}

function phiLogpdf(z) {
  return -0.5 * z * z - LOG_SQRT2PI;
}

// --- pooled scale-mixture density: g(z) = sum_i w_i / s_i * phi(z / s_i) ---

// Log-density of the pooled (or any) scale mixture at z (log-sum-exp).
export function logg(z, correction) {
  let best = -Infinity;
  const terms = [];
  const ws = correction.weights, ss = correction.scales;
  for (let i = 0; i < ws.length; i++) {
    const w = ws[i], s = ss[i];
    if (w <= 0.0) continue;
    const t = Math.log(w) - Math.log(s) + phiLogpdf(z / s);
    terms.push(t);
    if (t > best) best = t;
  }
  if (best === -Infinity) return -Infinity;
  let acc = 0.0;
  for (const t of terms) acc += Math.exp(t - best);
  return best + Math.log(acc);
}

export function g(z, correction) {
  return Math.exp(logg(z, correction));
}

// --- candidates ---

// Static candidate grid, plus a distinguished identity candidate (frozen at
// v = 1 forever). The scale mixture is a density only for 0 <= delta < 1.
export function makeCandidates(rhoGrid = [0.0, 0.8, 0.95, 0.99], gainGrid = [0.03, 0.12],
  deltaGrid = [0.0, 0.25, 0.50], deltaMax = DELTA_MAX) {
  if (!(deltaMax >= 0.0 && deltaMax < 1.0)) {
    throw new Error(`deltaMax must satisfy 0 <= deltaMax < 1, got ${deltaMax}`);
  }
  for (const delta of deltaGrid) {
    if (!(delta >= 0.0 && delta < 1.0)) {
      throw new Error(`deltaGrid entries must satisfy 0 <= delta < 1, got ${delta}`);
    }
  }
  const candidates = [{ rho: 0.0, gain: 0.0, delta: 0.0, is_identity: true }];
  for (const rho of rhoGrid) {
    for (const gain of gainGrid) {
      for (const delta of deltaGrid) {
        candidates.push({ rho, gain, delta: clip(delta, 0.0, deltaMax), is_identity: false });
      }
    }
  }
  return candidates;
}

function candScales(v, delta) {
  if (delta <= 0.0) return [Math.sqrt(v)];
  return [Math.sqrt(v * (1.0 - delta)), Math.sqrt(v * (1.0 + delta))];
}

function candWeights(delta) {
  return delta <= 0.0 ? [1.0] : [0.5, 0.5];
}

function candLogpdf(z, v, delta) {
  return logg(z, { weights: candWeights(delta), scales: candScales(v, delta) });
}

// --- online state ---

function initState(candidates) {
  let nOther = 0;
  for (const c of candidates) if (!c.is_identity) nOther++;
  nOther = Math.max(nOther, 1);
  const dynamic = candidates.map((c) => ({
    q: 0.0, log_weight: c.is_identity ? Math.log(nOther) : 0.0, guard_run: 0,
  }));
  return { dynamic, issued: null, n: 0 };
}

function updateQ(d, cfg, x) {
  const qMinus = cfg.rho * d.q;
  const resid = x - qMinus;
  const capped = Math.abs(resid) > INNOVATION_CAP;
  d.guard_run = capped ? d.guard_run + 1 : 0;
  const used = capped && d.guard_run <= ADAPT_AFTER ? clip(resid, -INNOVATION_CAP, INNOVATION_CAP) : resid;
  d.q = qMinus + cfg.gain * used;
}

function softmax(dynamic) {
  let m = -Infinity;
  for (const d of dynamic) if (d.log_weight > m) m = d.log_weight;
  const raw = dynamic.map((d) => Math.exp(d.log_weight - m));
  let total = 0.0;
  for (const r of raw) total += r;
  return raw.map((r) => r / total);
}

// Exact Bayesian pooling: the pooled mixture is the union of every
// candidate's (scale, weight) pairs, scaled by its softmax weight.
function pool(candidates, dynamic) {
  const omega = softmax(dynamic);
  const weights = [], scales = [];
  for (let j = 0; j < candidates.length; j++) {
    const cfg = candidates[j];
    const v = clip(1.0 + dynamic[j].q, V_MIN, V_MAX);
    const ss = candScales(v, cfg.delta), cw = candWeights(cfg.delta);
    for (let i = 0; i < ss.length; i++) {
      scales.push(ss[i]);
      weights.push(omega[j] * cw[i]);
    }
  }
  return { weights, scales };
}

// Current softmax weights, in candidate order. Diagnostics only.
export function candidateWeights(state) {
  return softmax(state.dynamic);
}

// Score each candidate's pre-update correction against z, update weights,
// update each candidate's latent variance from H_2(z), then pool into the
// correction issued for the next observation. Returns [correction, state].
export function cellStep(z, state, candidates) {
  if (state === null || state === undefined) state = initState(candidates);
  const dynamic = state.dynamic;
  const x = z * z - 1.0;
  for (let j = 0; j < candidates.length; j++) {
    const cfg = candidates[j], d = dynamic[j];
    const v = clip(1.0 + d.q, V_MIN, V_MAX);
    const r = candLogpdf(z, v, cfg.delta) - phiLogpdf(z);
    d.log_weight = WEIGHT_DECAY * d.log_weight + LEARNING_RATE * clip(r, -SCORE_CAP, SCORE_CAP);
  }
  for (let j = 0; j < candidates.length; j++) updateQ(dynamic[j], candidates[j], x);
  const correction = pool(candidates, dynamic);
  state.issued = correction;
  state.n += 1;
  return [correction, state];
}

// --- HomogenizedDist: F~ = H[Phi^-1(F(.))], H the pooled scale mixture ---

const QGRID_N = 32;
const QGRID_P = Array.from({ length: QGRID_N }, (_, i) => (i + 0.5) / QGRID_N);
const QGRID_W = 1.0 / QGRID_N;

export class HomogenizedDist {
  constructor(base, correction) {
    this.base = base;
    this.correction = correction;
    this._qgrid = null;
  }

  _z(y) {
    return phiInv(clamp01(this.base.cdf(y)));
  }

  _zCdf(z) {
    let total = 0.0;
    const ws = this.correction.weights, ss = this.correction.scales;
    for (let i = 0; i < ws.length; i++) total += ws[i] * STD_NORMAL.cdf(z / ss[i]);
    return clamp01(total);
  }

  _zQuantile(p, tol = 1e-9, maxIter = 100) {
    let lo = -40.0, hi = 40.0;
    for (let i = 0; i < maxIter; i++) {
      const mid = 0.5 * (lo + hi);
      if (this._zCdf(mid) < p) lo = mid;
      else hi = mid;
      if (hi - lo < tol) break;
    }
    return 0.5 * (lo + hi);
  }

  cdf(y) {
    return this._zCdf(this._z(y));
  }

  logpdf(y) {
    const z = this._z(y);
    return this.base.logpdf(y) + logg(z, this.correction) - phiLogpdf(z);
  }

  pdf(y) {
    const lp = this.logpdf(y);
    return lp > -700.0 ? Math.exp(lp) : 0.0;
  }

  quantile(p, tol = 1e-9, maxIter = 2100) {
    if (!(p > 0 && p < 1)) throw new Error("quantile p must be in (0, 1)");
    const hp = this._zQuantile(p, tol, maxIter);
    const u = clamp01(STD_NORMAL.cdf(hp));
    return this.base.quantile(u, tol, maxIter);
  }

  _quantileGrid() {
    if (this._qgrid === null) this._qgrid = QGRID_P.map((p) => this.quantile(p));
    return this._qgrid;
  }

  get mean() {
    let s = 0.0;
    for (const q of this._quantileGrid()) s += q;
    return s * QGRID_W;
  }

  get var() {
    const q = this._quantileGrid();
    const mu = this.mean;
    let s = 0.0;
    for (const qi of q) s += (qi - mu) ** 2;
    return s * QGRID_W;
  }

  get std() {
    const v = this.var;
    return v > 0 ? Math.sqrt(v) : 0.0;
  }

  // CRPS via the quantile-form identity (Gneiting & Raftery 2007).
  crps(x) {
    const q = this._quantileGrid();
    let total = 0.0;
    for (let i = 0; i < QGRID_N; i++) {
      const ind = x <= q[i] ? 1.0 : 0.0;
      total += (q[i] - x) * (ind - QGRID_P[i]);
    }
    return 2.0 * total * QGRID_W;
  }

  toString() {
    return `HomogenizedDist(components=${this.correction.weights.length})`;
  }
}

// --- the wrapper ---

// Borrow strength across horizons, in place. "weights" pulls each candidate's
// log-weight toward its cross-horizon mean; "state" pulls each candidate's q_m
// toward q_{m-1}. lam = 0 is independence, lam = 1 full pooling.
function couple(cells, mode, lam) {
  const live = cells.filter((c) => c !== null);
  if (live.length < 2 || lam <= 0.0) return;
  const n = live[0].dynamic.length;
  if (mode === "weights") {
    for (let i = 0; i < n; i++) {
      let s = 0.0;
      for (const c of live) s += c.dynamic[i].log_weight;
      const meanW = s / live.length;
      for (const c of live) {
        const d = c.dynamic[i];
        d.log_weight = (1.0 - lam) * d.log_weight + lam * meanW;
      }
    }
  } else if (mode === "state") {
    const idxs = [];
    for (let j = 0; j < cells.length; j++) if (cells[j] !== null) idxs.push(j);
    for (let i = 0; i < n; i++) {
      let prev = null;
      for (const j of idxs) {
        const d = cells[j].dynamic[i];
        if (prev !== null) d.q = (1.0 - lam) * d.q + lam * prev;
        prev = d.q;
      }
    }
  }
}

// Wrap a skater with an online homogenized scale-mixture correction, one
// candidate pool per horizon (horizon m is scored against the m-step
// predictive issued m steps ago). couple: "none", "weights", "state" or
// "shared". At k = 1 this is a single pool.
export function homogenize(base, candidates = null, k = 1, coupleMode = "none", lam = 0.25) {
  if (!(k >= 1)) throw new Error("homogenize needs k >= 1");
  if (!["none", "weights", "state", "shared"].includes(coupleMode)) {
    throw new Error(`couple must be one of none, weights, state, shared; got ${coupleMode}`);
  }
  const cands = candidates !== null && candidates !== undefined ? candidates : makeCandidates();

  function _skater(y, state) {
    if (state === null || state === undefined) {
      state = { base: null, raw: null, pending: [], cell: new Array(k).fill(null), correction: new Array(k).fill(null) };
    }
    const s = state;
    const pend = s.pending;
    const n = pend.length;
    for (let m = 1; m <= k; m++) {
      if (m > n) continue;
      const dM = pend[n - m][m - 1];
      const u = clamp01(dM.cdf(y));
      const z = phiInv(u);
      if (Number.isNaN(z)) continue;
      const slot = coupleMode === "shared" ? 0 : m - 1;
      const [corr, cell] = cellStep(z, s.cell[slot], cands);
      s.cell[slot] = cell;
      if (coupleMode === "shared") {
        for (let j = 0; j < k; j++) s.correction[j] = corr;
      } else {
        s.correction[m - 1] = corr;
      }
    }

    if (coupleMode === "weights" || coupleMode === "state") {
      couple(s.cell, coupleMode, lam);
      for (let m = 0; m < k; m++) {
        if (s.cell[m] !== null) s.correction[m] = pool(cands, s.cell[m].dynamic);
      }
    }

    const [dists, bs] = base(y, s.base);
    s.base = bs;
    s.raw = dists[0];
    pend.push(dists.slice());
    if (pend.length > k) pend.shift();

    const out = [];
    for (let m = 1; m <= k; m++) {
      const d = m - 1 < dists.length ? dists[m - 1] : dists[dists.length - 1];
      const corr = s.correction[m - 1];
      out.push(corr === null ? d : new HomogenizedDist(d, corr));
    }
    return [out, s];
  }
  _skater.skaterName = `homogenize(${base.skaterName || "?"}, k=${k})`;
  return _skater;
}
