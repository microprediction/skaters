// Race engine for the in-browser benchmark. Pure logic, no DOM.
//
// Every competitor exposes `.pending` (a Dist forecasting the next change) and
// `.step(y)` (consume the realized change, advance, refresh `.pending`). The
// harness scores each `.pending` on held-out log-likelihood and CRPS through the
// same skaters `Dist` — so a point/interval method is judged as the Gaussian it
// really is, exactly like the paper's harness.
//
// laplace and naive are online (O(1)/step) and sweep the whole universe. The
// Holt-Winters competitor refits every step and is meant for the single-series
// drill-down, where its slowness is the show.

import { laplace, Dist } from "../js/skaters/index.mjs";

// --- laplace: native predictive Dist, online -------------------------------
export function makeLaplace() {
  const f = laplace(1);
  let state = null, pending = null;
  return {
    name: "laplace",
    kind: "online",
    get pending() { return pending; },
    step(y) {
      const [dists, s] = f(y, state);
      pending = dists[0];
      state = s;
    },
  };
}

// --- naive: EWMA mean of the change series + a rolling std, online ----------
export function makeNaive() {
  let mean = null, ewmaVar = 1e-4, pending = Dist.gaussian(0, 1);
  const aMean = 0.1, aVar = 0.05;
  return {
    name: "naive",
    kind: "online",
    get pending() { return pending; },
    step(y) {
      if (mean === null) {
        mean = y;
      } else {
        const r = y - mean;
        ewmaVar = (1 - aVar) * ewmaVar + aVar * r * r;
        mean = (1 - aMean) * mean + aMean * y;
      }
      pending = Dist.gaussian(mean, Math.sqrt(Math.max(ewmaVar, 1e-9)));
    },
  };
}

// --- Holt-Winters: Holt's linear (level+trend), grid-searched, refit each step
// Deliberately not online: it re-optimises alpha/beta over the full history on
// every step, like the npm holtwinters package. Wraps its point forecast with a
// rolling residual std to become a scorable Gaussian.
export function makeHoltWinters(grid = [0.1, 0.3, 0.5, 0.7, 0.9]) {
  const history = [];
  let residVar = 1e-4, pending = Dist.gaussian(0, 1);
  const aVar = 0.05;

  function forecastNext(d) {
    const n = d.length;
    if (n < 3) return d[n - 1] ?? 0;
    let best = { sse: Infinity, next: d[n - 1] };
    for (const alpha of grid) {
      for (const beta of grid) {
        let level = d[0], trend = d[1] - d[0], sse = 0;
        for (let t = 1; t < n; t++) {
          const e = d[t] - (level + trend);
          sse += e * e;
          const newLevel = alpha * d[t] + (1 - alpha) * (level + trend);
          trend = beta * (newLevel - level) + (1 - beta) * trend;
          level = newLevel;
        }
        if (sse < best.sse) best = { sse, next: level + trend };
      }
    }
    return best.next;
  }

  return {
    name: "holt-winters",
    kind: "refit",
    get pending() { return pending; },
    step(y) {
      if (history.length) {
        const r = y - pending.mean;
        residVar = (1 - aVar) * residVar + aVar * r * r;
      }
      history.push(y);
      pending = Dist.gaussian(forecastNext(history), Math.sqrt(Math.max(residVar, 1e-9)));
    },
  };
}

// --- score one series through a set of competitors -------------------------
// Returns [{name, meanLL, meanCRPS, n}] plus per-step traces if `trace` is set.
export function runSeries(changes, competitors, burn = 100) {
  const acc = competitors.map(() => ({ ll: 0, crps: 0 }));
  let n = 0;
  for (let i = 0; i < changes.length; i++) {
    const y = changes[i];
    if (i >= burn) {
      for (let k = 0; k < competitors.length; k++) {
        const p = competitors[k].pending;
        if (p) {
          acc[k].ll += p.logpdf(y);
          acc[k].crps += p.crps(y);
        }
      }
      n++;
    }
    for (const c of competitors) c.step(y);
  }
  return competitors.map((c, k) => ({
    name: c.name,
    kind: c.kind,
    meanLL: n ? acc[k].ll / n : NaN,
    meanCRPS: n ? acc[k].crps / n : NaN,
    n,
  }));
}
