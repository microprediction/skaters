// Gaussian mixture distribution — JS port of skaters/dist.py.
//
// A Dist is a weighted mixture of Gaussians: components = [[w, m, s], ...].
// Weights are positive and normalized to sum to 1; std is always > 0.
// Pure JS, no dependencies. JS lacks Math.erf, so erf and erfc are a port
// of fdlibm s_erf.c (FreeBSD msun; Copyright (C) 1993 Sun Microsystems, Inc.;
// permission to use, copy, modify and distribute this software is freely
// granted, provided that this notice is preserved). The same algorithm
// backs the Rust port (libm crate). Both stay within about 1 ulp of the
// platform libm that Python's math.erf and math.erfc call.

const SQRT2 = Math.SQRT2;
const SQRT2PI = Math.sqrt(2.0 * Math.PI);
const LOG_SQRT2PI = 0.5 * Math.log(2.0 * Math.PI);

const ERX = 8.45062911510467529297e-01;
const EFX8 = 1.02703333676410069053e+00;
const PP0 = 1.28379167095512558561e-01, PP1 = -3.25042107247001499370e-01,
  PP2 = -2.84817495755985104766e-02, PP3 = -5.77027029648944159157e-03,
  PP4 = -2.37630166566501626084e-05;
const QQ1 = 3.97917223959155352819e-01, QQ2 = 6.50222499887672944485e-02,
  QQ3 = 5.08130628187576562776e-03, QQ4 = 1.32494738004321644526e-04,
  QQ5 = -3.96022827877536812320e-06;
const PA0 = -2.36211856075265944077e-03, PA1 = 4.14856118683748331666e-01,
  PA2 = -3.72207876035701323847e-01, PA3 = 3.18346619901161753674e-01,
  PA4 = -1.10894694282396677476e-01, PA5 = 3.54783043256182359371e-02,
  PA6 = -2.16637559486879084300e-03;
const QA1 = 1.06420880400844228286e-01, QA2 = 5.40397917702171048937e-01,
  QA3 = 7.18286544141962662868e-02, QA4 = 1.26171219808761642112e-01,
  QA5 = 1.36370839120290507362e-02, QA6 = 1.19844998467991074170e-02;
const RA0 = -9.86494403484714822705e-03, RA1 = -6.93858572707181764372e-01,
  RA2 = -1.05586262253232909814e+01, RA3 = -6.23753324503260060396e+01,
  RA4 = -1.62396669462573470355e+02, RA5 = -1.84605092906711035994e+02,
  RA6 = -8.12874355063065934246e+01, RA7 = -9.81432934416914548592e+00;
const SA1 = 1.96512716674392571292e+01, SA2 = 1.37657754143519042600e+02,
  SA3 = 4.34565877475229228821e+02, SA4 = 6.45387271733267880336e+02,
  SA5 = 4.29008140027567833386e+02, SA6 = 1.08635005541779435134e+02,
  SA7 = 6.57024977031928170135e+00, SA8 = -6.04244152148580987438e-02;
const RB0 = -9.86494292470009928597e-03, RB1 = -7.99283237680523006574e-01,
  RB2 = -1.77579549177547519889e+01, RB3 = -1.60636384855821916062e+02,
  RB4 = -6.37566443368389627722e+02, RB5 = -1.02509513161107724954e+03,
  RB6 = -4.83519191608651397019e+02;
const SB1 = 3.03380607434824582924e+01, SB2 = 3.25792512996573918826e+02,
  SB3 = 1.53672958608443695994e+03, SB4 = 3.19985821950859553908e+03,
  SB5 = 2.55305040643316442583e+03, SB6 = 4.74528541206955367215e+02,
  SB7 = -2.24409524465858183362e+01;
const X1P_1022 = 2.2250738585072014e-308;

const _buf = new DataView(new ArrayBuffer(8));
function highWord(x) { _buf.setFloat64(0, x); return _buf.getUint32(0); }
function clearLowWord(x) { _buf.setFloat64(0, x); _buf.setUint32(4, 0); return _buf.getFloat64(0); }

