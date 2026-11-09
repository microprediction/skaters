// granger JS parity against the Python reference (parity/granger_vectors.json).
//   node parity/check_granger.mjs
import { readFileSync } from "node:fs";
import { granger, loadGrangerParams } from "../docs/js/skaters/granger.mjs";

const ATOL = 1e-6, RTOL = 1e-6;     // the repo's JS parity gate
const V = JSON.parse(readFileSync(new URL("./granger_vectors.json", import.meta.url), "utf8"));
let worst = 0, bad = 0;
for (const [key, st] of Object.entries(V)) {
  const freq = key.split("/")[0];
  const f = granger(await loadGrangerParams(freq));
  let s = null;
  for (let t = 0; t < st.ys.length - 1; t++) {
    let d;
    [d, s] = f(st.ys[t], s);
    const m = d[0];
    const got = [m.logpdf(st.ys[t + 1]), m.mean, m.std, m.w[0], m.quantile(0.1), m.quantile(0.9)];
    got.forEach((a, i) => {
      const b = st.rows[t][i];
      const dev = Math.abs(a - b);
      worst = Math.max(worst, dev / Math.max(1, Math.abs(b)));
      if (!(dev <= ATOL + RTOL * Math.abs(b))) { if (bad < 5) console.log(`${key} step ${t} q${i}: js ${a} py ${b}`); bad++; }
    });
  }
}
console.log(`[granger js parity] worst relative deviation ${worst.toExponential(2)}, failures ${bad}`);
process.exit(bad ? 1 : 0);
