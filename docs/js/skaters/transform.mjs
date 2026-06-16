// Invertible online transforms — JS port of skaters/transform.py.
//
// A transform is { forward, inverseK }:
//   [yPrime, state] = forward(y, state)     // scalar in, scalar out
//   dists            = inverseK(dists, state) // map k Dists back
//
// forward runs on every observation; inverseK maps k Dist predictions in
// the transformed space back to the original space.

import { Dist } from "./dist.mjs";

// --- small helpers ---

function copysign(a, b) {
  const m = Math.abs(a);
  return b < 0 || Object.is(b, -0) ? -m : m;
}

function matVec(M, v, n) {
  const out = new Array(n).fill(0.0);
  for (let i = 0; i < n; i++) {
    let s = 0.0;
    for (let j = 0; j < n; j++) s += M[i * n + j] * v[j];
    out[i] = s;
  }
  return out;
}

function dot(a, b, n) {
  let s = 0.0;
  for (let i = 0; i < n; i++) s += a[i] * b[i];
  return s;
}

function eye(n, scale = 1.0) {
  const m = new Array(n * n).fill(0.0);
  for (let i = 0; i < n; i++) m[i * n + i] = scale;
  return m;
}

// ---------------------------------------------------------------------------
// Differencing:  y'_t = y_t - y_{t-1}
// ---------------------------------------------------------------------------

