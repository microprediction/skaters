// Invertible online transforms — JS port of skaters/transform.py.
//
// A transform is { forward, inverseK }:
//   [yPrime, state] = forward(y, state)     // scalar in, scalar out
//   dists            = inverseK(dists, state) // map k Dists back
//
// forward runs on every observation; inverseK maps k Dist predictions in
// the transformed space back to the original space.

import { fsum, Dist, erf } from "./dist.mjs";
import { SplicedDist } from "./tails.mjs";
import { PushforwardDist, tableFromMap, bisectRight } from "./pushforward.mjs";

// --- small helpers ---

// Shift by delta and add independent Gaussian variance add. Exact for a
// Gaussian mixture (each component widens). A tail-spliced predictive has no
// components to widen, so its body widens and the GPD splice, which lives in
// the body's PIT space, follows it.
function widen(d, delta, add) {
  if (d instanceof SplicedDist) return d._withBody(widen(d.body, delta, add), false);
  return new Dist(d.components.map(([w, m, s]) => [w, m + delta, Math.sqrt(s * s + add)]));
}

function hasComponents(d) {
  return !(d instanceof PushforwardDist) && d.components !== undefined && d.components !== null;
}

// The exact pushforward of d through the monotone map invFn. The table window
// adapts to each predictive: [m - 10s, m + 10s] over the mixture, or, with no
// mixture to read (laplace's tail-spliced SplicedDist), the extreme quantiles
// padded by their own span on each side.
function pushforward(d, invFn) {
  let lo, hi;
  if (hasComponents(d)) {
    lo = Infinity; hi = -Infinity;
    for (const [, m, s] of d.components) {
      lo = Math.min(lo, m - 10.0 * s);
      hi = Math.max(hi, m + 10.0 * s);
    }
  } else {
    const qLo = d.quantile(1e-6), qHi = d.quantile(1.0 - 1e-6);
    lo = 2.0 * qLo - qHi; hi = 2.0 * qHi - qLo;
  }
  const [ys, zs] = tableFromMap(invFn, lo, hi);
  return new PushforwardDist(d, ys, zs, { invFn });
}

// An inverseK that emits the exact pushforward.
function exactInverseK(invFn) {
  return (dists, state) => dists.map((d) => pushforward(d, invFn));
}

// Wichura AS241, as CPython's statistics.NormalDist().inv_cdf.
export function normalInvCdf(p) {
  if (!(p > 0.0 && p < 1.0)) throw new Error("p must be in the range 0.0 < p < 1.0");
  const q = p - 0.5;
  let num, den, r;
  if (Math.abs(q) <= 0.425) {
    r = 0.180625 - q * q;
    num = (((((((2.5090809287301226727e+3 * r +
                 3.3430575583588128105e+4) * r +
                 6.7265770927008700853e+4) * r +
                 4.5921953931549871457e+4) * r +
                 1.3731693765509461125e+4) * r +
                 1.9715909503065514427e+3) * r +
                 1.3314166789178437745e+2) * r +
                 3.3871328727963666080e+0) * q;
    den = (((((((5.2264952788528545610e+3 * r +
                 2.8729085735721942674e+4) * r +
                 3.9307895800092710610e+4) * r +
                 2.1213794301586595867e+4) * r +
                 5.3941960214247511077e+3) * r +
                 6.8718700749205790830e+2) * r +
                 4.2313330701600911252e+1) * r +
                 1.0);
    return 0.0 + num / den;
  }
  r = q <= 0.0 ? p : 1.0 - p;
  r = Math.sqrt(-Math.log(r));
  if (r <= 5.0) {
    r = r - 1.6;
    num = (((((((7.74545014278341407640e-4 * r +
                 2.27238449892691845833e-2) * r +
                 2.41780725177450611770e-1) * r +
                 1.27045825245236838258e+0) * r +
                 3.64784832476320460504e+0) * r +
                 5.76949722146069140550e+0) * r +
                 4.63033784615654529590e+0) * r +
                 1.42343711074968357734e+0);
    den = (((((((1.05075007164441684324e-9 * r +
                 5.47593808499534494600e-4) * r +
                 1.51986665636164571966e-2) * r +
                 1.48103976427480074590e-1) * r +
                 6.89767334985100004550e-1) * r +
                 1.67638483018380384940e+0) * r +
                 2.05319162663775882187e+0) * r +
                 1.0);
  } else {
    r = r - 5.0;
    num = (((((((2.01033439929228813265e-7 * r +
                 2.71155556874348757815e-5) * r +
                 1.24266094738807843860e-3) * r +
                 2.65321895265761230930e-2) * r +
                 2.96560571828504891230e-1) * r +
                 1.78482653991729133580e+0) * r +
                 5.46378491116411436990e+0) * r +
                 6.65790464350110377720e+0);
    den = (((((((2.04426310338993978564e-15 * r +
                 1.42151175831644588870e-7) * r +
                 1.84631831751005468180e-5) * r +
                 7.86869131145613259100e-4) * r +
                 1.48753612908506148525e-2) * r +
                 1.36929880922735805310e-1) * r +
                 5.99832206555887937690e-1) * r +
                 1.0);
  }
  let x = num / den;
  if (q < 0.0) x = -x;
  return 0.0 + x;
}

