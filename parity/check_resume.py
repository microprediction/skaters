"""Resume another port's checkpoints in Python (the reverse direction of
gen_resume.py).

    python parity/check_resume.py parity/resume_rust.json

The file is ``{"scenarios": {name: {"60": state, "250": state, ...}}}``,
states in the canonical layout (docs/STATE.md), written by the port after
the same number of observations of the series in resume_vectors.json. Each
is loaded with ``state_from_json`` into the same-named Python skater, which
steps the next STEPS observations; the probes must match Python's own
continuation (resume_vectors.json) to 1e-6. Exits non-zero on any mismatch
or missing checkpoint.
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_resume import all_scenarios  # noqa: E402
from gen_vectors import probe_dist, clean  # noqa: E402
from skaters.state import state_from_json  # noqa: E402

TOL = 1e-6


def decode(x):
    return {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}.get(x, x) if isinstance(x, str) else x


def close(a, b):
    a, b = decode(a), decode(b)
    if math.isnan(a) and math.isnan(b):
        return True
    if not (math.isfinite(a) and math.isfinite(b)):
        return a == b
    return abs(a - b) <= TOL + TOL * abs(b)


def main(path):
    here = os.path.dirname(os.path.abspath(__file__))
    ref = json.load(open(os.path.join(here, "resume_vectors.json")))
    theirs = json.load(open(path))["scenarios"]
    series, steps = ref["series"], ref["steps"]
    builders = {name: sk for name, _, sk in all_scenarios()}
    fails = checked = 0
    for name, exp in ref["scenarios"].items():
        got = theirs.get(name)
        if got is None:
            print(f"MISSING {name}"); fails += 1; continue
        for t, cp in exp["checkpoints"].items():
            if t not in got:
                print(f"MISSING {name}@{t}"); fails += 1; continue
            sk = builders[name]
            st = state_from_json(got[t])
            bad = 0
            for j, y in enumerate(series[int(t):int(t) + steps]):
                dists, st = sk(y, st)
                for h, d in enumerate(dists):
                    for a, b in zip(map(clean, probe_dist(d)), cp["out"][j][h]):
                        checked += 1
                        if not close(a, b):
                            bad += 1
            if bad:
                print(f"FAIL {name}@{t}: {bad} mismatches"); fails += 1
    print(f"{checked} values checked; {'RESUME OK' if not fails else f'RESUME FAILED ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
