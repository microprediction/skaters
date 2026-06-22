// User-facing API — JS port of skaters/api.py (named search policies).
//
// Two named forecasters: laplace (general) and doob (martingale specialist).

import { leaf, scaleMixtureLeaf, crpsLeaf } from "./leaf.mjs";
import { conjugate } from "./conjugate.mjs";
import { terminalLeafEnsemble } from "./terminal.mjs";
import { bayesianEnsemble } from "./bayesian.mjs";
import { sticky as project } from "./sticky.mjs";
import {
  difference, fractionalDifference, standardize, emaTransform, ouTransform, drift,
  holtLinear, ar, theta, seasonalDifference, garch, powerTransform, yeoJohnson,
} from "./transform.mjs";

// ---------------------------------------------------------------------------
// Shared candidate population
// ---------------------------------------------------------------------------

export function buildCandidates(k) {
  const candidates = [];
  const depths = [];
  const groups = {};
  const push = (c, d) => {
    candidates.push(c);
    depths.push(d);
    return candidates.length - 1;
  };

  // Depth 0: baseline noise
  push(leaf(k), 0);

  // Depth 1: single EMA at various speeds
  for (const alpha of [0.01, 0.05, 0.1, 0.3]) push(conjugate(leaf(k), emaTransform(alpha), k), 1);

  // Depth 1: differencing (pure random walk)
  groups.diff = [];
  groups.diff.push(push(conjugate(leaf(k), difference(), k), 1));

  // Depth 1: drift (random walk with adaptive drift)
  groups.drift = [];
  for (const [a, s] of [[0.05, 0.01], [0.01, 0.002], [0.002, 0.001], [0.0005, 0.0002]]) {
    groups.drift.push(push(conjugate(leaf(k), drift(a, s), k), 1));
  }

  // Depth 1: Theta
  for (const a of [0.05, 0.1, 0.3]) push(conjugate(leaf(k), theta(a), k), 1);

  // Depth 1: AR
  push(conjugate(leaf(k), ar(1), k), 1);
  push(conjugate(leaf(k), ar(2, 0.99, 1.0, 1), k), 1);

  // Depth 1: Holt linear
  groups.holt = [];
  for (const [a, b] of [[0.1, 0.02], [0.1, 0.05], [0.3, 0.1]]) {
    groups.holt.push(push(conjugate(leaf(k), holtLinear(a, b), k), 1));
  }

  // Depth 1: Seasonal differencing
  for (const period of [7, 12, 24]) push(conjugate(leaf(k), seasonalDifference(period), k), 1);

  // Depth 2: Seasonal differencing + EMA
  for (const period of [7, 12, 24]) {
    for (const alpha of [0.05, 0.1]) {
      push(conjugate(conjugate(leaf(k), emaTransform(alpha), k), seasonalDifference(period), k), 2);
    }
  }

  // Depth 2: differencing + EMA
  for (const alpha of [0.05, 0.1, 0.3]) {
    groups.diff.push(push(conjugate(conjugate(leaf(k), emaTransform(alpha), k), difference(), k), 2));
  }

  // Depth 2: standardize + EMA
  for (const alpha of [0.05, 0.1]) {
    push(conjugate(conjugate(leaf(k), emaTransform(alpha), k), standardize(), k), 2);
  }

  // Depth 2: fractional diff + EMA
  groups.frac = [];
  for (const d of [0.2, 0.4]) {
    groups.frac.push(push(conjugate(conjugate(leaf(k), emaTransform(0.1), k), fractionalDifference(d, 30), k), 2));
  }

  // Depth 2: drift + EMA
  for (const [aDrift, sDrift] of [[0.002, 0.001], [0.0005, 0.0002]]) {
    for (const aEma of [0.05, 0.1]) {
      groups.drift.push(push(conjugate(conjugate(leaf(k), emaTransform(aEma), k), drift(aDrift, sDrift), k), 2));
    }
  }

  // Depth 2: drift + Holt linear
  {
    const idx = push(conjugate(conjugate(leaf(k), holtLinear(0.1, 0.05), k), drift(0.001, 0.0005), k), 2);
    groups.drift.push(idx);
    groups.holt.push(idx);
  }

  // Depth 2: GARCH + EMA
  push(conjugate(conjugate(leaf(k), emaTransform(0.1), k), garch(), k), 2);

  // Depth 2: power transform + EMA
  push(conjugate(conjugate(leaf(k), emaTransform(0.1), k), powerTransform(0.5), k), 2);

  // Depth 2: thinking fast and slow (fast tracker outside, slow scale inside)
  const fastTrackers = () => [
    emaTransform(0.3), emaTransform(0.5), holtLinear(0.4, 0.2), ar(1), drift(0.05, 0.01), difference(),
  ];
  groups.fast_slow = [];
  for (const scaleAlpha of [0.02, 0.05]) {
    for (const tracker of fastTrackers()) {
      groups.fast_slow.push(push(conjugate(conjugate(leaf(k), standardize(scaleAlpha), k), tracker, k), 2));
    }
  }

  // Coordinate prior (Yeo-Johnson): learn the coordinate the series is simple in.
  groups.coordinate = [];
  for (const L of [0.0, 0.5]) {
    for (const innerTx of [difference(), emaTransform(0.1)]) {
      groups.coordinate.push(push(conjugate(conjugate(leaf(k), innerTx, k), yeoJohnson(L), k), 2));
    }
  }

  // Mean-reversion prior (Ornstein-Uhlenbeck), MULTI-STEP ONLY: redundant with
  // the ema/random-walk mix at one step, so gated on k > 1 (see api.py).
  groups.mean_revert = [];
  if (k > 1) {
    for (const L of [0.0, 0.5]) {
      for (const kappa of [0.03, 0.1, 0.3]) {
        groups.mean_revert.push(push(
          conjugate(conjugate(leaf(k), ouTransform(kappa, 0.02), k), yeoJohnson(L), k), 2));
      }
    }
  }

  return [candidates, depths, groups];
}

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