export function difference() {
  function forward(y, state) {
    if (state === null || state === undefined) return [0.0, { last: y }];
    return [y - state.last, { last: y }];
  }
  function inverseK(dists, state) {
    const anchor = state.last;
    const result = [];
    let cumsumMean = 0.0;
    let cumsumVar = 0.0;
    for (const d of dists) {
      cumsumMean += d.mean;
      cumsumVar += d.var;
      const std = cumsumVar > 0 ? Math.sqrt(cumsumVar) : Math.max(d.std, 1e-12);
      result.push(Dist.gaussian(anchor + cumsumMean, std));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Fractional differencing:  (1 - B)^d
// ---------------------------------------------------------------------------

function fracDiffWeights(d, window) {
  const w = [1.0];
  for (let i = 1; i < window; i++) w.push((-w[w.length - 1] * (d - i + 1)) / i);
  return w;
}

export function fractionalDifference(d = 0.4, window = 50) {
  const wFwd = fracDiffWeights(d, window);

  function forward(y, state) {
    if (state === null || state === undefined) state = { buffer: [] };
    const buf = state.buffer;
    buf.push(y);
    if (buf.length > window) buf.shift();
    const n = buf.length;
    let yPrime = 0.0;
    for (let j = 0; j < n; j++) yPrime += wFwd[j] * buf[n - 1 - j];
    return [yPrime, state];
  }

  function inverseK(dists, state) {
    const buf = state.buffer.slice();
    const result = [];
    for (const dIn of dists) {
      buf.push(0.0);
      const n = buf.length;
      let shift = 0.0;
      const upper = Math.min(n, window);
      for (let j = 1; j < upper; j++) shift -= wFwd[j] * buf[n - 1 - j];
      const recoveredMean = dIn.mean + shift;
      buf[buf.length - 1] = recoveredMean;
      result.push(Dist.gaussian(recoveredMean, dIn.std));
      if (buf.length > window) buf.shift();
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Running standardization
// ---------------------------------------------------------------------------

export function standardize(alpha = 0.05, eps = 1e-8) {
  function forward(y, state) {
    if (state === null || state === undefined) return [0.0, { mu: y, var: 0.0 }];
    let mu = state.mu;
    let varr = state.var;
    const diff = y - mu;
    mu = mu + alpha * diff;
    varr = (1 - alpha) * (varr + alpha * diff * diff);
    const sigma = varr > eps * eps ? Math.sqrt(varr) : eps;
    const yPrime = (y - mu) / sigma;
    return [yPrime, { mu, var: varr }];
  }
  function inverseK(dists, state) {
    const varr = state.var;
    const sigma = varr > 1e-16 ? Math.sqrt(varr) : 1e-8;
    return dists.map((d) => d.affine(sigma, state.mu));
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// EMA as a transform: subtract the running level
// ---------------------------------------------------------------------------

export function emaTransform(alpha = 0.05) {
  function forward(y, state) {
    if (state === null || state === undefined) return [0.0, { level: y }];
    const level = state.level + alpha * (y - state.level);
    return [y - level, { level }];
  }
  function inverseK(dists, state) {
    return dists.map((d) => d.shift(state.level));
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Theta method (Assimakopoulos & Nikolopoulos, 2000)
// ---------------------------------------------------------------------------

export function theta(alpha = 0.1) {
  function forward(y, state) {
    if (state === null || state === undefined) {
      return [0.0, { ses: y, t: 1, sum_t: 1.0, sum_t2: 1.0, sum_y: y, sum_ty: y }];
    }
    const s = state;
    s.t += 1;
    const t = s.t;
    s.ses = alpha * y + (1 - alpha) * s.ses;
    s.sum_t += t;
    s.sum_t2 += t * t;
    s.sum_y += y;
    s.sum_ty += t * y;
    const n = t;
    const denom = n * s.sum_t2 - s.sum_t * s.sum_t;
    const slope = Math.abs(denom) > 1e-12 ? (n * s.sum_ty - s.sum_t * s.sum_y) / denom : 0.0;
    s.slope = slope;
    const forecast = s.ses + slope / 2;
    return [y - forecast, s];
  }
  function inverseK(dists, state) {
    const ses = state.ses;
    const slope = state.slope === undefined ? 0.0 : state.slope;
    const result = [];
    let cumsumVar = 0.0;
    for (let h = 0; h < dists.length; h++) {
      const d = dists[h];
      cumsumVar += d.var;
      const forecast = ses + ((h + 1) * slope) / 2 + d.mean;
      const std = cumsumVar > 0 ? Math.sqrt(cumsumVar) : Math.max(d.std, 1e-12);
      result.push(Dist.gaussian(forecast, std));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Random walk with drift
// ---------------------------------------------------------------------------

export function drift(alpha = 0.002, shrinkage = 0.001) {
  const decay = 1 - alpha - shrinkage;
  function forward(y, state) {
    if (state === null || state === undefined) return [0.0, { last: y, mu: 0.0 }];
    const dy = y - state.last;
    const mu = decay * state.mu + alpha * dy;
    return [dy - mu, { last: y, mu }];
  }
  function inverseK(dists, state) {
    const anchor = state.last;
    const mu = state.mu;
    const result = [];
    let cumsumMean = 0.0;
    let cumsumVar = 0.0;
    for (let h = 0; h < dists.length; h++) {
      const d = dists[h];
      cumsumMean += d.mean;
      cumsumVar += d.var;
      const totalMean = anchor + (h + 1) * mu + cumsumMean;
      const totalStd = cumsumVar > 0 ? Math.sqrt(cumsumVar) : Math.max(d.std, 1e-12);
      result.push(Dist.gaussian(totalMean, totalStd));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Holt linear (level + trend)
// ---------------------------------------------------------------------------

export function holtLinear(alpha = 0.1, beta = 0.05) {
  function forward(y, state) {
    if (state === null || state === undefined) return [0.0, { level: y, trend: 0.0 }];
    const lPrev = state.level;
    const bPrev = state.trend;
    const lNew = alpha * y + (1 - alpha) * (lPrev + bPrev);
    const bNew = beta * (lNew - lPrev) + (1 - beta) * bPrev;
    return [y - (lPrev + bPrev), { level: lNew, trend: bNew }];
  }
  function inverseK(dists, state) {
    const level = state.level;
    const trend = state.trend;
    const result = [];
    let cumsumVar = 0.0;
    for (let h = 0; h < dists.length; h++) {
      const d = dists[h];
      cumsumVar += d.var;
      const forecast = level + (h + 1) * trend + d.mean;
      const std = cumsumVar > 0 ? Math.sqrt(cumsumVar) : Math.max(d.std, 1e-12);
      result.push(Dist.gaussian(forecast, std));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// GARCH(1,1) volatility scaling
// ---------------------------------------------------------------------------

export function garch(omega = 0.01, alpha = 0.1, beta = 0.85, eps = 1e-8) {
  function forward(y, state) {
    if (state === null || state === undefined) {
      const persist = alpha + beta;
      const var0 = persist < 1 ? omega / (1 - persist) : omega / eps;
      return [y / Math.max(Math.sqrt(var0), eps), { var: var0, last_y: y }];
    }
    const varr = omega + alpha * state.last_y * state.last_y + beta * state.var;
    const sigma = varr > eps * eps ? Math.sqrt(varr) : eps;
    return [y / sigma, { var: varr, last_y: y }];
  }
  function inverseK(dists, state) {
    const sigma = state.var > 1e-16 ? Math.sqrt(state.var) : 1e-8;
    return dists.map((d) => d.scale(sigma));
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Seasonal differencing:  y'_t = y_t - y_{t-s}
// ---------------------------------------------------------------------------

export function seasonalDifference(period = 12) {
  function forward(y, state) {
    if (state === null || state === undefined) return [0.0, { buffer: [y] }];
    const buf = state.buffer;
    let yPrime;
    if (buf.length >= period) yPrime = y - buf[buf.length - period];
    else yPrime = 0.0;
    buf.push(y);
    if (buf.length > 2 * period) buf.shift();
    return [yPrime, state];
  }
  function inverseK(dists, state) {
    const buf = state.buffer.slice();
    const recoveredMeans = [];
    const result = [];
    for (let h = 0; h < dists.length; h++) {
      const lagIdx = h - period;
      let anchor;
      if (lagIdx < 0) {
        const bufIdx = buf.length - period + h;
        anchor = bufIdx >= 0 && bufIdx < buf.length ? buf[bufIdx] : 0.0;
      } else {
        anchor = recoveredMeans[lagIdx];
      }
      recoveredMeans.push(dists[h].mean + anchor);
      result.push(dists[h].shift(anchor));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Signed power transform
// ---------------------------------------------------------------------------

export function powerTransform(p = 0.5) {
  const invP = 1.0 / p;
  const fwd = (y) => copysign(Math.pow(Math.abs(y), p), y);
  const inv = (yp) => copysign(Math.pow(Math.abs(yp), invP), yp);

  function forward(y, state) {
    return [fwd(y), state || {}];
  }
  function inverseK(dists, state) {
    const result = [];
    for (const d of dists) {
      const components = [];
      for (const [w, mu, sigma] of d.components) {
        const origMean = inv(mu);
        const absMu = Math.abs(mu);
        const deriv = absMu > 1e-12 ? invP * Math.pow(absMu, invP - 1) : invP;
        const origStd = Math.max(sigma * deriv, 1e-12);
        components.push([w, origMean, origStd]);
      }
      result.push(new Dist(components));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// AR(p) with online recursive least squares
// ---------------------------------------------------------------------------

export function ar(order = 2, lam = 0.99, ridge = 1.0, decay = 0.0) {
  const p = order;

  function initP() {
    const P = new Array(p * p).fill(0.0);
    for (let j = 0; j < p; j++) {
      P[j * p + j] = decay > 0 ? ridge / Math.pow(j + 1, decay) : ridge;
    }
    return P;
  }

  function forward(y, state) {
    if (state === null || state === undefined) {
      state = { buffer: [], phi: new Array(p).fill(0.0), P: initP(), n: 0 };
    }
    const buf = state.buffer;
    const phi = state.phi;
    state.n += 1;
    let residual;
    if (buf.length >= p) {
      const x = new Array(p);
      for (let i = 0; i < p; i++) x[i] = buf[buf.length - 1 - i];
      let prediction = 0.0;
      for (let i = 0; i < p; i++) prediction += phi[i] * x[i];
      residual = y - prediction;
      const P = state.P;
      const Px = matVec(P, x, p);
      const denom = lam + dot(x, Px, p);
      if (Math.abs(denom) > 1e-15) {
        const K = Px.map((px) => px / denom);
        for (let i = 0; i < p; i++) phi[i] += K[i] * residual;
        for (let i = 0; i < p; i++) {
          for (let j = 0; j < p; j++) {
            P[i * p + j] = (P[i * p + j] - K[i] * Px[j]) / lam;
          }
        }
      }
    } else {
      residual = y;
    }
    buf.push(y);
    if (buf.length > 2 * p + 10) buf.shift();
    return [residual, state];
  }

  function inverseK(dists, state) {
    const buf = state.buffer.slice();
    const phi = state.phi;
    const recoveredMeans = [];
    const recoveredVars = [];
    const result = [];
    for (let h = 0; h < dists.length; h++) {
      let arMean = 0.0;
      let arVar = 0.0;
      for (let j = 0; j < p; j++) {
        const lagH = h - j - 1;
        if (lagH < 0) {
          const bufIdx = buf.length + lagH;
          if (bufIdx >= 0 && bufIdx < buf.length) arMean += phi[j] * buf[bufIdx];
        } else if (lagH < recoveredMeans.length) {
          arMean += phi[j] * recoveredMeans[lagH];
          arVar += phi[j] * phi[j] * recoveredVars[lagH];
        }
      }
      const totalMean = dists[h].mean + arMean;
      const totalVar = dists[h].var + arVar;
      const totalStd = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(dists[h].std, 1e-12);
      recoveredMeans.push(totalMean);
      recoveredVars.push(totalVar);
      result.push(Dist.gaussian(totalMean, totalStd));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Grouped AR with geometrically grouped coefficients
// ---------------------------------------------------------------------------

function buildGroups(maxLag) {
  const groups = [];
  let g = 0;
  let size = 1;
  let assigned = 0;
  while (assigned < maxLag) {
    for (let i = 0; i < size; i++) {
      if (assigned >= maxLag) break;
      groups.push(g);
      assigned += 1;
    }
    g += 1;
    size *= 2;
  }
  return groups;
}

function groupRegressor(buf, groups, nGroups, maxLag) {
  const x = new Array(nGroups).fill(0.0);
  for (let j = 0; j < maxLag; j++) x[groups[j]] += buf[buf.length - 1 - j];
  return x;
}

export function groupedAr(maxLag = 16, lam = 0.99, ridge = 1.0) {
  const groups = buildGroups(maxLag);
  const nGroups = Math.max(...groups) + 1;

  function forward(y, state) {
    if (state === null || state === undefined) {
      state = { buffer: [], theta: new Array(nGroups).fill(0.0), P: eye(nGroups, ridge), n: 0 };
    }
    const buf = state.buffer;
    const th = state.theta;
    state.n += 1;
    let residual;
    if (buf.length >= maxLag) {
      const x = groupRegressor(buf, groups, nGroups, maxLag);
      let prediction = 0.0;
      for (let g = 0; g < nGroups; g++) prediction += th[g] * x[g];
      residual = y - prediction;
      const P = state.P;
      const Px = matVec(P, x, nGroups);
      const denom = lam + dot(x, Px, nGroups);
      if (Math.abs(denom) > 1e-15) {
        const K = Px.map((px) => px / denom);
        for (let g = 0; g < nGroups; g++) th[g] += K[g] * residual;
        for (let i = 0; i < nGroups; i++) {
          for (let j = 0; j < nGroups; j++) {
            P[i * nGroups + j] = (P[i * nGroups + j] - K[i] * Px[j]) / lam;
          }
        }
      }
    } else {
      residual = y;
    }
    buf.push(y);
    if (buf.length > maxLag + 10) buf.shift();
    return [residual, state];
  }

  function inverseK(dists, state) {
    const buf = state.buffer.slice();
    const th = state.theta;
    const phi = [];
    for (let j = 0; j < maxLag; j++) phi.push(th[groups[j]]);
    const recoveredMeans = [];
    const recoveredVars = [];
    const result = [];
    for (let h = 0; h < dists.length; h++) {
      let arMean = 0.0;
      let arVar = 0.0;
      for (let j = 0; j < maxLag; j++) {
        const lagH = h - j - 1;
        if (lagH < 0) {
          const bufIdx = buf.length + lagH;
          if (bufIdx >= 0 && bufIdx < buf.length) arMean += phi[j] * buf[bufIdx];
        } else if (lagH < recoveredMeans.length) {
          arMean += phi[j] * recoveredMeans[lagH];
          arVar += phi[j] * phi[j] * recoveredVars[lagH];
        }
      }
      const totalMean = dists[h].mean + arMean;
      const totalVar = dists[h].var + arVar;
      const totalStd = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(dists[h].std, 1e-12);
      recoveredMeans.push(totalMean);
      recoveredVars.push(totalVar);
      result.push(Dist.gaussian(totalMean, totalStd));
    }
    return result;
  }
  return { forward, inverseK };
}
