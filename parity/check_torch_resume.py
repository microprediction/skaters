"""Cross-language resume for the torch port, both directions.

Forward: every Python checkpoint in parity/resume_vectors.json (written by
gen_resume.py, canonical layout of docs/STATE.md) is loaded with
``skaters.torch.state_from_json`` into the same-named torch skater (the
builders of check_torch.py), which steps the next STEPS observations under
``torch.no_grad``; every probe (mean, std, logpdf, cdf, two quantiles, crps)
must match Python's own continuation to 1e-6.

Reverse: the torch skaters run the same series from scratch and their states
at the same times are written with ``skaters.torch.state_to_json`` to
parity/resume_torch.json as ``{"scenarios": {name: {"60": state, ...}}}``,
which ``parity/check_resume.py`` then resumes in Python.

    PYTHONPATH=src python3 parity/check_torch_resume.py [--only a,b] [--exclude substr,...]
        [--forward-only] [--out parity/resume_torch.json]
    PYTHONPATH=src python3 parity/check_resume.py parity/resume_torch.json

Exits non-zero on any mismatch or missing scenario; there is no skip list.
"""

from __future__ import annotations

import json
import math
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_torch import build_all_scenarios, decode  # noqa: E402

TOL = 1e-6


def close(a, b):
    a, b = float(a), decode(b)
    if math.isnan(a) and math.isnan(b):
        return True
    if not (math.isfinite(a) and math.isfinite(b)):
        return a == b
    return abs(a - b) <= TOL + TOL * abs(b)


def probes(d, probe, q_lo, q_hi):
    return [d.mean, d.std, d.logpdf(probe), d.cdf(probe), d.quantile(q_lo), d.quantile(q_hi), d.crps(probe)]


def forward(ref, builders, names, verbose=True):
    """Resume every Python checkpoint in torch; returns (fails, checked)."""
    from skaters.torch.state import state_from_json
    series, steps = ref["series"], ref["steps"]
    probe, q_lo, q_hi = ref["probe"], ref["q_lo"], ref["q_hi"]
    fails = checked = 0
    for name in names:
        exp = ref["scenarios"][name]
        if name not in builders:
            print(f"MISSING {name} (no torch builder)"); fails += 1; continue
        sk = builders[name][1]()
        for t, cp in exp["checkpoints"].items():
            st = state_from_json(cp["state"])
            bad = 0
            with torch.no_grad():
                for j, y in enumerate(series[int(t):int(t) + steps]):
                    dists, st = sk(y, st)
                    for h, d in enumerate(dists):
                        for a, b in zip(probes(d, probe, q_lo, q_hi), cp["out"][j][h]):
                            checked += 1
                            if not close(a, b):
                                bad += 1
                                if bad <= 2:
                                    print(f"  {name}@{t} step {j} h {h}: torch {float(a)!r} python {b!r}")
            if bad:
                print(f"FAIL {name}@{t}: {bad} mismatches"); fails += 1
            elif verbose:
                print(f"ok   {name}@{t}")
    return fails, checked


def write_torch_checkpoints(ref, builders, names, path):
    """Run each torch skater from scratch and write its canonical states at
    the checkpoint times."""
    from skaters.torch.state import state_to_json
    series, times = ref["series"], [int(t) for t in ref["times"]]
    out = {}
    for name in names:
        if name not in builders:
            continue
        sk = builders[name][1]()
        st = None
        snaps = {}
        with torch.no_grad():
            for i, y in enumerate(series[:max(times)]):
                _, st = sk(y, st)
                if i + 1 in times:
                    snaps[str(i + 1)] = json.loads(json.dumps(state_to_json(st), allow_nan=False))
        out[name] = snaps
    with open(path, "w") as f:
        json.dump({"scenarios": out}, f, allow_nan=False)
    return path


def main(argv):
    ref = json.load(open(os.path.join(HERE, "resume_vectors.json")))
    builders = build_all_scenarios()
    names = list(ref["scenarios"])
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
        names = [n for n in names if n in only]
    if "--exclude" in argv:             # name substrings, for splitting a long run
        drop = argv[argv.index("--exclude") + 1].split(",")
        names = [n for n in names if not any(d in n for d in drop)]
    verbose = "-q" not in argv
    fails, checked = forward(ref, builders, names, verbose)
    print(f"forward: {checked} values checked; {'OK' if not fails else f'FAILED ({fails})'}")
    if "--forward-only" in argv:
        return 0 if not fails else 1
    path = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(HERE, "resume_torch.json")
    write_torch_checkpoints(ref, builders, names, path)
    print(f"wrote {path}")
    rfails, rchecked = reverse(ref, path, names)
    print(f"reverse: {rchecked} values checked; {'OK' if not rfails else f'FAILED ({rfails})'}")
    ok = not fails and not rfails
    print("RESUME OK" if ok else "RESUME FAILED")
    return 0 if ok else 1


def reverse(ref, path, names):
    """check_resume.py restricted to ``names``: Python resumes torch's
    checkpoints and must match its own continuation."""
    from check_resume import close as py_close
    from gen_resume import all_scenarios
    from gen_vectors import probe_dist, clean
    from skaters.state import state_from_json
    theirs = json.load(open(path))["scenarios"]
    series, steps = ref["series"], ref["steps"]
    py = {name: sk for name, _, sk in all_scenarios()}
    fails = checked = 0
    for name in names:
        got = theirs.get(name)
        if got is None:
            print(f"MISSING reverse {name}"); fails += 1; continue
        for t, cp in ref["scenarios"][name]["checkpoints"].items():
            if t not in got:
                print(f"MISSING reverse {name}@{t}"); fails += 1; continue
            st = state_from_json(got[t])
            bad = 0
            for j, y in enumerate(series[int(t):int(t) + steps]):
                dists, st = py[name](y, st)
                for h, d in enumerate(dists):
                    for a, b in zip(map(clean, probe_dist(d)), cp["out"][j][h]):
                        checked += 1
                        if not py_close(a, b):
                            bad += 1
            if bad:
                print(f"FAIL reverse {name}@{t}: {bad} mismatches"); fails += 1
    return fails, checked


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