function objectiveLeaf(objective) {
  if (objective === "crps") return crpsLeaf;
  if (objective === "likelihood") return scaleMixtureLeaf;
  throw new Error(`objective must be 'crps' or 'likelihood', got ${objective}`);
}

export function laplace(k = 1, objective = "crps", sticky = true) {
  const [candidates, depths] = buildCandidates(k);
  let f = terminalLeafEnsemble(candidates, {
    k, leafFn: objectiveLeaf(objective), learningRate: 0.8, complexityPenalty: 0.005, depths, maxComponents: 20,
  });
  if (sticky) f = project(f, k);
  f.skaterName = `laplace(k=${k})`;
  return f;
}

export function doob(k = 1, objective = "crps") {
  if (objective !== "crps" && objective !== "likelihood") throw new Error(`objective must be 'crps' or 'likelihood', got ${objective}`);
  const lf = objective === "crps" ? crpsLeaf : scaleMixtureLeaf;
  const cands = [
    conjugate(lf(k), difference(), k),
    conjugate(conjugate(lf(k), garch(), k), difference(), k),
    conjugate(conjugate(lf(k), standardize(0.02), k), difference(), k),
    conjugate(conjugate(lf(k), garch(), k), difference(), k),
    conjugate(lf(k), difference(), k),
  ];
  const f = bayesianEnsemble(cands, { k, learningRate: 0.5, depths: [1, 2, 2, 2, 1], maxComponents: 30 });
  f.skaterName = `doob(k=${k})`;
  return f;
}

// The mean-reverting counterpart of doob: an online likelihood-weighted average
// over Ornstein-Uhlenbeck reversion speeds (JS port of api.mean_revert).
export function meanRevert(k = 1, kappas = [0.02, 0.05, 0.1, 0.2, 0.4], alpha = 0.02,
                           coordinate = null, objective = "crps") {
  const leafFn = objectiveLeaf(objective);
  const cands = [];
  const depths = [];
  for (const kp of kappas) {
    let c = conjugate(leaf(k), ouTransform(kp, alpha), k);
    let depth = 1;
    if (coordinate !== null && coordinate !== undefined) {
      c = conjugate(c, yeoJohnson(coordinate), k);
      depth = 2;
    }
    cands.push(c);
    depths.push(depth);
  }
  const f = terminalLeafEnsemble(cands, {
    k, leafFn, learningRate: 0.8, complexityPenalty: 0.005, depths, maxComponents: 20,
  });
  f.skaterName = `mean_revert(k=${k})`;
  return f;
}
