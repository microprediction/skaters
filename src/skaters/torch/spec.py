"""Spec-built skaters in torch: the twin of :mod:`skaters.spec`.

The spec grammar, canonical names and JSON (de)serialisation are the
reference's own functions, re-exported unchanged (they are pure dict
operations). Only :func:`build` differs: it materialises the spec into torch
skaters, with transforms from :func:`skaters.torch.transform.from_reference`,
conjugation from :mod:`skaters.torch.conjugate`, the reference leaf as a
constant (``reference_skater``), and a precision-weighted ensemble on
tensors (:func:`precision_weighted_ensemble`, mirroring
:mod:`skaters.ensemble` and :mod:`skaters.runstats`; a private twin until
``skaters.torch.ensemble`` lands).
"""

from __future__ import annotations

import math
from collections import deque

import torch

from skaters.leaf import leaf as reference_leaf
from skaters.spec import (  # noqa: F401  re-exported grammar helpers
    name, to_json, from_json, leaf_spec, ema_spec, ensemble_spec, conjugate_spec,
    diff_spec, frac_spec, std_spec, ema_t_spec, _infer_k,
)
from skaters.torch.conjugate import conjugate, reference_skater
from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.transform import from_reference


# ---------------------------------------------------------------------------
# running statistics on tensors (skaters.runstats)
# ---------------------------------------------------------------------------

def running_var_init() -> dict:
    return {"n": 0, "mean": torch.zeros((), dtype=DTYPE), "m2": torch.zeros((), dtype=DTYPE)}


def running_var_update(state: dict, x) -> dict:
    x = _t(x)
    n = state["n"] + 1
    delta = x - state["mean"]
    mean = state["mean"] + delta / n
    delta2 = x - mean
    m2 = state["m2"] + delta * delta2
    return {"n": n, "mean": mean, "m2": m2}


def running_var_get(state: dict):
    if state["n"] < 2:
        return state["mean"], torch.as_tensor(float("inf"), dtype=DTYPE)
    return state["mean"], state["m2"] / (state["n"] - 1)


def running_mse_get(state: dict):
    if state["n"] < 1:
        return torch.as_tensor(float("inf"), dtype=DTYPE)
    mean, var = running_var_get(state)
    if not bool(torch.isfinite(var)):
        return torch.as_tensor(float("inf"), dtype=DTYPE)
    return mean * mean + var


# ---------------------------------------------------------------------------
# ema skater and precision-weighted ensemble (skaters.ema, skaters.ensemble)
# ---------------------------------------------------------------------------

def ema(alpha: float = 0.05, k: int = 1):
    """``conjugate(leaf(k), ema_transform(alpha))`` with a torch EMA."""
    f = conjugate(reference_skater(reference_leaf(k=k)), from_reference("ema_transform", alpha=alpha), k=k)
    f.__name__ = f"ema(alpha={alpha}, k={k})"
    return f


def precision_weighted_ensemble(skaters: list, k: int = 1, floor: float = 1e-6):
    """Inverse-MSE weighting of sub-skaters' means, Dists combined exactly."""
    n = len(skaters)
    assert n > 0

    def _skater(y, state=None):
        y = _t(y)
        if state is None:
            state = {
                "sub": [None] * n,
                "queues": [[deque() for _ in range(k)] for _ in range(n)],
                "stats": [[running_var_init() for _ in range(k)] for _ in range(n)],
            }
        all_dists = []
        for i, f in enumerate(skaters):
            dists_i, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(dists_i)
        for i in range(n):
            for h in range(k):
                q = state["queues"][i][h]
                q.append(all_dists[i][h].mean)
                if len(q) > h + 1:
                    pred_mean = q.popleft()
                    error = y - pred_mean
                    state["stats"][i][h] = running_var_update(state["stats"][i][h], error)
        combined = []
        for h in range(k):
            weights = []
            for i in range(n):
                mse = running_mse_get(state["stats"][i][h])
                if bool(torch.isfinite(mse)):
                    w = 1.0 / torch.clamp(mse, min=floor)
                else:
                    w = torch.as_tensor(floor, dtype=DTYPE)
                weights.append(w)
            combined.append(TorchDist.combine([all_dists[i][h] for i in range(n)], weights))
        return combined, state

    _skater.__name__ = f"precision_weighted_ensemble(n={n}, k={k})"
    return _skater


# ---------------------------------------------------------------------------
# build: spec -> live torch skater
# ---------------------------------------------------------------------------

def build(spec: dict):
    op = spec["op"]
    if op == "leaf":
        f = reference_skater(reference_leaf(k=spec["k"]))
    elif op == "ema":
        f = ema(alpha=spec["alpha"], k=spec["k"])
    elif op == "ensemble":
        k = spec["k"]
        subs = [build(s) for s in spec["skaters"]]
        f = precision_weighted_ensemble(subs, k=k, floor=spec.get("floor", 1e-6))
    elif op == "conjugate":
        inner = build(spec["skater"])
        t = _build_transform(spec["transform"])
        k = _infer_k(spec["skater"])
        f = conjugate(inner, t, k=k)
    else:
        raise ValueError(f"Unknown op: {op}")
    f.__name__ = name(spec)
    return f


def _build_transform(spec: dict):
    op = spec["op"]
    if op == "diff":
        return from_reference("difference")
    if op == "frac":
        return from_reference("fractional_difference", d=spec["d"], window=spec.get("window", 50))
    if op == "std":
        return from_reference("standardize", alpha=spec.get("alpha", 0.05))
    if op == "ema_t":
        return from_reference("ema_transform", alpha=spec["alpha"])
    raise ValueError(f"Unknown transform op: {op}")
