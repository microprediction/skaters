"""Cross-language resume vectors for granger: Python checkpoints in the
canonical layout (docs/STATE.md, the `granger` row) and the next steps' issued
mixture, for each shipped parameter set on two of gen_granger_vectors.py's
streams (one with leading and one with mid-series missing values).

At each checkpoint t the file holds the state after t observations and, for
the next STEPS observations, the mixture's log density at the following
value, its mean, spread, laplace's weight and its 10% and 90% quantiles. A
port loads the state into a granger built from the same parameters, steps,
and matches the rows to 1e-6 (rust/tests/granger_parity.rs).

    PYTHONPATH=src python3 parity/gen_granger_resume.py  # -> parity/granger_resume.json
"""
import json
import os

from gen_granger_vectors import streams
from skaters.granger import available, granger
from skaters.state import state_from_json, state_to_json

TIMES = (2, 30, 120)
STEPS = 12
STREAMS = ("trend_cycle", "mid_nan", "leading_nan")


def main():
    out = {}
    all_streams = streams()
    for freq in available():
        for name in STREAMS:
            ys = all_streams[name]
            g = granger(1, frequency=freq)
            s = None
            cps = {}
            for t, y in enumerate(ys[:TIMES[-1]]):
                _, s = g(y, s)
                if t + 1 in TIMES:
                    snap = json.loads(json.dumps(state_to_json(s), allow_nan=False))
                    st = state_from_json(snap)
                    rows = []
                    for j in range(t + 1, t + 1 + STEPS):
                        d, st = g(ys[j], st)
                        m = d[0]
                        nxt = ys[j + 1]
                        lp = m.logpdf(nxt) if nxt == nxt else None
                        rows.append([lp, m.mean, m.std, m.w[0], m.quantile(0.1), m.quantile(0.9)])
                    cps[str(t + 1)] = {"state": snap, "rows": rows}
            out[f"{freq}/{name}"] = {"ys": [None if v != v else v for v in ys], "checkpoints": cps}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "granger_resume.json")
    with open(path, "w") as fh:
        json.dump(out, fh, allow_nan=False)
    print(f"[gen_granger_resume] {len(out)} streams x {len(TIMES)} checkpoints -> {path}")


if __name__ == "__main__":
    main()
