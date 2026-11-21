// User-facing API — JS port of skaters/api.py (named search policies).
//
// One forecaster: laplace (general). Volatility/mean-reversion are composable transforms.

import { leaf, scaleMixtureLeaf, crpsLeaf } from "./leaf.mjs";
import { conjugate } from "./conjugate.mjs";
import { terminalLeafEnsemble } from "./terminal.mjs";
import { search } from "./search.mjs";
import { bayesianEnsemble } from "./bayesian.mjs";
import { sticky as project } from "./sticky.mjs";
import { multiscale } from "./multiscale.mjs";
import { parade } from "./parade.mjs";
import { gpdtails } from "./tails.mjs";
import {
  difference, fractionalDifference, standardize, emaTransform, ouTransform, drift,
  holtLinear, ar, theta, seasonalDifference, seasonalAnchor, garch, powerTransform,
  yeoJohnson, logTransform,
} from "./transform.mjs";

// ---------------------------------------------------------------------------
// Shared candidate population
// ---------------------------------------------------------------------------

// Each candidate's own residual model is `leafFn` (the plain Gaussian leaf by
// default), as in api._build_candidates; laplace's final residual model is
// the terminal leaf, chosen separately.
export function buildCandidates(k, leafFn = leaf) {
  const candidates = [];
  const depths = [];
  const groups = {};
  const families = [];                 // human family label per candidate (for introspection)
  const push = (c, d, fam) => {
    candidates.push(c);
    depths.push(d);
    families.push(fam);
    return candidates.length - 1;
  };

  // Depth 0: baseline noise
  push(leafFn(k), 0, "baseline");

  // Depth 1: single EMA at various speeds
  for (const alpha of [0.01, 0.05, 0.1, 0.3]) push(conjugate(leafFn(k), emaTransform(alpha), k), 1, "EMA");

  // Depth 1: differencing (pure random walk)
  groups.diff = [];
  groups.diff.push(push(conjugate(leafFn(k), difference(), k), 1, "random walk"));

  // Depth 1: drift (random walk with adaptive drift)
  groups.drift = [];
  for (const [a, s] of [[0.05, 0.01], [0.01, 0.002], [0.002, 0.001], [0.0005, 0.0002]]) {
    groups.drift.push(push(conjugate(leafFn(k), drift(a, s), k), 1, "drift"));
  }

  // Depth 1: Theta
  for (const a of [0.05, 0.1, 0.3]) push(conjugate(leafFn(k), theta(a), k), 1, "Theta");

  // Depth 1: AR
  push(conjugate(leafFn(k), ar(1), k), 1, "AR");
  push(conjugate(leafFn(k), ar(2, 0.99, 1.0, 1), k), 1, "AR");

  // Depth 1: Holt linear
  groups.holt = [];
  for (const [a, b] of [[0.1, 0.02], [0.1, 0.05], [0.3, 0.1]]) {
    groups.holt.push(push(conjugate(leafFn(k), holtLinear(a, b), k), 1, "Holt trend"));
  }

  // Depth 1: Seasonal differencing
  for (const period of [7, 12, 24]) push(conjugate(leafFn(k), seasonalDifference(period), k), 1, "seasonal");

  // Depth 1: Hedged seasonal anchor — phase-EMA blended 50/50 with the
  // seasonal-naive (mirrors api.py; see comparisons/laplace-vs-csp/).
  for (const period of [7, 12, 24]) push(conjugate(leafFn(k), seasonalAnchor(period), k), 1, "seasonal anchor");

  // Depth 2: Seasonal differencing + EMA
  for (const period of [7, 12, 24]) {
    for (const alpha of [0.05, 0.1]) {
      push(conjugate(conjugate(leafFn(k), emaTransform(alpha), k), seasonalDifference(period), k), 2, "seasonal → EMA");
    }
  }

  // Depth 2: differencing + EMA
  for (const alpha of [0.05, 0.1, 0.3]) {
    groups.diff.push(push(conjugate(conjugate(leafFn(k), emaTransform(alpha), k), difference(), k), 2, "random walk → EMA"));
  }

  // Depth 2: standardize + EMA
  for (const alpha of [0.05, 0.1]) {
    push(conjugate(conjugate(leafFn(k), emaTransform(alpha), k), standardize(), k), 2, "standardize → EMA");
  }

  // Depth 2: fractional diff + EMA
  groups.frac = [];
  for (const d of [0.2, 0.4]) {
    groups.frac.push(push(conjugate(conjugate(leafFn(k), emaTransform(0.1), k), fractionalDifference(d, 30), k), 2, "frac-diff → EMA"));
  }

  // Depth 2: drift + EMA
  for (const [aDrift, sDrift] of [[0.002, 0.001], [0.0005, 0.0002]]) {
    for (const aEma of [0.05, 0.1]) {
      groups.drift.push(push(conjugate(conjugate(leafFn(k), emaTransform(aEma), k), drift(aDrift, sDrift), k), 2, "drift → EMA"));
    }
  }

  // Depth 2: drift + Holt linear
  {
    const idx = push(conjugate(conjugate(leafFn(k), holtLinear(0.1, 0.05), k), drift(0.001, 0.0005), k), 2, "drift → Holt");
    groups.drift.push(idx);
    groups.holt.push(idx);
  }

  // Depth 2: GARCH + EMA
  push(conjugate(conjugate(leafFn(k), emaTransform(0.1), k), garch(), k), 2, "GARCH vol → EMA");

  // Depth 2: power transform + EMA
  push(conjugate(conjugate(leafFn(k), emaTransform(0.1), k), powerTransform(0.5), k), 2, "power → EMA");

  // Depth 2: thinking fast and slow (fast tracker outside, slow scale inside)
  const fastTrackers = () => [
    emaTransform(0.3), emaTransform(0.5), holtLinear(0.4, 0.2), ar(1), drift(0.05, 0.01), difference(),
  ];
  groups.fast_slow = [];
  for (const scaleAlpha of [0.02, 0.05]) {
    for (const tracker of fastTrackers()) {
      groups.fast_slow.push(push(conjugate(conjugate(leafFn(k), standardize(scaleAlpha), k), tracker, k), 2, "fast/slow"));
    }
  }

  // Coordinate prior (Yeo-Johnson): learn the coordinate the series is simple in.
  groups.coordinate = [];
  for (const L of [0.0, 0.5]) {
    for (const innerTx of [difference(), emaTransform(0.1)]) {
      groups.coordinate.push(push(conjugate(conjugate(leafFn(k), innerTx, k), yeoJohnson(L), k), 2, "coordinate (Yeo-Johnson)"));
    }
  }

  // Mean-reversion prior (Ornstein-Uhlenbeck), MULTI-STEP ONLY: redundant with
  // the ema/random-walk mix at one step, so gated on k > 1 (see api.py).
  groups.mean_revert = [];
  if (k > 1) {
    for (const L of [0.0, 0.5]) {
      for (const kappa of [0.03, 0.1, 0.3]) {
        groups.mean_revert.push(push(
          conjugate(conjugate(leafFn(k), ouTransform(kappa, 0.02), k), yeoJohnson(L), k), 2, "mean reversion (OU)"));
      }
    }
  }

  return [candidates, depths, groups, families];
}

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