function erfc1(x) {
  const s = Math.abs(x) - 1.0;
  const p = PA0 + s * (PA1 + s * (PA2 + s * (PA3 + s * (PA4 + s * (PA5 + s * PA6)))));
  const q = 1.0 + s * (QA1 + s * (QA2 + s * (QA3 + s * (QA4 + s * (QA5 + s * QA6)))));
  return 1.0 - ERX - p / q;
}

function erfc2(ix, x) {
  if (ix < 0x3ff40000) return erfc1(x);
  x = Math.abs(x);
  const s = 1.0 / (x * x);
  let r, S;
  if (ix < 0x4006db6d) {
    r = RA0 + s * (RA1 + s * (RA2 + s * (RA3 + s * (RA4 + s * (RA5 + s * (RA6 + s * RA7))))));
    S = 1.0 + s * (SA1 + s * (SA2 + s * (SA3 + s * (SA4 + s * (SA5 + s * (SA6 + s * (SA7 + s * SA8)))))));
  } else {
    r = RB0 + s * (RB1 + s * (RB2 + s * (RB3 + s * (RB4 + s * (RB5 + s * RB6)))));
    S = 1.0 + s * (SB1 + s * (SB2 + s * (SB3 + s * (SB4 + s * (SB5 + s * (SB6 + s * SB7))))));
  }
  const z = clearLowWord(x);
  return Math.exp(-z * z - 0.5625) * Math.exp((z - x) * (z + x) + r / S) / x;
}

export function erf(x) {
  let ix = highWord(x);
  const sign = ix >>> 31;
  ix &= 0x7fffffff;
  if (ix >= 0x7ff00000) return 1.0 - 2.0 * sign + 1.0 / x;
  if (ix < 0x3feb0000) {
    if (ix < 0x3e300000) return 0.125 * (8.0 * x + EFX8 * x);
    const z = x * x;
    const r = PP0 + z * (PP1 + z * (PP2 + z * (PP3 + z * PP4)));
    const s = 1.0 + z * (QQ1 + z * (QQ2 + z * (QQ3 + z * (QQ4 + z * QQ5))));
    return x + x * (r / s);
  }
  const y = ix < 0x40180000 ? 1.0 - erfc2(ix, x) : 1.0 - X1P_1022;
  return sign ? -y : y;
}

export function erfc(x) {
  let ix = highWord(x);
  const sign = ix >>> 31;
  ix &= 0x7fffffff;
  if (ix >= 0x7ff00000) return 2.0 * sign + 1.0 / x;
  if (ix < 0x3feb0000) {
    if (ix < 0x3c700000) return 1.0 - x;
    const z = x * x;
    const r = PP0 + z * (PP1 + z * (PP2 + z * (PP3 + z * PP4)));
    const s = 1.0 + z * (QQ1 + z * (QQ2 + z * (QQ3 + z * (QQ4 + z * QQ5))));
    const y = r / s;
    if (sign || ix < 0x3fd00000) return 1.0 - (x + x * y);
    return 0.5 - (x - 0.5 + x * y);
  }
  if (ix < 0x403c0000) return sign ? 2.0 - erfc2(ix, x) : erfc2(ix, x);
  return sign ? 2.0 - X1P_1022 : X1P_1022 * X1P_1022;
}

// --- pure-JS Gaussian math (mirrors dist.py) ---

function gaussianPdf(x, mean, std) {
  if (std <= 0) return x === mean ? Infinity : 0.0;
  const z = (x - mean) / std;
  return Math.exp(-0.5 * z * z) / (std * SQRT2PI);
}

function gaussianCdf(x, mean, std) {
  if (std <= 0) return x >= mean ? 1.0 : 0.0;
  return 0.5 * (1.0 + erf((x - mean) / (std * SQRT2)));
}

function absExpectation(m, s) {
  // E|N(m, s^2)| = m(2Φ(m/s) - 1) + 2s·φ(m/s).
  if (s <= 0) return Math.abs(m);
  const z = m / s;
  return m * (2.0 * gaussianCdf(z, 0.0, 1.0) - 1.0) + 2.0 * s * gaussianPdf(z, 0.0, 1.0);
}

