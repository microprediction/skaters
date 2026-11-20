// Terminal-leaf ensemble — JS port of skaters/terminal.py.
// Mix the sub-models for the MEAN; model the combined residual with one
// terminal leaf (default the scale-mixture leaf), so its shape reaches the
// output undiluted.

import { fsum, Dist } from "./dist.mjs";
import { crpsLeaf } from "./leaf.mjs";

const PIT_DISPERSION_TARGET = 1.0 / 12.0;   // Var[U] for U ~ Uniform(0,1)
const PIT_EWMA_DECAY = 0.98;
const LOSS_FAST_DECAY = 0.90;
const LOSS_SLOW_DECAY = 0.995;
const TEMP_AMBIG_EPS = 0.15 * PIT_DISPERSION_TARGET;   // |e_t| below this defers to the loss-slope tiebreak

export function terminalLeafEnsemble(skaters, {
  leafFn = crpsLeaf,
  k = 1,
  learningRate = 0.5,
  complexityPenalty = 0.0,
  depths = null,
  priorLogWeights = null,
  maxComponents = 20,
  forget = 1.0,
  // Opt-in: drive eta online from the ensemble's own one-step calibration
  // (PIT dispersion, with a fast-vs-slow logpdf tiebreak in the dead band),
  // clipped to [learningRate / tempBand, learningRate * tempBand]. See terminal.py.
  adaptiveTemperature = false,
  tempRho = 0.03,
  tempBand = 3.0,
  gateHook = null,   // granger's gate: () => per-candidate offsets on the combining weights (or null)
} = {}) {
  const n = skaters.length;
  const d = depths === null ? new Array(n).fill(0) : depths;
  const prior = priorLogWeights === null ? new Array(n).fill(0.0) : priorLogWeights;

  // Closures live in the wrapper, never in state: skater state stays pure
  // data (serialisable for checkpoint/restore), mirroring terminal.py.
  const tleafs = Array.from({ length: k }, () => leafFn(1));

  function _skater(y, state) {
    if (state === null || state === undefined) {
      state = {
        sub: new Array(n).fill(null),
        qdist: Array.from({ length: n }, () => []),
        log_w: prior.slice(),
        leaf_state: new Array(k).fill(null),
        leaf_pred: new Array(k).fill(null),
        mean_q: Array.from({ length: k }, () => []),
        adapt: adaptiveTemperature ? {
          log_eta: Math.log(learningRate),
          pit_ewma: PIT_DISPERSION_TARGET,
          loss_fast: null,
          loss_slow: null,
          pred_q: [],          // pending issued h=1 predictive, for next step's signal
        } : null,
      };
    } else if (state.adapt === undefined) {
      state.adapt = null;      // a JS checkpoint from before the adaptive option
    }

    const allDists = [];
    for (let i = 0; i < n; i++) {
      const [di, s] = skaters[i](y, state.sub[i]);
      state.sub[i] = s;
      allDists.push(di);
    }

    // Adaptive selection temperature: resolve the ISSUED predictive from one
    // step ago against this y, turn its PIT dispersion (and, in the dead band,
    // its own logpdf trend) into a heat/cool signal, and use the resulting
    // eta for THIS step's weight update. Causal, same lag as qdist.
    let etaT = learningRate;
    if (adaptiveTemperature) {
      const ad = state.adapt;
      const pq = ad.pred_q;
      if (pq.length) {
        const prevPred = pq.shift();
        let lpC = prevPred.logpdf(y);
        if (!(lpC >= -20.0)) lpC = -20.0;
        else if (lpC > 20.0) lpC = 20.0;
        let u = prevPred.cdf(y);
        if (!(u >= 0.0 && u <= 1.0)) u = 0.5;      // degenerate/NaN guard: no signal
        ad.pit_ewma = PIT_EWMA_DECAY * ad.pit_ewma + (1.0 - PIT_EWMA_DECAY) * (u - 0.5) ** 2;
        if (ad.loss_fast === null) {
          ad.loss_fast = lpC;
          ad.loss_slow = lpC;
        } else {
          ad.loss_fast = LOSS_FAST_DECAY * ad.loss_fast + (1.0 - LOSS_FAST_DECAY) * lpC;
          ad.loss_slow = LOSS_SLOW_DECAY * ad.loss_slow + (1.0 - LOSS_SLOW_DECAY) * lpC;
        }
        const eT = ad.pit_ewma - PIT_DISPERSION_TARGET;
        const dlossT = ad.loss_fast - ad.loss_slow;
        let direction;
        if (Math.abs(eT) > TEMP_AMBIG_EPS) direction = eT > 0.0 ? -1.0 : 1.0;
        else direction = dlossT > 0.0 ? 1.0 : (dlossT < 0.0 ? -1.0 : 0.0);
        ad.log_eta += tempRho * direction;
        const lo = Math.log(learningRate / tempBand);
        const hi = Math.log(learningRate * tempBand);
        ad.log_eta = Math.min(Math.max(ad.log_eta, lo), hi);
      }
      etaT = Math.exp(ad.log_eta);
    }

    for (let i = 0; i < n; i++) {
      const q = state.qdist[i];
      if (q.length) {
        // Bounded loss (mixability): clamp to a finite band so neither a -inf
        // (y far from every component) nor a +inf (an exact hit on a Dirac atom,
        // e.g. the sticky lattice path) can dominate or NaN-poison log_w. The
        // `!(lp >= -20)` arm also catches NaN.
        let lp = q.shift().logpdf(y);
        if (lp > 20.0) lp = 20.0;
        else if (!(lp >= -20.0)) lp = -20.0;
        state.log_w[i] = forget * state.log_w[i] + etaT * lp - complexityPenalty * d[i];
      }
      q.push(allDists[i][0]);
    }

    // granger's gate shifts the combining weights for this step only; the
    // recursion above is untouched. laplace passes no hook.
    const off = gateHook === null ? null : gateHook();
    const lwc = off === null ? state.log_w : state.log_w.map((v, i) => v + off[i]);
    const maxLw = Math.max(...lwc);
    const w = lwc.map((lw) => Math.exp(lw - maxLw));
    const tot = fsum(w);

    const combined = [];
    for (let h = 0; h < k; h++) {
      const muH = fsum(w.map((wi, i) => wi * allDists[i][h].mean)) / tot;

      const mq = state.mean_q[h];
      if (mq.length >= h + 1) {
        const r = y - mq.shift();
        const [ld, ls] = tleafs[h](r, state.leaf_state[h]);
        state.leaf_state[h] = ls;
        state.leaf_pred[h] = ld[0];
      }

      let pred;
      if (state.leaf_pred[h] !== null) {
        pred = state.leaf_pred[h].shift(muH);
      } else {
        pred = Dist.combine(allDists.map((di) => di[h]), w);
        if (pred.components.length > maxComponents) pred = pred.prune(maxComponents);
      }
      combined.push(pred);
      mq.push(muH);
    }
    if (adaptiveTemperature) state.adapt.pred_q.push(combined[0]);
    return [combined, state];
  }
  _skater.skaterName = adaptiveTemperature
    ? `terminal_leaf_ensemble(n=${n}, k=${k}, adaptive_temp)`
    : `terminal_leaf_ensemble(n=${n}, k=${k})`;
  return _skater;
}
