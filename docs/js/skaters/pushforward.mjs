// Exact pushforward of a predictive through a monotone coordinate map.
// JS port of skaters/pushforward.py.
//
// PushforwardDist keeps the inner predictive in the transformed z-coordinate
// and answers queries through the change of variables
//
//   F_Y(y)      = F_Z(z(y))
//   log p_Y(y)  = log p_Z(z(y)) + log dz/dy
//   Q_Y(p)      = y(Q_Z(p))
//
// The map is supplied analytically or as a strictly increasing table. CRPS
// uses numerical quadrature in either case. Consumers that need mixture
// components get a `components` getter that maps each inner Gaussian by
// moment matching (one Gaussian fitted on a quantile grid when the inner has
// no components). Sums mirror CPython: builtin sum() is Neumaier-compensated
// (fsum here), explicit += loops stay plain.

import { fsum } from "./dist.mjs";

const SQRT2 = Math.sqrt(2.0);
const SQRTPI = Math.sqrt(Math.PI);

// 7-point Gauss-Hermite nodes/weights (physicists'), for E[g(Z)], Z ~ N(0,1).
const GH7 = [
  [-2.6519613568352334, 9.717812450995192e-04],
  [-1.6735516287674714, 5.451558281912703e-02],
  [-0.8162878828589647, 4.256072526101278e-01],
  [0.0, 8.102646175568073e-01],
  [0.8162878828589647, 4.256072526101278e-01],
  [1.6735516287674714, 5.451558281912703e-02],
  [2.6519613568352334, 9.717812450995192e-04],
];

function quantileRule(n) {
  // Fourth-power odds give the tails finer resolution under nonlinear maps.
  const edges = [];
  for (let i = 0; i <= n; i++) {
    const a = i ** 4, b = (n - i) ** 4;
    edges.push(a / (a + b));
  }
  const out = [];
  for (let i = 0; i < n; i++) out.push([(edges[i] + edges[i + 1]) * 0.5, edges[i + 1] - edges[i]]);
  return out;
}

const QUANTILE_RULE = quantileRule(257);

// Python's math.hypot(*xs): JS Math.hypot agrees to the last bit or so.
const hypot = (xs) => Math.hypot(...xs);