// Neumaier-compensated sum, matching CPython 3.12+'s built-in sum() on floats
// (the Python reference uses sum() for Dist normalisation and moments; the port
// must reproduce it bit-for-bit or pruning tie-breaks diverge).
export function fsum(values) {
  let s = 0.0, c = 0.0;
  for (const x of values) {
    const t = s + x;
    if (Math.abs(s) >= Math.abs(x)) c += (s - t) + x;
    else c += (x - t) + s;
    s = t;
  }
  return s + c;
}

// Extended dist types (e.g. the GPD tail splice) register their decoders
// here at module load, keeping the import graph one-directional.
const _distDecoders = {};
export function registerDistDecoder(tag, fn) { _distDecoders[tag] = fn; }

// Module-private key for the trusted constructor path (Dist.trusted).
const TRUSTED = Symbol("skaters.Dist.trusted");

export class Dist {
  // components: array of [weight, mean, std]
  constructor(components, mode = undefined) {
    if (!components || components.length === 0) {
      throw new Error("Dist requires at least one component");
    }
    if (mode === TRUSTED) {
      // Already-normalised weights, assigned without dividing by the
      // compensated sum. Only Dist.trusted can reach this branch.
      this.components = components;
      return;
    }
    const wTotal = fsum(components.map((c) => c[0]));
    if (!(wTotal > 0)) throw new Error("Dist weights must sum to > 0");
    this.components = components.map(([w, m, s]) => [w / wTotal, m, s]);
  }

  // Trusted-input construction: the components are taken as given, bit for
  // bit, with no renormalising. For the inverse of toDict and for callers
  // that have already normalised. Goes through the real constructor, so a
  // subclass or a second own property keeps working.
  static trusted(components) {
    return new this(components, TRUSTED);
  }

  // --- constructors ---

  static gaussian(mean = 0.0, std = 1.0) {
    return new Dist([[1.0, mean, std]]);
  }

  static combine(dists, weights = null) {
    const n = dists.length;
    if (weights === null) weights = new Array(n).fill(1.0 / n);
    const wTotal = fsum(weights);
    const components = [];
    for (let i = 0; i < n; i++) {
      const wOuter = weights[i];
      for (const [wInner, m, s] of dists[i].components) {
        components.push([(wOuter / wTotal) * wInner, m, s]);
      }
    }
    return new Dist(components);
  }

  // --- queries ---

  pdf(x) {
    let total = 0.0;
    for (const [w, m, s] of this.components) {
      if (w <= 0.0) continue;   // skaters#222: 0 * Infinity at a discarded (s=0) atom is NaN
      total += w * gaussianPdf(x, m, s);
    }
    return total;
  }

  logpdf(x) {
    // Log density accumulated in log-space (log-sum-exp). A Gaussian mixture is
    // strictly positive everywhere, so for finite x this is always finite;
    // log(sum(w * pdf)) would underflow to -Infinity once x sits many standard
    // deviations from every component (e.g. after the scale collapses on a
    // near-constant stream), because each exp(-z*z/2) rounds to 0.
    let best = -Infinity;
    const terms = [];
    for (const [w, m, s] of this.components) {
      if (w <= 0.0) continue;
      if (s <= 0.0) {
        if (x === m) return Infinity;
        continue;
      }
      const z = (x - m) / s;
      const t = Math.log(w) - 0.5 * z * z - Math.log(s) - LOG_SQRT2PI;
      terms.push(t);
      if (t > best) best = t;
    }
    if (best === -Infinity) return -Infinity;
    let acc = 0.0;
    for (const t of terms) acc += Math.exp(t - best);
    return best + Math.log(acc);
  }

  cdf(x) {
    let total = 0.0;
    for (const [w, m, s] of this.components) total += w * gaussianCdf(x, m, s);
    return total;
  }

  crps(x) {
    // Closed-form CRPS for a Gaussian mixture (Grimit et al. 2006).
    const comps = this.components;
    let t1 = 0.0;
    for (const [w, m, s] of comps) t1 += w * absExpectation(m - x, s);
    let t2 = 0.0;
    for (const [wi, mi, si] of comps) {
      for (const [wj, mj, sj] of comps) {
        t2 += wi * wj * absExpectation(mi - mj, Math.sqrt(si * si + sj * sj));
      }
    }
    return t1 - 0.5 * t2;
  }

