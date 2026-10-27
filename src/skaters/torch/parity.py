"""Side-by-side runner: the reference transform and its torch twin on the
same series, the same leaf distributions, compared step by step.

``check_parity(name, kwargs, series, k)`` drives both ports through
``series`` and, at every step after the first, maps ``k`` seeded random
mixtures through both ``inverse_k`` implementations. It returns the largest
absolute discrepancy seen in the forward emissions and in every component
(weight, mean, std) of every inverse output. A port is accepted at 1e-9:
the two run the same float64 arithmetic in the same order, so anything
larger is a porting error, not round-off.
"""

from __future__ import annotations

import math
import random

import torch

import skaters.transform as ref
from skaters.dist import Dist
from skaters.torch.dist import TorchDist
from skaters.torch.transform import from_reference


def random_series(n: int = 300, seed: int = 0, kind: str = "ar") -> list[float]:
    """A test series with level, scale and a little structure, so every
    branch of a transform sees traffic: AR(1) with drift and a level shift."""
    rng = random.Random(seed)
    y, out = 10.0, []
    for t in range(n):
        shock = rng.gauss(0.0, 1.0)
        if kind == "ar":
            y = 10.0 + 0.6 * (y - 10.0) + 0.02 * t + shock + (5.0 if t == n // 2 else 0.0)
        elif kind == "positive":
            y = max(0.5, y + 0.3 * shock)
        elif kind == "seasonal":
            y = 10.0 + 3.0 * math.sin(2 * math.pi * t / 7) + 0.5 * shock
        out.append(y)
    return out


def random_dists(k: int, rng: random.Random, zero_mean: bool = False) -> list[Dist]:
    """k random Gaussian mixtures (1 to 3 components) in the transformed space."""
    out = []
    for _ in range(k):
        n = rng.randint(1, 3)
        comps = []
        for _ in range(n):
            w = rng.uniform(0.2, 1.0)
            m = 0.0 if zero_mean else rng.gauss(0.0, 0.5)
            s = rng.uniform(0.1, 1.5)
            comps.append((w, m, s))
        out.append(Dist(comps))
    return out


def check_parity(name: str, kwargs: dict, series: list[float], k: int = 3,
                 seed: int = 1, every: int = 1, zero_mean: bool = False) -> dict:
    fwd, inv = getattr(ref, name)(**kwargs)
    mod = from_reference(name, **kwargs)
    rng = random.Random(seed)
    s_ref = None
    s_tor = None
    worst_z = 0.0
    worst_c = 0.0
    with torch.no_grad():
        for t, y in enumerate(series):
            z_ref, s_ref = fwd(y, s_ref)
            z_tor, s_tor = mod(y, s_tor)
            worst_z = max(worst_z, abs(float(z_tor) - z_ref))
            if t == 0 or t % every:
                continue
            dists = random_dists(k, rng, zero_mean=zero_mean)
            out_ref = inv(dists, s_ref)
            out_tor = mod.inverse_k([TorchDist.from_reference(d) for d in dists], s_tor)
            if len(out_ref) != len(out_tor):
                raise AssertionError(f"{name}: inverse_k lengths differ {len(out_ref)} vs {len(out_tor)}")
            for a, b in zip(out_ref, out_tor):
                bc = b.to_reference().components
                if len(a.components) != len(bc):
                    raise AssertionError(f"{name}: component counts differ at t={t}: "
                                         f"{len(a.components)} vs {len(bc)}")
                for (w1, m1, s1), (w2, m2, s2) in zip(a.components, bc):
                    worst_c = max(worst_c, abs(w1 - w2), abs(m1 - m2), abs(s1 - s2))
    return {"forward": worst_z, "inverse": worst_c}


def gradient_check(name: str, kwargs: dict, series: list[float], k: int = 2,
                   seed: int = 1) -> dict:
    """Backpropagate a log score through forward and inverse_k over the
    series; return each parameter's gradient. All must be finite."""
    mod = from_reference(name, **kwargs)
    rng = random.Random(seed)
    state = None
    loss = torch.zeros((), dtype=torch.float64)
    for t, y in enumerate(series[:-k]):
        _, state = mod(y, state)
        if t < 2:
            continue
        dists = [TorchDist.from_reference(d) for d in random_dists(k, rng)]
        out = mod.inverse_k(dists, state)
        for h, d in enumerate(out, start=1):
            loss = loss - d.logpdf(series[t + h])
    loss.backward()
    return {n: (None if p.grad is None else float(p.grad)) for n, p in mod.named_parameters()}