// Math.nextafter for doubles (Python's math.nextafter).
function nextafter(x, toward) {
  if (Number.isNaN(x) || Number.isNaN(toward)) return NaN;
  if (x === toward) return toward;
  if (x === 0) return toward > 0 ? Number.MIN_VALUE : -Number.MIN_VALUE;
  const buf = new DataView(new ArrayBuffer(8));
  buf.setFloat64(0, x);
  let bits = buf.getBigUint64(0);
  bits += ((toward > x) === (x > 0)) ? 1n : -1n;
  buf.setBigUint64(0, bits);
  return buf.getFloat64(0);
}

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
  const terms = new Array(n);
  for (let i = 0; i < n; i++) terms[i] = a[i] * b[i];
  return fsum(terms);
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
    const yPrime = fsum(Array.from({ length: n }, (_, j) => wFwd[j] * buf[n - 1 - j]));
    return [yPrime, state];
  }

  function inverseK(dists, state) {
    // Recovered horizons feed back through the same weights, so each carries a row
    // of responses to the future innovations and Var = sum_i c_i^2 var_i (issue #255).
    const H = dists.length;
    const buf = state.buffer.slice();
    const cbuf = buf.map(() => null);
    const result = [];
    for (let h = 0; h < H; h++) {
      const dIn = dists[h];
      buf.push(0.0);
      cbuf.push(null);
      const n = buf.length;
      let shift = 0.0;
      const coef = new Array(H).fill(0.0);
      coef[h] = 1.0;
      const upper = Math.min(n, window);
      for (let j = 1; j < upper; j++) {
        shift -= wFwd[j] * buf[n - 1 - j];
        const cj = cbuf[n - 1 - j];
        if (cj !== null) for (let i = 0; i < h; i++) coef[i] -= wFwd[j] * cj[i];
      }
      const recoveredMean = dIn.mean + shift;
      buf[n - 1] = recoveredMean;
      cbuf[n - 1] = coef;
      let totalVar = 0.0;
      for (let i = 0; i <= h; i++) totalVar += coef[i] * coef[i] * dists[i].var;
      const std = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(dIn.std, 1e-12);
      result.push(Dist.gaussian(recoveredMean, std));
      if (buf.length > window) { buf.shift(); cbuf.shift(); }
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
    const mu = state.mu;
    const varr = state.var;
    const diff = y - mu;
    // Emit against the PRIOR state, so the forward map is the affine change
    // of coordinates z = (y - mu) / sigma that the inverse applies. Scaling
    // by the post-update std makes the emission self-normalized (bounded by
    // 1/sqrt(alpha)) and the affine inverse is then not its inverse.
    // Cold start: before the variance is informative, scale by the first
    // nonzero residual, so the first informative emission is +-1.
    let sigma;
    if (varr > eps * eps) {
      sigma = Math.sqrt(varr);
    } else {
      sigma = Math.abs(diff) > eps ? Math.abs(diff) : eps;
    }
    const yPrime = diff / sigma;
    const muNew = mu + alpha * diff;
    const varNew = (1 - alpha) * varr + alpha * diff * diff;
    return [yPrime, { mu: muNew, var: varNew }];
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
    // Residual is the one-step forecast error (against the PRIOR level); using the
    // post-update level would shrink it by (1-alpha) -> overconfident intervals.
    const residual = y - state.level;
    const level = state.level + alpha * residual;
    return [residual, { level }];
  }
  function inverseK(dists, state) {
    const level = state.level;
    const out = [];
    let add = 0.0; // alpha^2 * sum_{i<h} var_i: the level's accumulated response (ETS(A,N,N), issue #254)
    for (const d of dists) {
      if (add > 0.0) out.push(widen(d, level, add));
      else out.push(d.shift(level));
      add += alpha * alpha * d.var;
    }
    return out;
  }
  return { forward, inverseK };
}