function bisectLeft(xs, x) {
  let lo = 0, hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (xs[mid] < x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export function bisectRight(xs, x) {
  let lo = 0, hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (x < xs[mid]) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

// Piecewise-linear with linear extrapolation from the end segments.
export function interpTable(x, xs, fs) {
  let i = bisectLeft(xs, x);
  if (i <= 0) i = 1;
  else if (i >= xs.length) i = xs.length - 1;
  const x0 = xs[i - 1], x1 = xs[i];
  return fs[i - 1] + (fs[i] - fs[i - 1]) * (x - x0) / (x1 - x0);
}

// [ys, zs] knots of a monotone map y = invFn(z) on [zLo, zHi]. Knots where
// invFn fails to strictly increase are dropped so every segment has a
// positive, finite slope.
export function tableFromMap(invFn, zLo, zHi, nodes = 400) {
  zHi = Math.max(zHi, zLo + 1e-9);
  const step = (zHi - zLo) / nodes;
  let ys = [], zs = [];
  for (let j = 0; j <= nodes; j++) {
    const z = zLo + step * j;
    const y = invFn(z);
    if (ys.length === 0 || y > ys[ys.length - 1]) { ys.push(y); zs.push(z); }
  }
  if (ys.length < 2) {
    const y0 = invFn(zLo);
    ys = [y0, y0 + 1e-9];
    zs = [zLo, zLo + 1e-9];
  }
  return [ys, zs];
}

export class PushforwardDist {
  // A z-space predictive pushed through a monotone y <-> z map. Supply a table
  // (ys, zs) or an analytic map via opts { invFn, fwdFn, logJacobianFn }
  // (logJacobianFn gives log(dz/dy) evaluated at z). opts.componentMomentsFn
  // optionally gives the mapped [mean, std] of a Gaussian component, and
  // opts.scaledInvFn(z, weight) the inverse times a positive weight.
  constructor(inner, ys = null, zs = null, opts = {}) {
    this.inner = inner;
    this.ys = ys;
    this.zs = zs;
    this.invFn = opts.invFn ?? null;
    this.fwdFn = opts.fwdFn ?? null;
    this.logJacobianFn = opts.logJacobianFn ?? null;
    this.componentMomentsFn = opts.componentMomentsFn ?? null;
    this.scaledInvFn = opts.scaledInvFn ?? null;
    this._comps = null;
    this._grid = null;
  }

  // --- the map ---

  _z(y) {
    // No clamp (skaters#221): interpTable extrapolates linearly past the ends.
    if (this.fwdFn !== null) return this.fwdFn(y);
    return interpTable(y, this.ys, this.zs);
  }

  _y(z) {
    if (this.invFn !== null) return this.invFn(z);
    return interpTable(z, this.zs, this.ys);
  }

  // dz/dy at y (central difference of the exact map when available, segment
  // secant otherwise; end segments extend beyond the table).
  _slope(y) {
    if (this.fwdFn !== null) {
      const h = 1e-5 * (1.0 + Math.abs(y));
      const za = this.fwdFn(y + h), zb = this.fwdFn(y - h);
      if (Number.isFinite(za) && Number.isFinite(zb) && za > zb) return (za - zb) / (2.0 * h);
    }
    if (this.invFn !== null) {
      const z = this._z(y);
      const h = 1e-5 * (1.0 + Math.abs(z));
      const dy = this.invFn(z + h) - this.invFn(z - h);
      if (dy > 0.0) return 2.0 * h / dy;
    }
    const ys = this.ys, zs = this.zs;
    let i = bisectLeft(ys, y);
    i = Math.min(Math.max(i, 1), ys.length - 1);
    return (zs[i] - zs[i - 1]) / (ys[i] - ys[i - 1]);
  }

  // --- queries (exact) ---

  logpdf(x) {
    const z = this._z(x);
    if (z === Infinity || z === -Infinity) return -Infinity;
    if (Number.isNaN(z)) return NaN;
    if (this.logJacobianFn !== null) return this.inner.logpdf(z) + this.logJacobianFn(z);
    return this.inner.logpdf(z) + Math.log(this._slope(x));
  }

  pdf(x) {
    return Math.exp(this.logpdf(x));
  }

  cdf(x) {
    const z = this._z(x);
    if (z === Infinity || z === -Infinity) return z < 0 ? 0.0 : 1.0;
    if (Number.isNaN(z)) return NaN;
    return this.inner.cdf(z);
  }

  quantile(p, tol = 1e-9, maxIter = 2100) {
    return this._y(this.inner.quantile(p, tol, maxIter));
  }

  // CRPS by quadrature over quantiles or over the table in z-space.
  crps(x) {
    if (!Number.isFinite(x)) return Math.abs(x);
    if (this.fwdFn !== null || this.zs === null) return this._crpsFromQuantiles(x);

    const zstar = this._z(x);
    const zs = this.zs;
    const sLo = 1.0 / this._slope(this.ys[0]);
    const sHi = 1.0 / this._slope(this.ys[this.ys.length - 1]);
    const z0 = zs[0], zn = zs[zs.length - 1];
    let base = [z0 - 8.0, z0 - 6.0, z0 - 4.0, z0 - 2.0, z0 - 1.0, ...zs,
                zn + 1.0, zn + 2.0, zn + 4.0, zn + 6.0, zn + 8.0,
                zstar - 1.0, zstar, zstar + 1.0];
    base = [...new Set(base)].sort((a, b) => a - b);
    const nodes = [base[0]];
    for (let k = 1; k < base.length; k++) {
      const z = base[k];
      const lo = nodes[nodes.length - 1];
      const gap = z - lo;
      if (gap > 0.1) {
        const pieces = Math.min(Math.trunc(gap / 0.1) + 1, 40);
        const step = gap / pieces;
        for (let j = 0; j < pieces - 1; j++) nodes.push(lo + step * (j + 1));
      }
      nodes.push(z);
    }
    let total = 0.0;
    let prevZ = nodes[0];
    let cPrev = this.inner.cdf(prevZ);
    for (let k = 1; k < nodes.length; k++) {
      const z = nodes[k];
      const c = this.inner.cdf(z);
      const ind = prevZ >= zstar ? 1.0 : 0.0;
      const g0 = (cPrev - ind) ** 2;
      const g1 = (c - ind) ** 2;
      let yp;
      if (z <= z0) yp = sLo;
      else if (prevZ >= zn) yp = sHi;
      else yp = (this._y(z) - this._y(prevZ)) / (z - prevZ);
      total += 0.5 * (g0 + g1) * (z - prevZ) * yp;
      prevZ = z; cPrev = c;
    }
    return total;
  }

  _crpsFromQuantiles(x) {
    // Twice the pinball loss integrated over p; weights first on overflow.
    let total = 0.0;
    const q = this._qgrid();
    for (let i = 0; i < QUANTILE_RULE.length; i++) {
      const [p, w] = QUANTILE_RULE[i];
      const weight = 2.0 * w * (q[i] >= x ? 1.0 - p : p);
      const gap = Math.abs(q[i] - x);
      if (Number.isFinite(gap)) {
        total += weight * gap;
      } else {
        let weightedQ = weight * q[i];
        if ((q[i] === Infinity || q[i] === -Infinity) && this.scaledInvFn !== null) {
          weightedQ = this.scaledInvFn(this.inner.quantile(p), weight);
        }
        total += Math.abs(weightedQ - weight * x);
      }
    }
    return total;
  }

  // --- affine maps ---

  // The law of a*Y + b, still a pushforward of (a reflection of) the same
  // inner. a > 0 composes the map; a < 0 reflects the inner with
  // inner.scale(-1) so the composed map stays increasing.
  affine(a, b) {
    a = Number(a); b = Number(b);
    if (a === 0.0 || !Number.isFinite(a) || !Number.isFinite(b)) {
      throw new Error("affine needs a finite nonzero a and a finite b");
    }
    const r = a > 0 ? 1.0 : -1.0;
    const inner = r > 0 ? this.inner : this.inner.scale(-1.0);
    const inv = this.invFn, fwd = this.fwdFn, lj = this.logJacobianFn;
    const cmf = this.componentMomentsFn, sinv = this.scaledInvFn;
    const logA = Math.log(Math.abs(a));
    let ys = null, zs = null;
    if (this.ys !== null) {
      ys = this.ys.map((y) => a * y + b);
      zs = this.zs.map((z) => r * z);
      if (r < 0) { ys.reverse(); zs.reverse(); }
    }
    return new PushforwardDist(inner, ys, zs, {
      invFn: inv === null ? null : (z) => a * inv(r * z) + b,
      fwdFn: fwd === null ? null : (y) => r * fwd((y - b) / a),
      logJacobianFn: lj === null ? null : (z) => lj(r * z) - logA,
      componentMomentsFn: cmf === null ? null : (m, s) => {
        const [m0, s0] = cmf(r * m, s);
        return [a * m0 + b, Math.abs(a) * s0];
      },
      scaledInvFn: sinv === null ? null : (z, w) => a * sinv(r * z, w) + w * b,
    });
  }

  shift(delta) {
    return this.affine(1.0, delta);
  }

  scale(factor) {
    if (factor === 0) throw new Error("scale factor must be nonzero");
    return this.affine(factor, 0.0);
  }

  // --- Dist-compatibility shim ---

  // Moment-matched mixture components in y-space (lazy, cached). A spliced or
  // already transformed inner gets one Gaussian fitted to its mapped quantiles.
  get components() {
    if (this._comps === null) {
      const innerComps = this.inner instanceof PushforwardDist ? null : (this.inner.components ?? null);
      if (innerComps === null) {
        const q = this._qgrid();
        const mu = fsum(q.map((y, i) => QUANTILE_RULE[i][1] * y));
        const sd = !Number.isFinite(mu) ? Infinity
          : hypot(q.map((y, i) => Math.sqrt(QUANTILE_RULE[i][1]) * (y - mu)));
        this._comps = [[1.0, mu, sd]];
      } else {
        const moments = this.componentMomentsFn ?? ((m, s) => this._gaussianMoments(m, s));
        this._comps = innerComps.filter(([w]) => w > 0.0).map(([w, m, s]) => [w, ...moments(m, s)]);
      }
    }
    return this._comps;
  }

  _gaussianMoments(m, s) {
    // Centered quadrature (skaters#225); hypot keeps std representable.
    const nodeYs = GH7.map(([x]) => this._y(m + s * SQRT2 * x));
    const mu = fsum(nodeYs.map((y, i) => (GH7[i][1] / SQRTPI) * y));
    if (!Number.isFinite(mu)) return [mu, Infinity];
    const sd = hypot(nodeYs.map((y, i) => Math.sqrt(GH7[i][1] / SQRTPI) * (y - mu)));
    return [mu, Math.max(sd, 1e-12)];
  }

  // Cached mapped quantiles used by numerical moments and CRPS.
  _qgrid() {
    if (this._grid === null) this._grid = QUANTILE_RULE.map(([p]) => this.quantile(p));
    return this._grid;
  }

  get mean() {
    return fsum(this.components.map(([w, m]) => w * m));
  }

  get var() {
    const sd = this.std;
    return sd * sd;
  }

  get std() {
    const comps = this.components;
    if (comps.length === 1) return comps[0][2];
    const mu = this.mean;
    if (!Number.isFinite(mu)) return Infinity;
    return hypot(comps.map(([w, m, s]) => Math.sqrt(w) * Math.hypot(s, m - mu)));
  }

  get length() {
    return this.components.length;
  }
}
