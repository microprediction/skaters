// JS scenario registry — must match parity/gen_vectors.py build_scenarios().

import { leaf, scaleMixtureLeaf, crpsLeaf, garchLeaf } from "../docs/js/skaters/leaf.mjs";
import { conjugate } from "../docs/js/skaters/conjugate.mjs";
import { ema } from "../docs/js/skaters/ema.mjs";
import { precisionWeightedEnsemble } from "../docs/js/skaters/ensemble.mjs";
import { bayesianEnsemble } from "../docs/js/skaters/bayesian.mjs";
import {
  difference, fractionalDifference, standardize, emaTransform, ouTransform, theta, drift,
  holtLinear, garch, seasonalDifference, powerTransform, ar, groupedAr, yeoJohnson,
  seasonalScale, logTransform, gaussianize,
} from "../docs/js/skaters/transform.mjs";
import { laplace, flesaker, dantzig } from "../docs/js/skaters/api.mjs";
import { homogenize, makeCandidates } from "../docs/js/skaters/homogenize.mjs";
import { residualTransform } from "../docs/js/skaters/residual_transform.mjs";
import { terminalLeafEnsemble } from "../docs/js/skaters/terminal.mjs";
import { multiscale } from "../docs/js/skaters/multiscale.mjs";
import { sticky } from "../docs/js/skaters/sticky.mjs";
import { search } from "../docs/js/skaters/search.mjs";
import { gpdtails } from "../docs/js/skaters/tails.mjs";
import {
  build as specBuild, emaSpec, ensembleSpec, conjugateSpec, diffSpec,
} from "../docs/js/skaters/spec.mjs";

export function buildScenarios() {
  const s = [];
  for (const k of [1, 3]) {
    const suf = k === 1 ? "" : `_k${k}`;
    s.push([`leaf${suf}`, k, leaf(k)]);
    s.push([`diff${suf}`, k, conjugate(leaf(k), difference(), k)]);
    s.push([`ema_t${suf}`, k, conjugate(leaf(k), emaTransform(0.1), k)]);
    s.push([`standardize${suf}`, k, conjugate(leaf(k), standardize(), k)]);
    s.push([`theta${suf}`, k, conjugate(leaf(k), theta(0.1), k)]);
    s.push([`drift${suf}`, k, conjugate(leaf(k), drift(0.05, 0.01), k)]);
    s.push([`holt${suf}`, k, conjugate(leaf(k), holtLinear(0.1, 0.05), k)]);
    s.push([`garch${suf}`, k, conjugate(leaf(k), garch(), k)]);
    s.push([`seasonal${suf}`, k, conjugate(leaf(k), seasonalDifference(7), k)]);
    s.push([`power${suf}`, k, conjugate(leaf(k), powerTransform(0.5), k)]);
    s.push([`ar1${suf}`, k, conjugate(leaf(k), ar(1), k)]);
    s.push([`ar2${suf}`, k, conjugate(leaf(k), ar(2, 0.99, 1.0, 1), k)]);
    s.push([`frac${suf}`, k, conjugate(leaf(k), fractionalDifference(0.4, 30), k)]);
    s.push([`grouped_ar${suf}`, k, conjugate(leaf(k), groupedAr(8), k)]);
    s.push([`yeojohnson_log${suf}`, k, conjugate(leaf(k), yeoJohnson(0.0), k)]);
    s.push([`yeojohnson_half${suf}`, k, conjugate(leaf(k), yeoJohnson(0.5), k)]);
    s.push([`ou${suf}`, k, conjugate(leaf(k), ouTransform(0.1), k)]);
    s.push([`ou_sqrt${suf}`, k, conjugate(conjugate(leaf(k), ouTransform(0.1), k), yeoJohnson(0.5), k)]);
    s.push([`seasonal_scale${suf}`, k, conjugate(leaf(k), seasonalScale(7), k)]);
    s.push([`seasonal_scale_c${suf}`, k, conjugate(leaf(k), seasonalScale(7, 0.1, true), k)]);
    s.push([`power_exact${suf}`, k, conjugate(leaf(k), powerTransform(0.5, true), k)]);
    s.push([`yeojohnson_exact${suf}`, k, conjugate(leaf(k), yeoJohnson(0.5, true), k)]);
    s.push([`log_lower${suf}`, k, conjugate(leaf(k), logTransform(-15.0), k)]);
    s.push([`log_upper${suf}`, k, conjugate(leaf(k), logTransform(null, 15.0), k)]);
    s.push([`gaussianize${suf}`, k, conjugate(leaf(k), gaussianize(), k)]);
    s.push([`gaussianize_smooth${suf}`, k, conjugate(leaf(k), gaussianize(39, 30, 9, true), k)]);
    s.push([`gaussianize_delete${suf}`, k, conjugate(leaf(k), gaussianize(15, 30, 9, false, 1.5, 8.0, "delete"), k)]);
    s.push([`gaussianize_emin${suf}`, k, conjugate(leaf(k), gaussianize(15, 30, 9, false, 1.5, 8.0, "emin"), k)]);
    s.push([`ema_skater${suf}`, k, ema(0.05, k)]);
    s.push([`pw_ensemble${suf}`, k,
      precisionWeightedEnsemble([ema(0.05, k), ema(0.2, k)], k)]);
    s.push([`multiscale${suf}`, k, multiscale((kk) => conjugate(leaf(kk), emaTransform(0.1), kk), k)]);
    s.push([`bayes_ensemble${suf}`, k, bayesianEnsemble(
      [ema(0.05, k), conjugate(leaf(k), difference(), k)],
      { k, learningRate: 0.5, complexityPenalty: 0.02, depths: [1, 1] })]);
  }

  // Named policies
  s.push(["pol_laplace", 1, laplace(1)]);
  // laplace at k>1 exercises the multi-step mean-reversion group (gated on k>1).
  s.push(["pol_laplace_k3", 3, laplace(3)]);
  s.push(["pol_flesaker", 1, flesaker(1, -15.0)]);

  // Adaptive-search engine (still public via skaters.search)
  s.push(["search_default", 1, search({ k: 1, expandInterval: 50 })]);

  // Spec-built skaters
  const specConj = conjugateSpec(ensembleSpec([emaSpec(0.01, 1), emaSpec(0.1, 1)], 1), diffSpec());
  s.push(["spec_diff_ensemble", 1, specBuild(specConj)]);
  s.push(["spec_ema", 1, specBuild(emaSpec(0.05, 1))]);

  // Scale-mixture leaf (the discrepancy-from-N(0,1) residual model)
  // GPD tail splice (fast warm-up so it activates within the 150-pt series)
  s.push(["gpd_tails", 1, gpdtails(conjugate(leaf(1), emaTransform(0.1), 1), 1, 0.9, 50, 100)]);

  s.push(["scale_mixture_leaf", 1, scaleMixtureLeaf(1)]);
  s.push(["crps_leaf", 1, crpsLeaf(1)]);
  s.push(["garch_leaf", 1, garchLeaf(1)]);
  s.push(["scalemix_ema", 1, conjugate(scaleMixtureLeaf(1), emaTransform(0.1), 1)]);
  return s;
}

