"""Vectors for the Rust granger parity test: the pure-Python granger's issued
mixture at every step (log density at the next observation, mean, spread,
laplace's mixture weight, 10% and 90% quantiles) on seeded streams, for each
shipped parameter set.

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
                rows.append([m.logpdf(ys[t + 1]), m.mean, m.std, m.w[0], m.quantile(0.1), m.quantile(0.9)])
            out[f"{freq}/{name}"] = {"ys": ys, "rows": rows}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "granger_vectors.json")
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"[gen_granger_vectors] {len(out)} streams -> {path}")


if __name__ == "__main__":
    main()
