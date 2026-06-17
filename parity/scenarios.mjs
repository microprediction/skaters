// JS scenario registry — must match parity/gen_vectors.py build_scenarios().

import { leaf, scaleMixtureLeaf } from "../docs/js/skaters/leaf.mjs";
import { conjugate } from "../docs/js/skaters/conjugate.mjs";
import { ema } from "../docs/js/skaters/ema.mjs";
import { precisionWeightedEnsemble } from "../docs/js/skaters/ensemble.mjs";
import { bayesianEnsemble } from "../docs/js/skaters/bayesian.mjs";
import {
  difference, fractionalDifference, standardize, emaTransform, theta, drift,
  holtLinear, garch, seasonalDifference, powerTransform, ar, groupedAr,
} from "../docs/js/skaters/transform.mjs";
import {
  skater, holt, hosking, laplace, wald, samuelson, kahneman, dantzig, dirac,
} from "../docs/js/skaters/api.mjs";
import { sticky } from "../docs/js/skaters/sticky.mjs";
import { search } from "../docs/js/skaters/search.mjs";
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
    s.push([`ema_skater${suf}`, k, ema(0.05, k)]);
    s.push([`pw_ensemble${suf}`, k,
      precisionWeightedEnsemble([ema(0.05, k), ema(0.2, k)], k)]);
    s.push([`bayes_ensemble${suf}`, k, bayesianEnsemble(
      [ema(0.05, k), conjugate(leaf(k), difference(), k)],
      { k, learningRate: 0.5, complexityPenalty: 0.02, depths: [1, 1] })]);
  }

  // Named policies
  const pols = { skater, holt, hosking, laplace, wald, samuelson, kahneman };
  for (const [nm, fac] of Object.entries(pols)) s.push([`pol_${nm}`, 1, fac(1)]);
  s.push(["pol_skater_k2", 2, skater(2)]);
  s.push(["pol_kahneman_k2", 2, kahneman(2)]);

  // Adaptive search and direct search
  s.push(["pol_dantzig", 1, dantzig(1)]);
  s.push(["search_default", 1, search({ k: 1, expandInterval: 50 })]);

  // Spec-built skaters
  const specConj = conjugateSpec(ensembleSpec([emaSpec(0.01, 1), emaSpec(0.1, 1)], 1), diffSpec());
  s.push(["spec_diff_ensemble", 1, specBuild(specConj)]);
  s.push(["spec_ema", 1, specBuild(emaSpec(0.05, 1))]);

  // Scale-mixture leaf (the discrepancy-from-N(0,1) residual model)
  s.push(["scale_mixture_leaf", 1, scaleMixtureLeaf(1)]);
  s.push(["scalemix_ema", 1, conjugate(scaleMixtureLeaf(1), emaTransform(0.1), 1)]);
  return s;
}


// Sticky/dirac scenarios run on the repeat-heavy series (exercise the spike).
export function buildRepeatScenarios() {
  return [
    ["sticky_ema", 1, sticky(conjugate(leaf(1), emaTransform(0.1), 1), 1)],
    ["dirac", 1, dirac(1)],
  ];
}