// Wrappers on a skater's own PIT residuals, the adaptive temperature, the
// named search policy, and laplace with a custom terminal leaf. Must match
// parity/gen_vectors.py build_wrapper_scenarios() (vectors "wrapper_scenarios").
export function buildWrapperScenarios() {
  const s = [];
  const emaC = (kk) => conjugate(leaf(kk), emaTransform(0.1), kk);
  s.push(["homogenize", 1, homogenize(emaC(1))]);
  s.push(["homogenize_k2_weights", 2, homogenize(emaC(2), null, 2, "weights")]);
  s.push(["homogenize_k2_state", 2, homogenize(emaC(2), null, 2, "state", 0.5)]);
  s.push(["homogenize_k2_shared", 2, homogenize(emaC(2), null, 2, "shared")]);
  s.push(["homogenize_small_grid", 1, homogenize(emaC(1), makeCandidates([0.0, 0.9], [0.1], [0.0, 0.5]))]);
  for (const model of ["m0", "m1", "m2"]) {
    s.push([`residual_transform_${model}`, 1, residualTransform(emaC(1), model)]);
  }
  s.push(["residual_transform_m2_lr", 1, residualTransform(emaC(1), "m2", 0.05)]);
  s.push(["terminal_adaptive", 1, terminalLeafEnsemble(
    [ema(0.05, 1), conjugate(leaf(1), difference(), 1)],
    { k: 1, depths: [0, 1], adaptiveTemperature: true, tempRho: 0.1 })]);
  s.push(["terminal_adaptive_k3", 3, terminalLeafEnsemble(
    [ema(0.05, 3), conjugate(leaf(3), difference(), 3)],
    { k: 3, depths: [0, 1], adaptiveTemperature: true, forget: 0.99 })]);
  s.push(["pol_dantzig", 1, dantzig(1, { expandInterval: 50 })]);
  s.push(["pol_laplace_garch_leaf", 1, laplace(1, "crps", true, null, 0.03, "gpd", garchLeaf)]);
  return s;
}


// Sticky/dirac scenarios run on the repeat-heavy series (exercise the spike).
export function buildRepeatScenarios() {
  return [
    ["sticky_ema", 1, sticky(conjugate(leaf(1), emaTransform(0.1), 1), 1)],
  ];
}

// Missing-observation scenarios run on the gap series: a non-finite tick must
// not reach the tree, must not advance the base state, and must age the fan by
// one horizon. k=1 holds the previous predictive; k=3 shifts.
export function buildGapScenarios() {
  return [
    ["pol_laplace", 1, laplace(1)],
    ["pol_laplace_k3", 3, laplace(3)],
  ];
}
