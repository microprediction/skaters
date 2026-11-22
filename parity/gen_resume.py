"""Cross-language resume vectors: Python checkpoints, in the canonical state
layout (docs/STATE.md), that another port must resume.

For every parity scenario (``gen_vectors.build_scenarios`` and
``build_wrapper_scenarios``) the skater runs over a fixed series; at each
checkpoint time t (the state after t observations) the state is written with
``state_to_json``, together with the probes of the next STEPS predictives
(mean, std, logpdf, cdf, two quantiles, crps, as in gen_vectors). A port
builds the same-named skater, loads the state, steps the next STEPS
observations and must match the probes to 1e-6.

The reverse direction: a port writes its own checkpoints of the same
scenarios at the same times as ``{"scenarios": {name: {"60": state, ...}}}``
and ``parity/check_resume.py <file>`` resumes them here.

Run:  python parity/gen_resume.py   (writes parity/resume_vectors.json)
"""

from __future__ import annotations

import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_vectors import (build_scenarios, build_wrapper_scenarios, probe_dist,  # noqa: E402
                         PROBE, Q_LO, Q_HI)
from skaters.state import state_to_json  # noqa: E402

TIMES = (60, 250, 530)
STEPS = 20


def make_resume_series(n: int = TIMES[-1] + STEPS + 1, seed: int = 2027):
    """Mean-reverting level, weekly cycle, noise: long enough for laplace's
    GPD splice (warm-up 500) and bounded well inside the log scenarios' +-15."""
    rng = random.Random(seed)
    lvl, out = 0.0, []
    for t in range(n):
        lvl = 0.97 * lvl + rng.gauss(0, 0.3)
        out.append(lvl + 2.0 * math.sin(2 * math.pi * t / 7) + rng.gauss(0, 1.0))
    assert max(abs(v) for v in out) < 12.0
    return out


def all_scenarios():
    return list(build_scenarios()) + list(build_wrapper_scenarios())


def run_checkpoints(skater, series):
    """{str(t): {"state": canonical, "out": probes of the next STEPS steps}}."""
    out = {}
    state = None
    stops = set(TIMES)
    for i, y in enumerate(series[:TIMES[-1]]):
        _, state = skater(y, state)
        t = i + 1
        if t in stops:
            snap = state_to_json(state)
            text = json.dumps(snap, allow_nan=False)
            # the continuation, from a JSON restore, as a port will run it
            from skaters.state import state_from_json
            st = state_from_json(json.loads(text))
            probes = []
            for y2 in series[t:t + STEPS]:
                dists, st = skater(y2, st)
                probes.append([probe_dist(d) for d in dists])
            out[str(t)] = {"state": json.loads(text), "out": probes}
    return out


def main():
    series = make_resume_series()
    vec = {"series": series, "times": list(TIMES), "steps": STEPS,
           "probe": PROBE, "q_lo": Q_LO, "q_hi": Q_HI, "scenarios": {}}
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
    for name, k, sk in all_scenarios():
        if only and name not in only:
            continue
        vec["scenarios"][name] = {"k": k, "checkpoints": run_checkpoints(sk, series)}
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "resume_vectors.json")
    with open(path, "w") as f:
        json.dump(vec, f, allow_nan=False)
    print(f"wrote {path}: {len(vec['scenarios'])} scenarios x {len(TIMES)} checkpoints")


if __name__ == "__main__":
    main()