  // Same bracket, tolerance, atom and binary64 convergence rules as Python.
  quantile(p, tol = 1e-9, maxIter = 2100) {
    if (!(p > 0 && p < 1)) throw new Error("quantile p must be in (0, 1)");
    const mu = this.mean, sigma = Math.sqrt(this.var);
    if (!Number.isFinite(sigma)) throw new Error("quantile needs a finite mixture variance");
    let minSigma = Infinity;
    for (const [w, , s] of this.components) if (w > 0 && s > 0) minSigma = Math.min(minSigma, s);
    if (!Number.isFinite(minSigma)) minSigma = 1.0;
    const xTol = tol * Math.min(1.0, minSigma);
    let lo = mu - 8 * sigma, hi = mu + 8 * sigma;
    const seed = Math.max(16 * sigma, 1e-12 * Math.max(1.0, Math.abs(mu)));
    let width = seed, found = false;
    for (let i = 0; i < 120; i++) {
      if (this.cdf(lo) < p) { found = true; break; }
      lo -= width; width *= 2.0;
    }
    if (!found) throw new Error("could not bracket quantile from below");
    width = seed; found = false;
    for (let i = 0; i < 120; i++) {
      if (this.cdf(hi) >= p) { found = true; break; }
      hi += width; width *= 2.0;
    }
    if (!found) throw new Error("could not bracket quantile from above");
    if (!(Number.isFinite(lo) && Number.isFinite(hi))) throw new Error("quantile needs a finite search bracket");
    for (let i = 0; i < maxIter; i++) {
      let mid = 0.5 * (lo + hi);
      if (!Number.isFinite(mid)) mid = 0.5 * lo + 0.5 * hi;
      if (!(lo < mid && mid < hi)) {
        const gap = hi - lo;
        if (0 < tol && tol <= 2 * gap) {
          let lower = 0, upper = 0, swappedLower = 0, swappedUpper = 0;
          for (const [w, m, s] of this.components) {
            const cl = w * gaussianCdf(lo, m, s), cu = w * gaussianCdf(hi, m, s);
            lower += cl; upper += cu;
            const unresolved = w > 0 && s <= gap;
            swappedLower += unresolved ? cu : cl;
            swappedUpper += unresolved ? cl : cu;
          }
          if (swappedLower === lower && swappedUpper === upper) return mid;
        }
        return hi;
      }
      if (this.cdf(mid) < p) lo = mid;
      else hi = mid;
      if (hi - lo < xTol) {
        for (const [w, m, s] of this.components) {
          if (w > 0 && s === 0 && lo <= m && m <= hi) {
            let left = 0.0;
            for (const [wi, mi, si] of this.components) left += wi * (si === 0 ? Number(mi < m) : gaussianCdf(m, mi, si));
            if (left < p && p <= this.cdf(m)) return m;
          }
        }
        break;
      }
    }
    const mid = 0.5 * (lo + hi);
    return Number.isFinite(mid) ? mid : 0.5 * lo + 0.5 * hi;
  }

  get mean() {
    return fsum(this.components.map(([w, m]) => w * m));
  }

  get var() {
    // centered form: avoids catastrophic cancellation when means are large
    // relative to spreads (which would otherwise yield var=0, std=0).
    const mu = this.mean;
    return fsum(this.components.map(([w, m, s]) => w * (s * s + (m - mu) * (m - mu))));
  }

  get std() {
    const v = this.var;
    return v > 0 ? Math.sqrt(v) : 0.0;
  }

  // --- transform support ---

  shift(delta) {
    return new Dist(this.components.map(([w, m, s]) => [w, m + delta, s]));
  }

  scale(factor) {
    if (factor === 0) throw new Error("scale factor must be nonzero");
    const f = Math.abs(factor);
    return new Dist(this.components.map(([w, m, s]) => [w, m * factor, s * f]));
  }

