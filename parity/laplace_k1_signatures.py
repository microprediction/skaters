"""Frozen k=1 output signatures for laplace: the before/after check for any
change that can move the issued predictive (Dist internals, tails, transforms).

Runs laplace(1) over fixed seeded streams and records, at every step after a
short warm-up, the issued one-step Dist's mean, std, seven quantiles, and the
log density and CDF at the next observation. Each stream gets a sha256 digest
of those values written with full float precision.

    PYTHONPATH=src python parity/laplace_k1_signatures.py --write before.json
    # ... apply the change ...
    PYTHONPATH=src python parity/laplace_k1_signatures.py --compare before.json

--compare prints, per stream and field, whether the digest is unchanged and
the largest absolute move, also in units of the issued std. A change meant to
be invisible at ordinary scales should leave the ordinary streams' digests
identical, or move them by no more than its stated tolerance; the
near-constant and lattice streams are where a numerical fix is expected to
show.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys

from skaters import laplace

PROBS = (0.001, 0.01, 0.1, 0.5, 0.9, 0.99, 0.999)
FIELDS = ("mean", "std") + tuple(f"q{p}" for p in PROBS) + ("logpdf", "cdf")
WARMUP = 50
N = 700


def streams() -> dict[str, list[float]]:
    rng = random.Random(20261106)
    out = {}
    lvl, xs = 0.0, []
    for t in range(N):                     # trend + weekly cycle + noise
        lvl += rng.gauss(0, 0.2)
        xs.append(lvl + 2.0 * math.sin(2 * math.pi * t / 7) + rng.gauss(0, 1.0))
    out["benign"] = xs
    xs = [rng.gauss(0, 8.0 if (t // 150) % 2 else 1.0) for t in range(N)]
    xs[349] = 1e6                          # vol regimes and one monster spike
    out["regimes_spike"] = xs
    xs = [rng.gauss(0, 1) / math.sqrt(rng.gammavariate(1.5, 1 / 1.5)) for _ in range(N)]
    out["student_t3"] = xs                 # heavy tails, df = 3
    x, xs = 0.0, []
    for _ in range(N):                     # mean-reverting AR(1)
        x = -0.6 * x + rng.gauss(0, 1)
        xs.append(x)
    out["ar1_negative"] = xs
    x, xs = 100.0, []
    for _ in range(N):                     # sticky lattice: tick 0.25, mostly repeats
        if rng.random() < 0.3:
            x += 0.25 * rng.choice((-2, -1, 1, 2))
        xs.append(x)
    out["sticky_lattice"] = xs
    xs = [5.0 + (1e-9 * rng.gauss(0, 1) if rng.random() < 0.05 else 0.0) for _ in range(N)]
    out["near_constant"] = xs              # scale far below any absolute tolerance
    xs = [rng.gauss(0, 1) + (40.0 if t >= N // 2 else 0.0) for t in range(N)]
    out["level_shift"] = xs
    return out


def run(ys: list[float]) -> list[list[float]]:
    f = laplace(1)
    state = None
    rows = []
    for t, y in enumerate(ys[:-1]):
        dists, state = f(y, state)
        if t < WARMUP:
            continue
        d, nxt = dists[0], ys[t + 1]
        rows.append([d.mean, d.std] + [d.quantile(p) for p in PROBS]
                    + [d.logpdf(nxt), d.cdf(nxt)])
    return rows


def digest(rows: list[list[float]]) -> str:
    return hashlib.sha256(json.dumps([[repr(v) for v in r] for r in rows]).encode()).hexdigest()


def collect() -> dict:
    out = {}
    for name, ys in streams().items():
        rows = run(ys)
        out[name] = {"sha256": digest(rows), "rows": rows}
    return out


def compare(base: dict, new: dict) -> bool:
    same = True
    for name, b in base.items():
        n = new[name]
        ok = b["sha256"] == n["sha256"]
        same &= ok
        print(f"{name:15s} {'identical' if ok else 'CHANGED'}  {n['sha256'][:16]}")
        if ok:
            continue
        for j, field in enumerate(FIELDS):
            worst, worst_sd = 0.0, 0.0
            for rb, rn in zip(b["rows"], n["rows"]):
                x, y = rb[j], rn[j]
                if x == y or (isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y)):
                    continue
                gap = abs(y - x) if math.isfinite(x) and math.isfinite(y) else math.inf
                worst = max(worst, gap)
                sd = rb[1]
                if sd and math.isfinite(sd):
                    worst_sd = max(worst_sd, gap / sd)
            if worst:
                print(f"    {field:8s} max |move| {worst:.3e}   in std units {worst_sd:.3e}")
    return same


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", metavar="JSON", help="save signatures and values")
    g.add_argument("--compare", metavar="JSON", help="compare against a saved file")
    a = ap.parse_args(argv)
    new = collect()
    if a.write:
        with open(a.write, "w") as fh:
            json.dump(new, fh)
    if a.compare:
        with open(a.compare) as fh:
            return 0 if compare(json.load(fh), new) else 1
    for name, v in new.items():
        print(f"{name:15s} {v['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