// Ornstein-Uhlenbeck mean-reversion (JS port of transform.ou_transform).
// Reverts toward a running mean at speed kappa; phi = 1 - kappa. Multi-step
// inverse uses the exact OU moments (phi^h mean decay, saturating variance).
export function ouTransform(kappa = 0.1, alpha = 0.02) {
  const phi = 1.0 - kappa;
  function forward(y, state) {
    if (state === null || state === undefined || !Number.isFinite(y)) {
      const y0 = Number.isFinite(y) ? y : 0.0;
      return [0.0, { m: y0, fc: y0, y: y0 }];
    }
    let resid = y - state.fc;
    if (!Number.isFinite(resid)) resid = 0.0;
    const m = state.m + alpha * (y - state.m);
    const fc = m + phi * (y - m);
    return [resid, { m, fc, y }];
  }
  function inverseK(dists, state) {
    const m = state.m;
    const ylast = state.y;
    return dists.map((d, i) => {
      const h = i + 1;
      const center = m + Math.pow(phi, h) * (ylast - m);
      // Var = sum_{k<=i} phi^{2(i-k)} var_k, as a scale on this horizon's Dist (issue #256);
      // equals the old sqrt(sum_j phi^2j) for equal variances.
      const vh = d.var;
      let g;
      if (vh > 0.0) {
        let tot = 0.0;
        for (let k = 0; k <= i; k++) tot += Math.pow(phi, 2 * (i - k)) * dists[k].var;
        g = Math.sqrt(tot / vh);
      } else {
        g = phi < 1.0 - 1e-9
          ? Math.sqrt((1.0 - Math.pow(phi, 2 * h)) / (1.0 - phi * phi))
          : Math.sqrt(h);
      }
      return d.scale(g).shift(center);
    });
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
    // Forecast from the PRIOR state, then update (forecasting after folding y into
    // ses/slope would leak y into its own residual -> overconfident interval).
    const forecast = s.ses + (s.slope === undefined ? 0.0 : s.slope) / 2;
    const residual = y - forecast;
    s.ses = alpha * y + (1 - alpha) * s.ses;
    s.sum_t += t;
    s.sum_t2 += t * t;
    s.sum_y += y;
    s.sum_ty += t * y;
    const n = t;
    const denom = n * s.sum_t2 - s.sum_t * s.sum_t;
    const slope = Math.abs(denom) > 1e-12 ? (n * s.sum_ty - s.sum_t * s.sum_y) / denom : 0.0;
    s.slope = slope;
    return [residual, s];
  }
  function inverseK(dists, state) {
    const ses = state.ses;
    const slope = state.slope === undefined ? 0.0 : state.slope;
    const result = [];
    for (let h = 0; h < dists.length; h++) {
      const d = dists[h];
      const forecast = ses + ((h + 1) * slope) / 2 + d.mean;
      // SES: c_0 = 1, c_j = alpha; Var = sum_j c_j^2 var_{h-j} (issue #253).
      let totalVar = 0.0;
      for (let j = 0; j <= h; j++) {
        const c = j === 0 ? 1.0 : alpha;
        totalVar += c * c * dists[h - j].var;
      }
      const std = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(d.std, 1e-12);
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
    // Increment minus the PRIOR drift (one-step forecast error); the post-update
    // drift would leak dy into its own residual -> overconfident interval.
    const residual = dy - state.mu;
    const mu = decay * state.mu + alpha * dy;
    return [residual, { last: y, mu }];
  }
  function inverseK(dists, state) {
    const anchor = state.last;
    const mu = state.mu;
    const rho = decay + alpha; // 1 - shrinkage: persistence of the drift estimate
    const result = [];
    let cumsumMean = 0.0;
    for (let h = 0; h < dists.length; h++) {
      const d = dists[h];
      cumsumMean += d.mean;
      const totalMean = anchor + (h + 1) * mu + cumsumMean;
      // c = 1 + alpha * sum_{m<h-i} rho^m: direct plus through the drift estimate (issue #257).
      let totalVar = 0.0;
      for (let i = 0; i <= h; i++) {
        let acc = 0.0, f = 1.0;
        for (let m = 0; m < h - i; m++) { acc += f; f *= rho; }
        const c = 1.0 + alpha * acc;
        totalVar += c * c * dists[i].var;
      }
      const totalStd = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(d.std, 1e-12);
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
    for (let h = 0; h < dists.length; h++) {
      const d = dists[h];
      const forecast = level + (h + 1) * trend + d.mean;
      // ETS(A,A,N): c_0 = 1, c_j = alpha + alpha*beta*j; Var = sum_j c_j^2 var_{h-j} (issue #242).
      let totalVar = 0.0;
      for (let j = 0; j <= h; j++) {
        const c = j === 0 ? 1.0 : alpha + alpha * beta * j;
        totalVar += c * c * dists[h - j].var;
      }
      const std = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(d.std, 1e-12);
      result.push(Dist.gaussian(forecast, std));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// GARCH(1,1) volatility scaling
// ---------------------------------------------------------------------------

export function garch(omega = 0.01, alpha = 0.1, beta = 0.85, meanAlpha = 0.05, eps = 1e-8) {
  function forward(y, state) {
    if (state === null || state === undefined) {
      const persist = alpha + beta;
      const var0 = persist < 1 ? omega / (1 - persist) : omega / eps;
      return [0.0, { var: var0, last_dev: 0.0, mu: y }];
    }
    // GARCH conditional variance of the DEVIATION from a running mean, not of
    // the raw value: alpha*y^2 treats y as a mean-zero return, so on a level
    // series the "volatility" is of order |y| and the inverse re-inflates it
    // (unstable). Tracking a mean makes garch shift-invariant; on mean-zero
    // returns mu stays ~0 and this reduces to the original y/sigma.
    const mu = state.mu;
    const dev = y - mu;
    const varr = omega + alpha * state.last_dev * state.last_dev + beta * state.var;
    const sigma = varr > eps * eps ? Math.sqrt(varr) : eps;
    return [dev / sigma, { var: varr, last_dev: dev, mu: mu + meanAlpha * dev }];
  }
  function inverseK(dists, state) {
    const sigma = state.var > 1e-16 ? Math.sqrt(state.var) : 1e-8;
    return dists.map((d) => d.affine(sigma, state.mu));
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
    const recoveredVars = [];
    const result = [];
    for (let h = 0; h < dists.length; h++) {
      const lagIdx = h - period;
      let anchorMean, anchorVar;
      if (lagIdx < 0) {
        // Observed buffer value: deterministic, only shifts the location.
        const bufIdx = buf.length - period + h;
        anchorMean = bufIdx >= 0 && bufIdx < buf.length ? buf[bufIdx] : 0.0;
        anchorVar = 0.0;
      } else {
        // Value recovered earlier in this call: it carries its own variance,
        // which must be added along the seasonal integration chain (mirrors the
        // difference / grouped_ar inverses). Dropping it understates uncertainty
        // at every horizon h >= period.
        anchorMean = recoveredMeans[lagIdx];
        anchorVar = recoveredVars[lagIdx];
      }
      recoveredMeans.push(dists[h].mean + anchorMean);
      recoveredVars.push(dists[h].var + anchorVar);
      if (anchorVar > 0.0) {
        // Convolve with N(0, anchorVar): shift means, inflate stds.
        result.push(widen(dists[h], anchorMean, anchorVar));
      } else {
        result.push(dists[h].shift(anchorMean));
      }
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Seasonal anchor: hedged seasonal location (phase-EMA blended with naive)
// ---------------------------------------------------------------------------

export function seasonalAnchor(period, alpha = 0.2, weight = 0.5) {
  const anchorOf = (ema, snaive) =>
    ema !== null ? weight * ema + (1.0 - weight) * snaive : snaive;

  function forward(y, state) {
    if (state === null || state === undefined) {
      return [0.0, { ema: new Array(period).fill(null), buffer: [y], n: 1 }];
    }
    const buf = state.buffer;
    const p = state.n % period;
    const snaive = buf.length >= period ? buf[buf.length - period] : buf[buf.length - 1];
    const yPrime = y - anchorOf(state.ema[p], snaive);
    const e = state.ema[p];
    state.ema[p] = e === null ? y : e + alpha * (y - e);
    buf.push(y);
    if (buf.length > 2 * period) buf.shift();
    state.n += 1;
    return [yPrime, state];
  }

  function inverseK(dists, state) {
    const buf = state.buffer;
    const H = dists.length;
    const recoveredMeans = [];
    // Innovation-response rows of recovered values and of each phase's EMA: the
    // forward updates the EMA from recovered values too, so an anchor at h >= period
    // responds to the value one period back through (1 - weight) and weight*alpha (issue #258).
    const recResp = [];
    const emaResp = [];
    for (let q = 0; q < period; q++) emaResp.push(new Array(H).fill(0.0));
    const result = [];
    for (let h = 0; h < H; h++) {
      const p = (state.n + h) % period;
      const lagIdx = h - period;
      let snaive, snResp;
      if (lagIdx < 0) {
        const bufIdx = buf.length - period + h;
        snaive = bufIdx >= 0 && bufIdx < buf.length ? buf[bufIdx] : buf[buf.length - 1];
        snResp = null;
      } else {
        snaive = recoveredMeans[lagIdx];
        snResp = recResp[lagIdx];
      }
      const e = state.ema[p];
      const aMean = anchorOf(e, snaive);
      const aResp = new Array(H).fill(0.0);
      for (let i = 0; i < h; i++) {
        const sn = snResp !== null ? snResp[i] : 0.0;
        aResp[i] = (e !== null && e !== undefined) ? weight * emaResp[p][i] + (1.0 - weight) * sn : sn;
      }
      let aVar = 0.0;
      for (let i = 0; i < h; i++) aVar += aResp[i] * aResp[i] * dists[i].var;
      const r = aResp.slice();
      r[h] = 1.0;
      recoveredMeans.push(dists[h].mean + aMean);
      recResp.push(r);
      if (e === null || e === undefined) emaResp[p] = r.slice();
      else emaResp[p] = emaResp[p].map((v, i) => (1.0 - alpha) * v + alpha * r[i]);
      if (aVar > 0.0) {
        result.push(widen(dists[h], aMean, aVar));
      } else {
        result.push(dists[h].shift(aMean));
      }
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Seasonal scale: phase-indexed running standardization
// ---------------------------------------------------------------------------

// JS port of transform.seasonal_scale. Each phase keeps its own EWMA mean and
// variance, shrunk in log space toward the global EWMA variance by visit
// count, w = visits / (visits + 3). center=false divides by the phase sigma
// without subtracting the phase mean.
export function seasonalScale(period, alpha = 0.05, center = false, eps = 1e-8) {
  if (!(period >= 1)) throw new Error("seasonalScale needs period >= 1");
  if (!(alpha > 0 && alpha < 1)) throw new Error("seasonalScale needs 0 < alpha < 1");
  const aG = alpha / period;
  const K0 = 3.0;

  // Bias-corrected global variance (the slow EWMA starts from zero).
  function vg(state) {
    const updates = state.n - 1;
    if (updates <= 0) return 0.0;
    return state.var_g / (1.0 - Math.pow(1.0 - aG, updates));
  }

  function phaseStats(state, p) {
    const w = state.vis[p] / (state.vis[p] + K0);
    const vp = Math.max(state.var[p], eps * eps);
    const vgl = Math.max(vg(state), eps * eps);
    const varEff = Math.exp(w * Math.log(vp) + (1.0 - w) * Math.log(vgl));
    const muEff = center ? w * state.mu[p] + (1.0 - w) * state.mu_g : 0.0;
    return [muEff, Math.sqrt(varEff)];
  }

  function forward(y, state) {
    if (state === null || state === undefined) {
      return [0.0, { mu_g: y, var_g: 0.0, mu: new Array(period).fill(0.0),
                     var: new Array(period).fill(0.0), vis: new Array(period).fill(0), n: 1 }];
    }
    const p = state.n % period;
    // Center against the PRIOR mean, scale by the UPDATED variance.
    const [muEff] = phaseStats(state, p);
    const dg = y - state.mu_g;
    state.mu_g += aG * dg;
    state.var_g = (1 - aG) * state.var_g + aG * dg * dg;
    if (state.vis[p] === 0) {           // first visit seeds from global stats
      state.mu[p] = y;
      state.var[p] = vg(state);
    } else {
      const dp = y - state.mu[p];
      state.mu[p] += alpha * dp;
      state.var[p] = (1 - alpha) * state.var[p] + alpha * dp * dp;
    }
    state.vis[p] += 1;
    state.n += 1;
    const [, sigma] = phaseStats(state, p);
    return [(y - muEff) / sigma, state];
  }

  function inverseK(dists, state) {
    const out = [];
    for (let h = 0; h < dists.length; h++) {
      const [muEff, sigma] = phaseStats(state, (state.n + h) % period);
      out.push(dists[h].affine(sigma, muEff));
    }
    return out;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Signed power transform
// ---------------------------------------------------------------------------

export function powerTransform(p = 0.5, exact = false) {
  const invP = 1.0 / p;
  const fwd = (y) => copysign(Math.pow(Math.abs(y), p), y);
  const inv = (yp) => copysign(Math.pow(Math.abs(yp), invP), yp);

  function forward(y, state) {
    return [fwd(y), state || {}];
  }
  function inverseK(dists, state) {
    const result = [];
    for (const d of dists) {
      if (d.components === undefined || d.components === null) {   // tail-spliced: exact pushforward
        result.push(pushforward(d, inv));
        continue;
      }
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
  return { forward, inverseK: exact ? exactInverseK(inv) : inverseK };
}

// Yeo-Johnson coordinate transform — signed Box-Cox family. JS port of
// skaters/transform.py:yeo_johnson. Learns the coordinate the series is simple
// in (lambda=0 -> log1p / non-negative, 1 -> identity, 0.5 -> compression).
export function yeoJohnson(lmbda = 0.0, exact = false) {
  const L = lmbda;
  const fwd = (y) => {
    if (y >= 0.0) return L === 0.0 ? Math.log1p(y) : (Math.pow(y + 1.0, L) - 1.0) / L;
    if (L === 2.0) return -Math.log1p(-y);
    return -((Math.pow(-y + 1.0, 2.0 - L) - 1.0) / (2.0 - L));
  };
  // clamp exp args so squaring the result in var() stays finite (exp(350)~1e152).
  const inv = (yp) => {
    if (yp >= 0.0) {
      if (L === 0.0) return Math.expm1(Math.min(yp, 350.0));
      return Math.pow(Math.max(L * yp + 1.0, 1e-12), 1.0 / L) - 1.0;
    }
    if (L === 2.0) return 1.0 - Math.exp(Math.min(-yp, 350.0));
    return 1.0 - Math.pow(Math.max(-(2.0 - L) * yp + 1.0, 1e-12), 1.0 / (2.0 - L));
  };
  const dinv = (yp) => {
    if (yp >= 0.0) {
      if (L === 0.0) return Math.exp(Math.min(yp, 350.0));
      return Math.pow(Math.max(L * yp + 1.0, 1e-12), 1.0 / L - 1.0);
    }
    if (L === 2.0) return Math.exp(Math.min(-yp, 350.0));
    return Math.pow(Math.max(-(2.0 - L) * yp + 1.0, 1e-12), 1.0 / (2.0 - L) - 1.0);
  };

  function forward(y, state) {
    return [fwd(y), state || {}];
  }
  function inverseK(dists, state) {
    const result = [];
    for (const d of dists) {
      if (d.components === undefined || d.components === null) {   // tail-spliced: exact pushforward
        result.push(pushforward(d, inv));
        continue;
      }
      const components = [];
      for (const [w, mu, sigma] of d.components) {
        components.push([w, inv(mu), Math.max(sigma * dinv(mu), 1e-12)]);
      }
      result.push(new Dist(components));
    }
    return result;
  }
  return { forward, inverseK: exact ? exactInverseK(inv) : inverseK };
}

// ---------------------------------------------------------------------------
// Log coordinate with a one-sided bound (JS port of transform.log_transform)
// ---------------------------------------------------------------------------

// y' = log(y - lower) (the default, lower = 0) or y' = -log(upper - y). The
// inverse is the exact pushforward through the inverse map. Give one bound.
// A finite observation on or past the bound throws; missing observations pass
// through for the inner skater. Experimental, alongside flesaker.
export function logTransform(lower = null, upper = null) {
  if (lower !== null && lower !== undefined && upper !== null && upper !== undefined) {
    throw new Error("log_transform takes one bound: lower or upper");
  }
  const hasUpper = upper !== null && upper !== undefined;
  const b = Number(hasUpper ? upper : (lower === null || lower === undefined ? 0.0 : lower));
  if (!Number.isFinite(b)) throw new Error("log_transform needs a finite bound");
  const direction = hasUpper ? -1.0 : 1.0;
  const boundLabel = hasUpper ? "upper" : "lower";
  const LOG_TWO = Math.log(2.0);

  const fwdQuery = (y) => {
    const gap = direction * (y - b);
    if (gap <= 0.0) return -direction * Infinity;
    if (gap === Infinity) {
      // A gap between finite floats can overflow even when its log fits.
      const halfGap = direction * (0.5 * y - 0.5 * b);
      return direction * (Math.log(halfGap) + LOG_TWO);
    }
    return direction * Math.log(gap);
  };
  const inverseAtScale = (z, weight) => {
    const bound = weight * b;
    const logGap = direction * z + Math.log(weight);
    const gap = Math.exp(logGap);
    if (gap === Infinity) {
      // The shift by the bound can bring an overflowing gap into range.
      return 2.0 * (0.5 * bound + direction * Math.exp(logGap - LOG_TWO));
    }
    return bound + direction * gap;
  };
  const inv = (z) => {
    const y = inverseAtScale(z, 1.0);
    return y === b ? nextafter(b, direction * Infinity) : y;
  };
  const logJacobian = (z) => -direction * z;
  const moments = (m, s) => {
    const variance = s * s;
    const logMeanGap = direction * m + 0.5 * variance;
    const mean = inverseAtScale(direction * logMeanGap, 1.0);
    if (s === 0.0) return [mean, 0.0];
    let logRelativeStd;
    if (variance < 1e-16) logRelativeStd = Math.log(s);
    else if (variance > 40.0) logRelativeStd = 0.5 * variance;
    else logRelativeStd = 0.5 * Math.log(Math.expm1(variance));
    return [mean, Math.exp(logMeanGap + logRelativeStd)];
  };

  function forward(y, state) {
    if (typeof y !== "number" || !Number.isFinite(y)) return [y, state || {}];
    const z = fwdQuery(y);
    if (z === -direction * Infinity) {
      throw new Error(`log_transform: observation ${y} must lie inside ${boundLabel}=${b}`);
    }
    return [z, state || {}];
  }
  function inverseK(dists, state) {
    return dists.map((d) => new PushforwardDist(d, null, null, {
      invFn: inv, fwdFn: fwdQuery, logJacobianFn: logJacobian,
      componentMomentsFn: moments, scaledInvFn: inverseAtScale,
    }));
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// AR(p) with online recursive least squares
// ---------------------------------------------------------------------------

// Spectral radius of the AR companion matrix (largest |characteristic root|).
// The h-step forecast converges iff this is < 1. Closed form for p<=2, power
// iteration otherwise.
function arSpectralRadius(phi) {
  const p = phi.length;
  if (p === 1) return Math.abs(phi[0]);
  if (p === 2) {
    const a = phi[0], b = phi[1];
    const disc = a * a + 4.0 * b;
    if (disc >= 0.0) {
      const r = Math.sqrt(disc);
      return Math.max(Math.abs((a + r) / 2.0), Math.abs((a - r) / 2.0));
    }
    return Math.hypot(a / 2.0, Math.sqrt(-disc) / 2.0);
  }
  // Power iteration from a single seed can silently miss the true dominant
  // eigenvalue if that seed happens to be (near-)orthogonal to it. Two seeds
  // unlikely to BOTH align with a non-dominant eigenvector; take the max.
  let best = 0.0;
  for (const seed of [new Array(p).fill(1.0), Array.from({ length: p }, (_, i) => (i % 2 === 0 ? 1.0 : -1.0))]) {
    let v = seed.slice(), rho = 0.0;
    for (let it = 0; it < 60; it++) {
      let s = 0.0;
      for (let j = 0; j < p; j++) s += phi[j] * v[j];
      const nv = new Array(p);
      nv[0] = s;
      for (let i = 1; i < p; i++) nv[i] = v[i - 1];
      let m = 0.0;
      for (const x of nv) m = Math.max(m, Math.abs(x));
      if (m === 0.0) m = 1.0;
      v = nv.map((x) => x / m);
      rho = m;
    }
    best = Math.max(best, rho);
  }
  return best;
}

// Damp AR coefficients into the stationary region for forecasting. Scaling
// phi_j by gamma^(j+1) scales every companion eigenvalue by gamma; a no-op when
// already stationary. Constrained forecasting, not a magnitude clip.
function arStationary(phi, margin = 0.999) {
  const rho = arSpectralRadius(phi);
  if (rho <= margin) return phi;
  const g = margin / rho;
  return phi.map((c, j) => c * Math.pow(g, j + 1));
}

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
      state = { buffer: [], phi: new Array(p).fill(0.0), phi_used: new Array(p).fill(0.0), P: initP(), n: 0 };
    }
    const buf = state.buffer;
    const phi = state.phi;
    if (state.phi_used === undefined) state.phi_used = arStationary(phi.slice());   // pre-#235 checkpoint
    state.n += 1;
    let residual;
    if (buf.length >= p) {
      const x = new Array(p);
      for (let i = 0; i < p; i++) x[i] = buf[buf.length - 1 - i];

      // Emitted residual uses `phi_used` -- the stationarity-projected
      // coefficients as of the end of the previous tick -- not the raw RLS
      // estimate, so forward's emission and inverseK's reconstruction always
      // agree on which predictor produced the residual (skaters#232).
      const phiUsed = state.phi_used;
      const prediction = fsum(Array.from({ length: p }, (_, i) => phiUsed[i] * x[i]));
      residual = y - prediction;

      // RLS update keeps fitting the RAW (unconstrained) least-squares
      // problem with its own prediction error.
      const rawPrediction = fsum(Array.from({ length: p }, (_, i) => phi[i] * x[i]));
      const rawResidual = y - rawPrediction;
      const P = state.P;
      const Px = matVec(P, x, p);
      const denom = lam + dot(x, Px, p);
      if (Math.abs(denom) > 1e-15) {
        const K = Px.map((px) => px / denom);
        for (let i = 0; i < p; i++) phi[i] += K[i] * rawResidual;
        for (let i = 0; i < p; i++) {
          for (let j = 0; j < p; j++) {
            P[i * p + j] = (P[i * p + j] - K[i] * Px[j]) / lam;
          }
        }
        // Guard against RLS covariance windup (see the Python note): under
        // low-excitation input P inflates by 1/lam each step and overflows to
        // Inf, giving nan coefficients. Reset the covariance (keeping phi) if it
        // grows implausibly large or non-finite. No effect on well-excited data.
        let bad = false, pmax = 0.0;
        for (let m = 0; m < P.length; m++) {
          const v = P[m];
          if (!Number.isFinite(v)) { bad = true; break; }
          const av = Math.abs(v);
          if (av > pmax) pmax = av;
        }
        if (bad || pmax > 1e10) { const np = initP(); for (let m = 0; m < P.length; m++) P[m] = np[m]; }
      }
      // Re-project after every update so forward's next emission and
      // inverseK always agree on the same constrained coefficients.
      state.phi_used = arStationary(phi.slice());
    } else {
      residual = y;
    }
    buf.push(y);
    if (buf.length > 2 * p + 10) buf.shift();
    return [residual, state];
  }

  function inverseK(dists, state) {
    const buf = state.buffer.slice();
    // Same coefficients forward() already emitted residuals under
    // (skaters#232) -- maintained incrementally there, not re-derived here,
    // except for a pre-#235 checkpoint that has no cache yet.
    const phi = state.phi_used !== undefined ? state.phi_used : arStationary(state.phi.slice());
    const H = dists.length;
    // Impulse responses psi_0..psi_{H-1}: psi_0 = 1, psi_i = sum_j phi_j psi_{i-j}.
    const psi = [1.0];
    for (let i = 1; i < H; i++) {
      let s = 0.0;
      for (let j = 0; j < p; j++) if (i - 1 - j >= 0) s += phi[j] * psi[i - 1 - j];
      psi.push(s);
    }
    const recoveredMeans = [];
    const result = [];
    for (let h = 0; h < H; h++) {
      let arMean = 0.0;
      for (let j = 0; j < p; j++) {
        const lagH = h - j - 1;
        if (lagH < 0) {
          const bufIdx = buf.length + lagH;
          if (bufIdx >= 0 && bufIdx < buf.length) arMean += phi[j] * buf[bufIdx];
        } else if (lagH < recoveredMeans.length) {
          arMean += phi[j] * recoveredMeans[lagH];
        }
      }
      const totalMean = dists[h].mean + arMean;
      // Var(y_{t+h+1}) = sum_i psi_{h-i}^2 var_i (issue #245); same order as Python/Rust.
      let totalVar = 0.0;
      for (let i = 0; i <= h; i++) totalVar += psi[h - i] * psi[h - i] * dists[i].var;
      const totalStd = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(dists[h].std, 1e-12);
      recoveredMeans.push(totalMean);
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
      state = { buffer: [], theta: new Array(nGroups).fill(0.0), phi_used: new Array(maxLag).fill(0.0), P: eye(nGroups, ridge), n: 0 };
    }
    const buf = state.buffer;
    const th = state.theta;
    if (state.phi_used === undefined) {   // pre-#235 checkpoint
      state.phi_used = arStationary(Array.from({ length: maxLag }, (_, j) => th[groups[j]]));
    }
    state.n += 1;
    let residual;
    if (buf.length >= maxLag) {
      const x = groupRegressor(buf, groups, nGroups, maxLag);

      // Emitted residual uses the previous tick's stationarity-projected,
      // per-lag coefficients -- same fix as ar() (skaters#232).
      const phiUsed = state.phi_used;
      const lagX = new Array(maxLag);
      for (let j = 0; j < maxLag; j++) lagX[j] = buf[buf.length - 1 - j];
      const prediction = fsum(Array.from({ length: maxLag }, (_, j) => phiUsed[j] * lagX[j]));
      residual = y - prediction;

      // RLS update keeps fitting the RAW group-level least-squares problem
      // with its own prediction error.
      const rawPrediction = fsum(Array.from({ length: nGroups }, (_, g) => th[g] * x[g]));
      const rawResidual = y - rawPrediction;
      const P = state.P;
      const Px = matVec(P, x, nGroups);
      const denom = lam + dot(x, Px, nGroups);
      if (Math.abs(denom) > 1e-15) {
        const K = Px.map((px) => px / denom);
        for (let g = 0; g < nGroups; g++) th[g] += K[g] * rawResidual;
        for (let i = 0; i < nGroups; i++) {
          for (let j = 0; j < nGroups; j++) {
            P[i * nGroups + j] = (P[i * nGroups + j] - K[i] * Px[j]) / lam;
          }
        }
        // RLS covariance windup guard (see ar()): reset P if it inflates
        // implausibly or turns non-finite; keeps theta. No effect on well-excited data.
        let bad = false, pmax = 0.0;
        for (let m = 0; m < P.length; m++) {
          const v = P[m];
          if (!Number.isFinite(v)) { bad = true; break; }
          const av = Math.abs(v);
          if (av > pmax) pmax = av;
        }
        if (bad || pmax > 1e10) { const np = eye(nGroups, ridge); for (let m = 0; m < P.length; m++) P[m] = np[m]; }
      }
      const rawPhi = [];
      for (let j = 0; j < maxLag; j++) rawPhi.push(th[groups[j]]);
      state.phi_used = arStationary(rawPhi);
    } else {
      residual = y;
    }
    buf.push(y);
    if (buf.length > maxLag + 10) buf.shift();
    return [residual, state];
  }

  function inverseK(dists, state) {
    const buf = state.buffer.slice();
    // Same coefficients forward() already emitted residuals under
    // (skaters#232) -- maintained incrementally there, not re-derived here,
    // except for a pre-#235 checkpoint that has no cache yet.
    const phi = state.phi_used !== undefined
      ? state.phi_used
      : arStationary(Array.from({ length: maxLag }, (_, j) => state.theta[groups[j]]));
    const H = dists.length;
    const psi = [1.0];
    for (let i = 1; i < H; i++) {
      let s = 0.0;
      for (let j = 0; j < maxLag; j++) if (i - 1 - j >= 0) s += phi[j] * psi[i - 1 - j];
      psi.push(s);
    }
    const recoveredMeans = [];
    const result = [];
    for (let h = 0; h < H; h++) {
      let arMean = 0.0;
      for (let j = 0; j < maxLag; j++) {
        const lagH = h - j - 1;
        if (lagH < 0) {
          const bufIdx = buf.length + lagH;
          if (bufIdx >= 0 && bufIdx < buf.length) arMean += phi[j] * buf[bufIdx];
        } else if (lagH < recoveredMeans.length) {
          arMean += phi[j] * recoveredMeans[lagH];
        }
      }
      const totalMean = dists[h].mean + arMean;
      // Var(y_{t+h+1}) = sum_i psi_{h-i}^2 var_i (issue #245); same order as Python/Rust.
      let totalVar = 0.0;
      for (let i = 0; i <= h; i++) totalVar += psi[h - i] * psi[h - i] * dists[i].var;
      const totalStd = totalVar > 0 ? Math.sqrt(totalVar) : Math.max(dists[h].std, 1e-12);
      recoveredMeans.push(totalMean);
      result.push(Dist.gaussian(totalMean, totalStd));
    }
    return result;
  }
  return { forward, inverseK };
}

// ---------------------------------------------------------------------------
// Empirical Gaussianization (JS port of transform.gaussianize)
// ---------------------------------------------------------------------------

// z = Phi^{-1}(F_hat(y)) with fence-post weights, F_hat from a sorted buffer of
// past inputs sketched to at most maxKnots equal-mass centers. smooth=false
// interpolates the fence-post CDF linearly; smooth=true uses a Gaussian-kernel
// CDF through a monotone C^1 cubic (Fritsch-Butland tangents). Segment slopes
// are guarded at slopeCap times the interquartile slope (guard "move",
// "delete" or "emin") and the forward output is clamped to |z| <= zMax. The
// inverse maps each component by an equal-probability particle approximation
// (nParticles Gaussians), or emits the exact pushforward for a spliced
// predictive. Before warmup observations it standardizes by expanding moments.
export function gaussianize(maxKnots = 39, warmup = 30, nParticles = 9, smooth = false,
                            slopeCap = 20.0, zMax = 8.0, guard = "move") {
  const SLOPE_CAP = slopeCap;
  const Z_MAX = zMax;
  const SQ2 = Math.sqrt(2.0);
  const J = nParticles;
  const mids = [];
  for (let j = 0; j < J; j++) mids.push(normalInvCdf((j + 0.5) / J));
  const edges = [];
  for (let j = 1; j < J; j++) edges.push(normalInvCdf(j / J));
  const fdiv = (a, b) => Math.floor(a / b);

  // Delete knots whose segment slope dy/dz exceeds the cap, walking outward
  // from the median knot. Survivors keep their values and levels.
  function pruneSlopes(ys, zs) {
    const i1 = fdiv(ys.length, 4), i3 = fdiv(3 * ys.length, 4);
    if (i3 <= i1 || zs[i3] <= zs[i1]) return [ys, zs];
    const cap = SLOPE_CAP * (ys[i3] - ys[i1]) / (zs[i3] - zs[i1]);
    if (cap <= 0) return [ys, zs];
    const c = fdiv(ys.length, 2);
    const keep = [c];
    for (let i = c + 1; i < ys.length; i++) {
      const j = keep[keep.length - 1];
      if ((ys[i] - ys[j]) / (zs[i] - zs[j]) <= cap) keep.push(i);
    }
    for (let i = c - 1; i >= 0; i--) {
      const j = Math.min(...keep);
      if ((ys[j] - ys[i]) / (zs[j] - zs[i]) <= cap) keep.push(i);
    }
    keep.sort((a, b) => a - b);
    if (keep.length < 2) return [ys, zs];
    return [keep.map((i) => ys[i]), keep.map((i) => zs[i])];
  }

  // Smallest-rank-displacement guard: the least e such that knots within e
  // ranks of their order statistics admit the slope cap, then project.
  function eminKnots(buf, ys, zs, idxs) {
    const i1 = fdiv(ys.length, 4), i3 = fdiv(3 * ys.length, 4);
    if (i3 <= i1 || zs[i3] <= zs[i1]) return [ys, zs];
    const cap = SLOPE_CAP * (ys[i3] - ys[i1]) / (zs[i3] - zs[i1]);
    if (cap <= 0) return [ys, zs];
    const nb = buf.length, K = ys.length;
    const dz = [];
    for (let j = 0; j < K - 1; j++) dz.push(zs[j + 1] - zs[j]);

    function corridor(e) {
      const lo = [], hi = [];
      for (let j = 0; j < K; j++) {
        lo.push(buf[Math.max(0, idxs[j] - e)]);
        hi.push(buf[Math.min(nb - 1, idxs[j] + e)]);
      }
      const U = new Array(K).fill(0.0);
      U[K - 1] = hi[K - 1];
      for (let j = K - 2; j >= 0; j--) U[j] = Math.min(hi[j], U[j + 1]);
      const Db = new Array(K).fill(0.0);
      Db[K - 1] = lo[K - 1];
      for (let j = K - 2; j >= 0; j--) Db[j] = Math.max(lo[j], Db[j + 1] - cap * dz[j]);
      const L = new Array(K).fill(0.0);
      L[0] = Db[0];
      for (let j = 1; j < K; j++) L[j] = Math.max(Db[j], L[j - 1]);
      for (let j = 0; j < K; j++) if (L[j] > U[j]) return null;
      return [L, U];
    }

    if (corridor(0) !== null) return [ys, zs];
    let loE = 0, hiE = nb;
    while (hiE - loE > 1) {
      const mid = fdiv(loE + hiE, 2);
      if (corridor(mid) !== null) hiE = mid;
      else loE = mid;
    }
    const res = corridor(hiE);
    if (res === null) return [ys, zs];
    const [L, U] = res;
    const w = new Array(K).fill(0.0);
    w[0] = Math.max(L[0], Math.min(ys[0], U[0]));
    for (let j = 1; j < K; j++) {
      const aJ = Math.max(L[j], w[j - 1]);
      const bJ = Math.min(U[j], w[j - 1] + cap * dz[j - 1]);
      w[j] = Math.max(aJ, Math.min(ys[j], bJ));
    }
    const ks = [w[0]], kz = [zs[0]];
    for (let j = 1; j < K; j++) {
      if (w[j] > ks[ks.length - 1]) { ks.push(w[j]); kz.push(zs[j]); }
    }
    return [ks, kz];
  }

  // Cap segment slopes dy/dz in place, walking outward from the median knot.
  function capSlopes(ys, zs) {
    const i1 = fdiv(ys.length, 4), i3 = fdiv(3 * ys.length, 4);
    if (i3 <= i1 || zs[i3] <= zs[i1]) return;
    const cap = SLOPE_CAP * (ys[i3] - ys[i1]) / (zs[i3] - zs[i1]);
    if (cap <= 0) return;
    const c = fdiv(ys.length, 2);
    for (let i = c + 1; i < ys.length; i++) ys[i] = Math.min(ys[i], ys[i - 1] + cap * (zs[i] - zs[i - 1]));
    for (let i = c - 1; i >= 0; i--) ys[i] = Math.max(ys[i], ys[i + 1] - cap * (zs[i + 1] - zs[i]));
  }

  // Fritsch-Butland harmonic-mean tangents: monotone C^1 cubic.
  function tangents(xs, vs) {
    const d = [];
    for (let i = 0; i < xs.length - 1; i++) d.push((vs[i + 1] - vs[i]) / (xs[i + 1] - xs[i]));
    const t = [d[0]];
    for (let i = 1; i < xs.length - 1; i++) {
      const a = d[i - 1], b = d[i];
      t.push(a * b > 0 ? 2.0 * a * b / (a + b) : 0.0);
    }
    t.push(d[d.length - 1]);
    return t;
  }

  function herm(s, dx, v0, v1, t0, t1) {
    const s2 = s * s;
    const s3 = s2 * s;
    return (v0 * (2 * s3 - 3 * s2 + 1) + dx * t0 * (s3 - 2 * s2 + s)
            + v1 * (-2 * s3 + 3 * s2) + dx * t1 * (s3 - s2));
  }

  function hermDs(s, dx, v0, v1, t0, t1) {
    const s2 = s * s;
    return (v0 * (6 * s2 - 6 * s) + dx * t0 * (3 * s2 - 4 * s + 1)
            + v1 * (-6 * s2 + 6 * s) + dx * t1 * (3 * s2 - 2 * s));
  }

  function build(buf) {
    const n = buf.length;
    const m = Math.min(maxKnots, n);
    let cs = [];
    const idxs = [];
    for (let i = 0; i < m; i++) {
      const idx = Math.trunc((i + 0.5) * n / m);
      const y = buf[idx];
      if (cs.length && y <= cs[cs.length - 1]) continue;
      cs.push(y);
      idxs.push(idx);
    }
    if (cs.length < 2) return null;
    if (!smooth) {
      let zs = idxs.map((idx) => normalInvCdf((idx + 1) / (n + 1)));
      if (guard === "delete") [cs, zs] = pruneSlopes(cs, zs);
      else if (guard === "emin") [cs, zs] = eminKnots(buf, cs, zs, idxs);
      else capSlopes(cs, zs);
      return [cs, zs, null];
    }
    // kernel-smoothed CDF on the sketch, Silverman bandwidth
    const mm = cs.length;
    const i1 = fdiv(mm, 4), i3 = fdiv(3 * mm, 4);
    const iqr = cs[i3] - cs[i1];
    const mean = fsum(cs) / mm;
    const sd = Math.sqrt(fsum(cs.map((c) => (c - mean) ** 2)) / mm);
    let scale = iqr > 0 ? Math.min(sd, iqr / 1.34) : sd;
    if (scale <= 0) scale = Math.max(Math.abs(cs[mm - 1] - cs[0]), 1e-8);
    const h = Math.max(0.9 * scale * Math.pow(n, -0.2), 1e-12);
    const R = 8.0 * h;
    const zs = [];
    let lo = 0, hi = 0;
    for (const c of cs) {
      while (lo < mm && cs[lo] < c - R) lo += 1;
      while (hi < mm && cs[hi] <= c + R) hi += 1;
      const terms = [];
      for (let j = lo; j < hi; j++) terms.push(0.5 * (1.0 + erf((c - cs[j]) / (SQ2 * h))));
      const f = (lo + fsum(terms)) / mm;
      zs.push(normalInvCdf((1.0 + n * f) / (n + 2.0)));
    }
    const cs2 = [cs[0]], zs2 = [zs[0]];
    for (let i = 1; i < mm; i++) {
      if (zs[i] > zs2[zs2.length - 1] + 1e-12) { cs2.push(cs[i]); zs2.push(zs[i]); }
    }
    if (cs2.length < 2) return null;
    capSlopes(cs2, zs2);
    return [cs2, zs2, tangents(cs2, zs2)];
  }

  function fwd(y, knots) {
    const [cs, zs, ts] = knots;
    const K = cs.length;
    if (y <= cs[0]) {
      const s0 = ts ? ts[0] : (zs[1] - zs[0]) / (cs[1] - cs[0]);
      return zs[0] + s0 * (y - cs[0]);
    }
    if (y >= cs[K - 1]) {
      const s1 = ts ? ts[K - 1] : (zs[K - 1] - zs[K - 2]) / (cs[K - 1] - cs[K - 2]);
      return zs[K - 1] + s1 * (y - cs[K - 1]);
    }
    const i = bisectRight(cs, y) - 1;
    if (ts === null) return zs[i] + (zs[i + 1] - zs[i]) * (y - cs[i]) / (cs[i + 1] - cs[i]);
    const dx = cs[i + 1] - cs[i];
    return herm((y - cs[i]) / dx, dx, zs[i], zs[i + 1], ts[i], ts[i + 1]);
  }

  function inv(z, knots) {
    const [cs, zs, ts] = knots;
    const K = cs.length;
    if (z <= zs[0]) {
      const s0 = ts ? ts[0] : (zs[1] - zs[0]) / (cs[1] - cs[0]);
      return cs[0] + (z - zs[0]) / Math.max(s0, 1e-12);
    }
    if (z >= zs[K - 1]) {
      const s1 = ts ? ts[K - 1] : (zs[K - 1] - zs[K - 2]) / (cs[K - 1] - cs[K - 2]);
      return cs[K - 1] + (z - zs[K - 1]) / Math.max(s1, 1e-12);
    }
    const i = bisectRight(zs, z) - 1;
    if (ts === null) return cs[i] + (cs[i + 1] - cs[i]) * (z - zs[i]) / (zs[i + 1] - zs[i]);
    const dx = cs[i + 1] - cs[i];
    let s = (z - zs[i]) / (zs[i + 1] - zs[i]);
    for (let it = 0; it < 6; it++) {
      const d = hermDs(s, dx, zs[i], zs[i + 1], ts[i], ts[i + 1]);
      if (d <= 1e-14) break;
      s -= (herm(s, dx, zs[i], zs[i + 1], ts[i], ts[i + 1]) - z) / d;
      s = s < 0.0 ? 0.0 : (s > 1.0 ? 1.0 : s);
    }
    return cs[i] + s * dx;
  }

  function moments(state) {
    const { n, mu, m2 } = state;
    const v = n > 2 ? m2 / (n - 1) : 0.0;
    const sigma = v > 0 ? Math.sqrt(v) : 1e-8;
    return [mu, sigma];
  }

  function forward(y, state) {
    if (state === null || state === undefined) state = { buf: [], n: 0, mu: 0.0, m2: 0.0, knots: null };
    const knots = state.knots;
    let z;
    if (knots !== null) {
      z = fwd(y, knots);
    } else {
      const [mu, s] = moments(state);
      let sigma = s;
      // cold start: scale by the first observed deviation
      if (sigma <= 1e-8) sigma = Math.max(Math.abs(y - mu), 1e-8);
      z = state.n ? (y - mu) / sigma : 0.0;
    }
    z = Math.max(-Z_MAX, Math.min(Z_MAX, z));
    state.buf.splice(bisectRight(state.buf, y), 0, y);
    const n = state.n + 1;
    const d0 = y - state.mu;
    const mu = state.mu + d0 / n;
    state.m2 = state.m2 + d0 * (y - mu);
    state.n = n;
    state.mu = mu;
    state.knots = n >= warmup ? build(state.buf) : null;
    return [z, state];
  }

  function inverseK(dists, state) {
    const knots = state.knots;
    if (knots === null) {
      const [mu, sigma] = moments(state);
      return dists.map((d) => d.affine(sigma, mu));
    }
    const result = [];
    for (const d of dists) {
      if (d.components === undefined || d.components === null) {   // tail-spliced: exact pushforward
        result.push(pushforward(d, (z) => inv(z, knots)));
        continue;
      }
      const comps = [];
      for (const [w, mu, sig] of d.components) {
        const pts = mids.map((q) => inv(mu + sig * q, knots));
        const eds = edges.map((e) => inv(mu + sig * e, knots));
        for (let j = 0; j < J; j++) {
          const lo = j > 0 ? eds[j - 1] : null;
          const hi = j < J - 1 ? eds[j] : null;
          let std;
          if (lo !== null && hi !== null) std = (hi - lo) / 2.0;
          else if (hi !== null) std = hi - pts[j];
          else std = pts[j] - lo;
          comps.push([w / J, pts[j], Math.max(std, 1e-9)]);
        }
      }
      result.push(new Dist(comps).prune(12));
    }
    return result;
  }
  return { forward, inverseK };
}