function objectiveLeaf(objective, scaleAlpha) {
  if (objective === "crps") return (k) => crpsLeaf(k, undefined, scaleAlpha);
  if (objective === "likelihood") return (k) => scaleMixtureLeaf(k, undefined, scaleAlpha);
  throw new Error(`objective must be 'crps' or 'likelihood', got ${objective}`);
}

function laplaceSingleScale(k, objective, sticky, scaleAlpha, leafFactory) {
  const [candidates, depths] = buildCandidates(k);
  let f = terminalLeafEnsemble(candidates, {
    k, leafFn: leafFactory !== null && leafFactory !== undefined ? leafFactory : objectiveLeaf(objective, scaleAlpha), learningRate: 0.8, complexityPenalty: 0.005, depths, maxComponents: 20,
    forget: 0.99,
  });
  if (sticky) f = project(f, k);
  return f;
}

// Multi-scale by default at k > 1: one instance per decimation stride
// (default {1, ceil(sqrt(k)), k}), horizons mix eligible scales by likelihood.
// Pass scales = [1] for the single-scale (native fan-out) variant.
//
// scaleAlpha is the terminal leaf's residual-variance EWMA rate (how fast the
// predictive scale tracks volatility). Default 0.03 beats the older 0.01 on
// held-out log-likelihood AND CRPS across the continuous FRED universe; pass
// scaleAlpha = 0.01 to reproduce the earlier default.
//
// leaf optionally overrides the objective's terminal leaf with a factory
// leaf(k) -> skater, e.g. laplace(1, "crps", true, null, 0.03, "gpd", garchLeaf)
// (Python's laplace(leaf=garch_leaf)). It comes last so the existing
// positional order is unchanged; scaleAlpha is ignored when it is given.
export function laplace(k = 1, objective = "crps", sticky = true, scales = null, scaleAlpha = 0.03, tails = "gpd",
  leaf = null) {
  if (tails !== "gpd" && tails !== "gaussian") throw new Error(`tails must be 'gpd' or 'gaussian', got ${tails}`);
  // conditional tail fit (body -> region -> tail), then parade reads PIT/z
  // against the spliced predictive (see tails.mjs, parade.mjs)
  let f = multiscale((kk) => laplaceSingleScale(kk, objective, sticky, scaleAlpha, leaf), k, { scales });
  if (tails === "gpd") f = gpdtails(f, k);
  f = parade(f, k);
  f.skaterName = `laplace(k=${k})`;
  return f;
}

// laplace for a series that never crosses a known bound. Experimental (an
// example composition, as in api.flesaker). Forecasts log(y - lower) with
// laplace and maps the predictive back by the exact change of variables.
// The default bound is lower = 0; pass upper for a one-sided ceiling. The
// returned state is laplace's own. laplaceArgs are laplace's positional
// arguments after k: [objective, sticky, scales, scaleAlpha, tails].
export function flesaker(k = 1, lower = null, upper = null, ...laplaceArgs) {
  const { forward, inverseK } = logTransform(lower, upper);
  const inner = laplace(k, ...laplaceArgs);
  function skater(y, state) {
    const [yp] = forward(y, null);
    const [dists, st] = inner(yp, state);
    return [inverseK(dists, {}), st];
  }
  const bound = upper !== null && upper !== undefined
    ? `upper=${upper}` : `lower=${lower === null || lower === undefined ? 0.0 : lower}`;
  skater.skaterName = `flesaker(k=${k}, ${bound})`;
  return skater;
}

// Adaptive-search skater: grow the model space online instead of fixing it
// (api.dantzig). Beam search over the transform grammar, with replay so new
// candidates join warm. Accepts search's options ({ expandInterval, maxPool,
// costBudget, ... }); k is the forecast horizon.
export function dantzig(k = 1, opts = {}) {
  const f = search({ ...opts, k });
  f.skaterName = `dantzig(k=${k})`;
  return f;
}
