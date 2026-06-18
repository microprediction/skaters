// User-facing API — JS port of skaters/api.py (named search policies).
//
// Every named policy builds a Bayesian ensemble over the SAME shared
// candidate population. They differ only in prior, learning rate, and
// complexity penalty — i.e., the search strategy. (dantzig lives in
// search.mjs because it uses adaptive search.)

import { leaf, scaleMixtureLeaf, crpsLeaf } from "./leaf.mjs";
import { conjugate } from "./conjugate.mjs";
import { terminalLeafEnsemble } from "./terminal.mjs";
import { bayesianEnsemble } from "./bayesian.mjs";
import { search } from "./search.mjs";
import { sticky as project } from "./sticky.mjs";
import {
  difference, fractionalDifference, standardize, emaTransform, drift,
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

  return [candidates, depths, groups];
}

function priorFavoringDepths(depths, favored, boost = 2.0) {
  return depths.map((d) => (favored.has(d) ? boost : 0.0));
}

function priorFavoringIndices(n, favored, boost = 2.0) {
  const out = new Array(n).fill(0.0);
  for (const i of favored) out[i] = boost;
  return out;
}

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

function objectiveLeaf(objective) {
  if (objective === "crps") return crpsLeaf;
  if (objective === "likelihood") return scaleMixtureLeaf;
  throw new Error(`objective must be 'crps' or 'likelihood', got ${objective}`);
}

export function skater(k = 1, aggressiveness = 0.5, objective = "crps", sticky = true) {
  if (!(aggressiveness > 0 && aggressiveness < 1)) throw new Error("aggressiveness in (0,1)");
  const learningRate = 0.1 + 0.8 * aggressiveness;
  const complexityPenalty = 0.05 * (1 - aggressiveness);
  const [candidates, depths] = buildCandidates(k);
  let f = terminalLeafEnsemble(candidates, { k, leafFn: objectiveLeaf(objective), learningRate, complexityPenalty, depths, maxComponents: 20 });
  if (sticky) f = project(f, k);
  f.skaterName = `skater(k=${k})`;
  return f;
}

export function holt(k = 1) {
  const [candidates, depths, groups] = buildCandidates(k);
  const trend = new Set([...groups.diff, ...groups.drift, ...groups.holt]);
  const priorLogWeights = priorFavoringIndices(candidates.length, trend, 3.0);
  const f = terminalLeafEnsemble(candidates, {
    k, learningRate: 0.5, complexityPenalty: 0.02, depths, priorLogWeights, maxComponents: 15,
  });
  f.skaterName = `holt(k=${k})`;
  return f;
}

export function hosking(k = 1) {
  const [candidates, depths, groups] = buildCandidates(k);
  const priorLogWeights = priorFavoringIndices(candidates.length, new Set(groups.frac), 3.0);
  const f = terminalLeafEnsemble(candidates, {
    k, learningRate: 0.5, complexityPenalty: 0.01, depths, priorLogWeights, maxComponents: 15,
  });
  f.skaterName = `hosking(k=${k})`;
  return f;
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

export function wald(k = 1) {
  const [candidates, depths] = buildCandidates(k);
  const priorLogWeights = priorFavoringDepths(depths, new Set([0]), 2.0);
  const f = terminalLeafEnsemble(candidates, {
    k, learningRate: 0.15, complexityPenalty: 0.08, depths, priorLogWeights, maxComponents: 10,
  });
  f.skaterName = `wald(k=${k})`;
  return f;
}

export function samuelson(k = 1) {
  const [candidates, depths, groups] = buildCandidates(k);
  const priorLogWeights = priorFavoringDepths(depths, new Set([2]), 2.0);
  for (const i of new Set([...groups.drift, ...groups.holt])) priorLogWeights[i] = 5.0;
  const f = terminalLeafEnsemble(candidates, {
    k, learningRate: 0.4, complexityPenalty: 0.01, depths, priorLogWeights, maxComponents: 15,
  });
  f.skaterName = `samuelson(k=${k})`;
  return f;
}

export function dantzig(k = 1) {
  const f = search({
    k, learningRate: 0.3, complexityPenalty: 0.01, maxPool: 40,
    expandInterval: 50, expandTopN: 5, maxDepth: 3, costBudget: 10.0,
  });
  f.skaterName = `dantzig(k=${k})`;
  return f;
}

export function kahneman(k = 1, strength = 8.0) {
  const [candidates, depths, groups] = buildCandidates(k);
  const priorLogWeights = priorFavoringIndices(candidates.length, new Set(groups.fast_slow), strength);
  const f = terminalLeafEnsemble(candidates, {
    k, learningRate: 0.5, complexityPenalty: 0.01, depths, priorLogWeights, maxComponents: 15,
  });
  f.skaterName = `kahneman(k=${k})`;
  return f;
}

export function dirac(k = 1, spikeFrac = 0.003) {
  // skater is sticky by default; dirac is the harder-atom shorthand.
  const f = project(skater(k, 0.5, "crps", false), k, 0.05, spikeFrac);
  f.skaterName = `dirac(k=${k})`;
  return f;
}

export function doob(k = 1) {
  // committed martingale mean + learned volatility clock (time-changed BM).
  // Same mean across candidates -> BMA blends vol clocks without washing kurtosis.
  const cands = [
    conjugate(leaf(k), difference(), k),
    conjugate(conjugate(leaf(k), garch(), k), difference(), k),
    conjugate(conjugate(leaf(k), standardize(0.02), k), difference(), k),
    conjugate(conjugate(scaleMixtureLeaf(k), garch(), k), difference(), k),
    conjugate(scaleMixtureLeaf(k), difference(), k),
  ];
  const f = bayesianEnsemble(cands, { k, learningRate: 0.5, depths: [1, 2, 2, 2, 1], maxComponents: 30 });
  f.skaterName = `doob(k=${k})`;
  return f;
}