  affine(a, b) {
    if (a === 0) throw new Error("affine a must be nonzero");
    return new Dist(this.components.map(([w, m, s]) => [w, a * m + b, Math.abs(a) * s]));
  }

  // Number of mixture components (mirrors Python's __len__).
  get length() {
    return this.components.length;
  }

  // --- pruning ---

  prune(maxComponents = 20) {
    maxComponents = Math.max(1, maxComponents);   // a Dist needs >=1 component
    if (this.components.length <= maxComponents) return this;
    // Sort first so the merge path (and hence the result) is independent of
    // component order — mixtures are order-free but the closest-pair scan
    // is not, and ties at equal means are common (lattice atoms).
    let comps = this.components.map((c) => c.slice())
      .sort((a, b) => (a[1] - b[1]) || (a[2] - b[2]) || (a[0] - b[0]));
    // Pair selection tolerates last-ulp noise in the means: pick the FIRST
    // pair within a hair of the true minimum distance, so platforms that
    // disagree at the ulp level (e.g. libm erf vs a polynomial) still merge
    // the same pairs in the same order. Exact argmin would amplify ulp
    // noise into macroscopically different mixtures.
    // Translation-invariant (skaters#226): the span of the sorted means, not
    // the sum of their absolute locations (which inflates with translation).
    const scale = (comps[comps.length - 1][1] - comps[0][1]) + 1e-12;
    while (comps.length > maxComponents) {
      let bestDist = Infinity;
      for (let i = 0; i < comps.length; i++)
        for (let j = i + 1; j < comps.length; j++) {
          const d = Math.abs(comps[i][1] - comps[j][1]);
          if (d < bestDist) bestDist = d;
        }
      const thresh = bestDist + 1e-9 * scale;
      let bestI = null, bestJ = null;
      outer:
      for (let i = 0; i < comps.length; i++)
        for (let j = i + 1; j < comps.length; j++)
          if (Math.abs(comps[i][1] - comps[j][1]) <= thresh) { bestI = i; bestJ = j; break outer; }
      const [wi, mi, si] = comps[bestI];
      const [wj, mj, sj] = comps[bestJ];
      const wNew = wi + wj;
      let mNew, sNew;
      if (wNew < 1e-300) {
        mNew = 0.5 * (mi + mj);
        sNew = Math.max(si, sj, 1e-12);
      } else {
        mNew = (wi * mi + wj * mj) / wNew;
        const vNew =
          (wi * (si * si + (mi - mNew) * (mi - mNew))
            + wj * (sj * sj + (mj - mNew) * (mj - mNew))) / wNew;
        sNew = Math.sqrt(Math.max(vNew, 0.0));
      }
      comps[bestI] = [wNew, mNew, sNew];
      comps.splice(bestJ, 1);
    }
    return new Dist(comps);
  }

  // --- serialization ---

  toDict() {
    return { components: this.components.map((c) => c.slice()) };
  }

  static fromDict(d) {
    if (d.spliced) {
      const fn = _distDecoders.spliced;
      if (!fn) throw new Error("spliced dist: import tails.mjs before fromDict");
      return fn(d);
    }
    // The exact inverse of toDict. Weights that already sum to one, to
    // within 1e-9 of the compensated sum, take the trusted path and are kept
    // bit-for-bit: renormalising a normalised mixture divides by a total that
    // is one only up to rounding, which can move the last bit and break a
    // checkpoint/restore round trip. A loose hand-written dict still goes
    // through the normalising constructor. Mirrors Dist.from_dict in Python.
    const components = d.components.map((c) => c.slice());
    const wTotal = fsum(components.map((c) => c[0]));
    if (Math.abs(wTotal - 1.0) <= 1e-9) return Dist.trusted(components);
    return new Dist(components);
  }

}

// Classes allowed inside skater state (see state.mjs). Dist is one; extended
// dist types register themselves alongside their decoder.
const _distClasses = [Dist];
export function registerDistClass(cls) { if (!_distClasses.includes(cls)) _distClasses.push(cls); }
export function isDistInstance(v) {
  for (const cls of _distClasses) if (v instanceof cls) return true;
  return false;
}
