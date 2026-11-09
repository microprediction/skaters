"""Vectors for the Rust granger parity test: the pure-Python granger's issued
mixture at every step (log density at the next observation, mean, spread,
laplace's mixture weight, 10% and 90% quantiles) on seeded streams, for each
shipped parameter set. Missing observations are null in ``ys``; the log
density at a missing next value is null.

    PYTHONPATH=src python parity/gen_granger_vectors.py   # -> parity/granger_vectors.json
"""
import json
import math
import os
import random

from skaters.granger import available, granger


def streams(n=200):
    rng = random.Random(23)
    out = {}
    x, xs = 0.0, []
    for t in range(n):
        x += rng.gauss(0, 0.3)
        xs.append(x + math.sin(2 * math.pi * t / 12) + rng.gauss(0, 1))
    out["trend_cycle"] = xs
    out["regimes"] = [rng.gauss(0, 4.0 if (t // 50) % 2 else 1.0) for t in range(n)]
    v, xs = 10.0, []
    for _ in range(n):
        if rng.random() < 0.35:
            v += 0.25 * rng.choice((-1, 1))
        xs.append(v)
    out["sticky"] = xs
    # missing values: leading (the expert's ensemble has not stepped yet) and mid-series
    ys = [rng.gauss(0, 1) for _ in range(n)]
    out["leading_nan"] = [float("nan")] * 3 + ys[3:]
    out["mid_nan"] = [v if t not in (40, 41, 120) else float("nan") for t, v in enumerate(ys)]
    return out


def main():
    out = {}
    for freq in available():
        for name, ys in streams().items():
            g = granger(1, frequency=freq)
            s = None
            rows = []
            for t, y in enumerate(ys[:-1]):
                d, s = g(y, s)
                m = d[0]
                nxt = ys[t + 1]
                lp = m.logpdf(nxt) if nxt == nxt else None      # no score at a missing value
                rows.append([lp, m.mean, m.std, m.w[0], m.quantile(0.1), m.quantile(0.9)])
            # JSON has no NaN: a missing observation is null
            out[f"{freq}/{name}"] = {"ys": [None if v != v else v for v in ys], "rows": rows}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "granger_vectors.json")
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"[gen_granger_vectors] {len(out)} streams -> {path}")


if __name__ == "__main__":
    main()
