// Online residual-transform wrapper: JS port of skaters/residual_transform.py.
//
// Learns a monotone correction in z-space from the skater's own resolved
// residuals z_t = Phi^-1(F_{t-1}(y_t)) and composes it with the base
// predictive:
//
//     F~(y) = H(Phi^-1(F(y))),   Q~(p) = F.quantile(Phi(H.quantile(p)))
//
//   m0  identity        H = N(0, 1)
//   m1  dynamic scale   H = N(0, exp(ell)),  ell' = a*ell + c*(z^2 - 1)
//   m2  + leverage      ell' = a*ell + b*z + c*(z^2 - 1)
//
// a, b, c are learned online by an RMSProp-normalised gradient step with an
// RTRL-lite sensitivity filter. State (docs/STATE.md): base, raw, z, learner,
// theta.

import { Dist } from "./dist.mjs";

const STD_NORMAL = Dist.gaussian(0.0, 1.0);
const EPS = 1e-12;
const LOG_SQRT2PI = Math.log(Math.sqrt(2.0 * Math.PI));

const A_MIN = 0.0, A_MAX = 0.995;
const BC_MAX = 3.0;
const ELL_MIN = -20.0, ELL_MAX = 20.0;
const SENS_MAX = 50.0;
const GRAD_MAX = 3.0;

const QGRID_N = 32;
const QGRID_P = Array.from({ length: QGRID_N }, (_, i) => (i + 0.5) / QGRID_N);
const QGRID_W = 1.0 / QGRID_N;

function phiInv(p) {
  return STD_NORMAL.quantile(p);
}

function clamp01(u) {
  return Math.min(Math.max(u, EPS), 1.0 - EPS);
}

function clip(x, lo, hi) {
  return x < lo ? lo : (x > hi ? hi : x);
}

// --- families: H as three pure functions of (z or p, theta) ---

export const IDENTITY_FAMILY = Object.freeze({
  cdf: (z, theta) => STD_NORMAL.cdf(z),
  quantile: (p, theta) => phiInv(p),
  logpdf: (z, theta) => -0.5 * z * z - LOG_SQRT2PI,
});

export const GAUSSIAN_SHIFT_SCALE_FAMILY = Object.freeze({
  cdf: (z, theta) => STD_NORMAL.cdf((z - theta.m) / Math.exp(0.5 * theta.ell)),
  quantile: (p, theta) => theta.m + Math.exp(0.5 * theta.ell) * phiInv(p),
  logpdf: (z, theta) => {
    const sigma = Math.exp(0.5 * theta.ell);
    const zz = (z - theta.m) / sigma;
    return -0.5 * zz * zz - Math.log(sigma) - LOG_SQRT2PI;
  },
});

// --- CorrectedDist: F~ = H[Phi^-1(F(.))], exact composition ---

export class CorrectedDist {
  constructor(base, family, theta) {
    this.base = base;
    this.family = family;
    this.theta = theta;
    this._qgrid = null;
  }

  _z(y) {
    return phiInv(clamp01(this.base.cdf(y)));
  }

  cdf(y) {
    return this.family.cdf(this._z(y), this.theta);
  }

  logpdf(y) {
    const z = this._z(y);
    // chain rule: log f~(y) = log f(y) + log h(z) - log phi(z)
    return this.base.logpdf(y) + this.family.logpdf(z, this.theta) + 0.5 * z * z + LOG_SQRT2PI;
  }

  pdf(y) {
    const lp = this.logpdf(y);
    return lp > -700.0 ? Math.exp(lp) : 0.0;
  }

  quantile(p, tol = 1e-9, maxIter = 2100) {
    if (!(p > 0 && p < 1)) throw new Error("quantile p must be in (0, 1)");
    const hp = this.family.quantile(p, this.theta);
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
    return `CorrectedDist(theta=${JSON.stringify(this.theta)})`;
  }
}

// --- RTRL-lite online learners for m1 / m2 ---

const RMS_RHO = 0.01;
const RMS_EPS = 1e-6;

function initScaleLearner(learnB) {
  const state = { ell: 0.0, a: 0.5, c: 0.05, ea: 0.0, ec: 0.0, g2a: 0.0, g2c: 0.0 };
  if (learnB) {
    state.b = 0.0;
    state.eb = 0.0;
    state.g2b = 0.0;
  }
  return state;
}

function rmsStep(lr, grad, g2Prev) {
  const g2New = (1.0 - RMS_RHO) * g2Prev + RMS_RHO * grad * grad;
  return [lr * grad / Math.sqrt(g2New + RMS_EPS), g2New];
}

function updateScaleLearner(state, z, lr, learnB) {
  const ellPrev = state.ell;
  const a = state.a, c = state.c;
  const b = state.b === undefined ? 0.0 : state.b;

  const gradEll = clip(0.5 - 0.5 * z * z * Math.exp(-ellPrev), -GRAD_MAX, GRAD_MAX);

  const [stepA, g2aNew] = rmsStep(lr, gradEll * state.ea, state.g2a);
  const [stepC, g2cNew] = rmsStep(lr, gradEll * state.ec, state.g2c);
  const aNew = clip(a - stepA, A_MIN, A_MAX);
  const cNew = clip(c - stepC, -BC_MAX, BC_MAX);
  let bNew = 0.0, g2bNew = 0.0;
  if (learnB) {
    let stepB;
    [stepB, g2bNew] = rmsStep(lr, gradEll * state.eb, state.g2b);
    bNew = clip(b - stepB, -BC_MAX, BC_MAX);
  }

  const eaNew = clip(ellPrev + aNew * state.ea, -SENS_MAX, SENS_MAX);
  const ecNew = clip((z * z - 1.0) + aNew * state.ec, -SENS_MAX, SENS_MAX);
  const ellNew = clip(aNew * ellPrev + bNew * z + cNew * (z * z - 1.0), ELL_MIN, ELL_MAX);

  const out = { ell: ellNew, a: aNew, c: cNew, ea: eaNew, ec: ecNew, g2a: g2aNew, g2c: g2cNew };
  if (learnB) {
    out.b = bNew;
    out.eb = clip(z + aNew * state.eb, -SENS_MAX, SENS_MAX);
    out.g2b = g2bNew;
  }
  return out;
}

function thetaOf(model, learner) {
  if (model === "m0") return { m: 0.0, ell: 0.0 };
  const theta = { m: 0.0, ell: learner.ell, a: learner.a, c: learner.c };
  if (model === "m2") theta.b = learner.b;
  return theta;
}

const MODELS = ["m0", "m1", "m2"];

// Wrap a k = 1 skater with an online residual-transform correction. The
// state carries z (the resolved residual, null on the first tick), raw (the
// base skater's own forecast) and theta (the parameters of the returned
// CorrectedDist).
export function residualTransform(base, model = "m2", lr = 0.01, k = 1) {
  if (k !== 1) throw new Error("residual_transform currently supports k=1 only");
  if (!MODELS.includes(model)) throw new Error(`model must be one of m0, m1, m2, got ${model}`);
  const learnB = model === "m2";
  const family = model === "m0" ? IDENTITY_FAMILY : GAUSSIAN_SHIFT_SCALE_FAMILY;

  function _skater(y, state) {
    if (state === null || state === undefined) {
      const learner0 = model === "m0" ? null : initScaleLearner(learnB);
      state = { base: null, raw: null, z: null, learner: learner0, theta: thetaOf(model, learner0 || {}) };
    }
    let z = null;
    if (state.raw !== null) {
      z = phiInv(clamp01(state.raw.cdf(y)));
      if (model !== "m0") state.learner = updateScaleLearner(state.learner, z, lr, learnB);
    }
    state.z = z;

    const [dists, bs] = base(y, state.base);
    state.base = bs;
    const fT = dists[0];
    state.raw = fT;

    const theta = thetaOf(model, model !== "m0" ? state.learner : {});
    state.theta = theta;
    return [[new CorrectedDist(fT, family, theta)], state];
  }
  _skater.skaterName = `residual_transform(${base.skaterName || "?"}, model=${model})`;
  return _skater;
}

// --- diagnostics: online EWMA moments and the leverage statistic L_k ---

// A diagnostic only: feed it state.z from residualTransform (or parade).
export class ResidualDiagnostics {
  constructor(K = 5, halflife = 50.0) {
    this.K = K;
    this._alpha = 1.0 - 0.5 ** (1.0 / halflife);
    this.n = 0;
    this.m1 = 0.0; this.m2 = 0.0; this.m3 = 0.0; this.m4 = 0.0;
    this._buf = [];
    this._L = new Array(K).fill(0.0);
    this._crossSq = new Array(K).fill(0.0);
  }

  update(z) {
    this.n += 1;
    const a = this._alpha > 1.0 / this.n ? this._alpha : 1.0 / this.n;
    const z2 = z * z;
    this.m1 = (1 - a) * this.m1 + a * z;
    this.m2 = (1 - a) * this.m2 + a * z2;
    this.m3 = (1 - a) * this.m3 + a * z * z2;
    this.m4 = (1 - a) * this.m4 + a * z2 * z2;
    for (let lag = 1; lag <= this.K; lag++) {
      if (this._buf.length >= lag) {
        const zLag = this._buf[this._buf.length - lag];
        this._L[lag - 1] = (1 - a) * this._L[lag - 1] + a * zLag * (z2 - 1.0);
        this._crossSq[lag - 1] = (1 - a) * this._crossSq[lag - 1] + a * zLag * zLag * z2;
      }
    }
    this._buf.push(z);
    if (this._buf.length > this.K) this._buf.shift();
  }

  summary() {
    return {
      n: this.n,
      "E[z]": this.m1, "E[z2]": this.m2, "E[z3]": this.m3, "E[z4]": this.m4,
      L: this._L.slice(),
      cross_sq: this._crossSq.slice(),
    };
  }
}
